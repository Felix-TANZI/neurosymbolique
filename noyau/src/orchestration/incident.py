"""Traitement complet d'un incident affectant une chambre.

Le cas d'usage enchaine les consequences d'un incident: la chambre devient
indisponible, les sejours qu'elle heberge perdent leur affectation, et chacun
recoit une proposition de relogement.

L'enchainement constitue la reponse operationnelle attendue: un responsable
qui signale une fuite n'attend pas qu'on lui confirme la fuite, mais qu'on lui
dise ce qu'il advient des clients concernes.

Rien n'est applique. L'ensemble des consequences est etabli, presente, et
demeure suspendu a la validation d'un responsable. Une immobilisation de
chambre et un relogement engagent l'exploitation: ils ne peuvent resulter
d'une inference.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy.orm import Session

from src.domaine import (
    Chambre,
    EtatTechnique,
    Gravite,
    Incident,
    NumeroChambre,
    Periode,
    Reservation,
    TypeIncident,
)
from src.donnees import (
    DepotChambres,
    DepotReservations,
    EntiteIntrouvableError,
)

from .affectation import AffecterChambre, Recommandation, demande_depuis
from .composition import SituationIncompleteError

logger = logging.getLogger(__name__)

INCIDENTS_IMMOBILISANTS: frozenset[TypeIncident] = frozenset(
    {
        TypeIncident.DEGAT_DES_EAUX,
        TypeIncident.RISQUE_SECURITE,
        TypeIncident.PANNE_ELECTRIQUE,
    }
)


@dataclass(frozen=True, slots=True)
class SignalementDIncident:
    """Incident signale sur une chambre de l'etablissement."""

    chambre: str
    type_incident: TypeIncident
    gravite: Gravite
    description: str = ""
    jour: date = field(default_factory=date.today)


@dataclass(frozen=True, slots=True)
class SejourARelogerr:
    """Sejour prive de sa chambre et proposition qui lui est faite."""

    reservation: Reservation
    recommandation: Recommandation

    @property
    def reference(self) -> str:
        return str(self.reservation.identifiant)

    @property
    def a_trouve_une_chambre(self) -> bool:
        return self.recommandation.a_conclu

    @property
    def chambre_proposee(self) -> str | None:
        return self.recommandation.chambre_proposee


@dataclass(frozen=True, slots=True)
class ConsequencesDUnIncident:
    """Ensemble des consequences etablies pour un incident signale.

    Les consequences sont etablies mais non appliquees: elles constituent une
    proposition d'ensemble, que le responsable valide, corrige ou refuse.
    """

    incident: Incident
    immobilise_la_chambre: bool
    sejours_a_reloger: tuple[SejourARelogerr, ...] = ()
    justification: tuple[str, ...] = ()

    @property
    def chambre(self) -> str:
        return str(self.incident.chambre)

    @property
    def nombre_de_sejours(self) -> int:
        return len(self.sejours_a_reloger)

    @property
    def sejours_sans_solution(self) -> tuple[SejourARelogerr, ...]:
        return tuple(
            sejour for sejour in self.sejours_a_reloger if not sejour.a_trouve_une_chambre
        )

    @property
    def est_entierement_resolu(self) -> bool:
        """Indique que chaque sejour concerne dispose d'une proposition."""
        return not self.sejours_sans_solution

    @property
    def demande_une_intervention(self) -> bool:
        """Indique qu'un sejour demeure sans solution automatique."""
        return bool(self.sejours_sans_solution)


class TraiterUnIncident:
    """Etablit les consequences operationnelles d'un incident signale."""

    def __init__(self, affectation: AffecterChambre) -> None:
        self._affectation = affectation

    def executer(
        self,
        session: Session,
        signalement: SignalementDIncident,
        temps_maximal: float | None = None,
    ) -> ConsequencesDUnIncident:
        """Etablit l'immobilisation eventuelle et le relogement des sejours.

        L'ordre des operations suit celui des consequences reelles: la chambre
        devient indisponible, ce qui prive les sejours en cours de leur
        hebergement, ce qui appelle un relogement.
        """
        chambre = self._retrouver(session, signalement.chambre)
        incident = self._constituer(signalement)
        immobilise = self._immobilise(signalement)

        if not immobilise:
            logger.info(
                "incident %s sur %s sans immobilisation",
                signalement.type_incident.value,
                signalement.chambre,
            )
            return ConsequencesDUnIncident(
                incident=incident,
                immobilise_la_chambre=False,
                justification=(
                    f"La chambre {chambre.numero} demeure exploitable: "
                    f"l'incident signale ne la rend pas indisponible.",
                ),
            )

        concernes = self._sejours_heberges(session, chambre.numero, signalement.jour)
        relogements = self._reloger_ensemble(
            session, concernes, chambre.numero, temps_maximal, signalement.jour
        )

        consequences = ConsequencesDUnIncident(
            incident=incident,
            immobilise_la_chambre=True,
            sejours_a_reloger=relogements,
            justification=self._justifier(chambre.numero, relogements),
        )
        logger.info(
            "incident traite sur %s: %d sejours concernes, %d sans solution",
            signalement.chambre,
            consequences.nombre_de_sejours,
            len(consequences.sejours_sans_solution),
        )
        return consequences

    @staticmethod
    def _retrouver(session: Session, numero: str) -> Chambre:
        """Retrouve la chambre concernee, ou signale son absence."""
        try:
            return DepotChambres(session).retrouver(NumeroChambre(numero))
        except EntiteIntrouvableError as erreur:
            raise SituationIncompleteError(
                f"la chambre {numero} n'appartient pas a l'etablissement"
            ) from erreur

    @staticmethod
    def _constituer(signalement: SignalementDIncident) -> Incident:
        """Constitue l'incident a partir du signalement."""
        return Incident(
            identifiant=f"I-{datetime.now():%Y%m%d%H%M%S}",
            chambre=NumeroChambre(signalement.chambre),
            type_incident=signalement.type_incident,
            gravite=signalement.gravite,
            signale_le=datetime.now(),
            description=signalement.description,
        )

    @staticmethod
    def _immobilise(signalement: SignalementDIncident) -> bool:
        """Etablit si l'incident rend la chambre indisponible.

        Le critere combine la nature et la gravite: une panne electrique
        mineure degrade le confort, une panne majeure interdit l'occupation.
        """
        return (
            signalement.type_incident in INCIDENTS_IMMOBILISANTS
            and signalement.gravite >= Gravite.MAJEURE
        ) or signalement.gravite is Gravite.CRITIQUE

    @staticmethod
    def _sejours_heberges(
        session: Session, chambre: NumeroChambre, jour: date
    ) -> list[Reservation]:
        """Restitue les sejours que la chambre heberge a compter du jour.

        Les sejours acheves ne sont pas concernes: leur client a quitte
        l'etablissement, l'immobilisation ne les affecte pas.
        """
        horizon = Periode(jour, date(jour.year + 1, jour.month, jour.day))
        return [
            sejour
            for sejour in DepotReservations(session).lister_sur_periode(horizon)
            if sejour.chambre_affectee == chambre and sejour.periode.depart > jour
        ]

    def _reloger_ensemble(
        self,
        session: Session,
        sejours: list[Reservation],
        chambre_immobilisee: NumeroChambre,
        temps_maximal: float | None,
        jour: date,
    ) -> tuple[SejourARelogerr, ...]:
        """Etablit les relogements en tenant compte de ceux deja proposes.

        Les sejours sont traites successivement, chaque proposition retenue
        devenant une occupation pour les suivantes. Sans cette precaution,
        deux clients pourraient se voir proposer la meme chambre, et
        l'ensemble des propositions serait inapplicable.

        L'ordre suit la date d'arrivee: un sejour deja commence appelle une
        solution plus urgente qu'un sejour a venir.
        """
        retenues: list[Reservation] = []
        relogements: list[SejourARelogerr] = []

        for sejour in sorted(sejours, key=lambda s: s.periode.arrivee):
            relogement = self._reloger(
                session, sejour, chambre_immobilisee, temps_maximal, jour, retenues
            )
            relogements.append(relogement)

            if relogement.chambre_proposee is not None:
                retenues.append(
                    sejour.avec_chambre(
                        NumeroChambre(relogement.chambre_proposee.removeprefix("c"))
                    )
                )

        return tuple(relogements)

    def _reloger(
        self,
        session: Session,
        sejour: Reservation,
        chambre_immobilisee: NumeroChambre,
        temps_maximal: float | None,
        jour: date,
        deja_proposees: list[Reservation] | None = None,
    ) -> SejourARelogerr:
        """Etablit une proposition de relogement pour un sejour.

        Le parc soumis exclut la chambre immobilisee, ce qui evite qu'elle ne
        soit proposee a nouveau. Les occupations concurrentes demeurent prises
        en compte: reloger un client dans une chambre deja retenue par un autre
        deplacerait le probleme.
        """
        depot_chambres = DepotChambres(session)
        depot_reservations = DepotReservations(session)

        parc = [
            chambre
            for chambre in depot_chambres.lister()
            if chambre.numero != chambre_immobilisee
        ]
        occupations = [
            occupation
            for occupation in depot_reservations.lister_affectees_sur_periode(
                sejour.periode
            )
            if occupation.identifiant != sejour.identifiant
            and occupation.chambre_affectee != chambre_immobilisee
        ] + [
            proposee
            for proposee in (deja_proposees or [])
            if proposee.periode.chevauche(sejour.periode)
        ]

        demande = demande_depuis(
            parc, sejour.avec_chambre(None), occupations, jour=jour
        )
        return SejourARelogerr(
            reservation=sejour,
            recommandation=self._affectation.executer(demande, temps_maximal),
        )

    @staticmethod
    def _justifier(
        chambre: NumeroChambre, relogements: tuple[SejourARelogerr, ...]
    ) -> tuple[str, ...]:
        """Formule les consequences etablies."""
        enonces = [f"La chambre {chambre} devient indisponible."]

        if not relogements:
            enonces.append("Aucun sejour en cours n'est affecte.")
            return tuple(enonces)

        pluriel = "s" if len(relogements) > 1 else ""
        enonces.append(
            f"{len(relogements)} sejour{pluriel} doi{'vent' if pluriel else 't'} "
            f"etre reloge{pluriel}."
        )

        for relogement in relogements:
            if relogement.a_trouve_une_chambre:
                enonces.append(
                    f"{relogement.reference} peut etre reloge en "
                    f"{relogement.chambre_proposee}."
                )
            else:
                enonces.append(
                    f"{relogement.reference} ne peut etre reloge: "
                    f"aucune chambre du parc ne convient."
                )

        return tuple(enonces)


def etat_technique_apres(signalement: SignalementDIncident) -> EtatTechnique:
    """Restitue l'etat technique que l'incident confere a la chambre."""
    if TraiterUnIncident._immobilise(signalement):
        return EtatTechnique.BLOQUEE
    return EtatTechnique.DEGRADEE
