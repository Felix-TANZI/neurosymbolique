"""Traitement complet d'un incident affectant une chambre.

Le cas d'usage enchaine les consequences d'un incident: la chambre devient
indisponible, les sejours qu'elle heberge perdent leur affectation, et chacun
se voit ouvrir un eventail de relogements possibles.

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
    Preferences,
    Reservation,
    TypeIncident,
)
from src.donnees import (
    DepotChambres,
    DepotReservations,
    EntiteIntrouvableError,
)

from .affectation import demande_depuis
from .composition import SituationIncompleteError
from .options import OPTIONS_PAR_DEFAUT, Eventail, ProposerDesOptions

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
    preferences: Preferences = field(default_factory=Preferences)


@dataclass(frozen=True, slots=True)
class SejourARelogerr:
    """Sejour prive de sa chambre et options qui lui sont ouvertes."""

    reservation: Reservation
    eventail: Eventail
    convoitees: frozenset[str] = field(default_factory=frozenset)

    @property
    def options_partagees(self) -> tuple[str, ...]:
        """Restitue les chambres qu'un autre sejour peut egalement recevoir.

        Une chambre proposee a deux sejours dont les periodes ne se
        chevauchent pas demeure attribuable a l'un ou a l'autre, mais non aux
        deux si leurs choix se portent sur elle. Le responsable doit le savoir
        avant d'arreter le premier choix.
        """
        return tuple(
            option.chambre
            for option in self.eventail.options
            if option.chambre in self.convoitees
        )

    @property
    def reference(self) -> str:
        return str(self.reservation.identifiant)

    @property
    def a_trouve_une_chambre(self) -> bool:
        return not self.eventail.est_vide

    @property
    def chambre_proposee(self) -> str | None:
        preferee = self.eventail.preferee
        return preferee.chambre if preferee else None

    @property
    def offre_un_choix(self) -> bool:
        return self.eventail.offre_un_choix


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

    def __init__(self, options: ProposerDesOptions) -> None:
        self._options = options

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
            session,
            concernes,
            chambre.numero,
            signalement.jour,
            temps_maximal,
            signalement.preferences,
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
        jour: date,
        temps_maximal: float | None,
        preferences: Preferences,
    ) -> tuple[SejourARelogerr, ...]:
        """Etablit les relogements en tenant compte de ceux deja proposes.

        Les sejours sont traites successivement, chaque proposition retenue
        devenant une occupation pour les suivantes. Sans cette precaution,
        deux clients pourraient se voir proposer la meme chambre, et
        l'ensemble des propositions serait inapplicable.

        L'ordre suit la date d'arrivee: un sejour deja commence appelle une
        solution plus urgente qu'un sejour a venir.
        """
        relogements: list[SejourARelogerr] = []
        retenues: list[Reservation] = []
        proposees: dict[str, list[str]] = {}

        for sejour in sorted(sejours, key=lambda s: s.periode.arrivee):
            relogement = self._reloger(
                session,
                sejour,
                chambre_immobilisee,
                jour,
                temps_maximal,
                preferences,
                retenues,
            )
            relogements.append(relogement)

            for option in relogement.eventail.options:
                proposees.setdefault(option.chambre, []).append(
                    relogement.reference
                )

            if relogement.chambre_proposee is not None:
                retenues.append(
                    sejour.avec_chambre(
                        NumeroChambre(relogement.chambre_proposee.removeprefix("c"))
                    )
                )

        partagees = frozenset(
            chambre
            for chambre, references in proposees.items()
            if len(references) > 1
        )

        return tuple(
            SejourARelogerr(
                reservation=relogement.reservation,
                eventail=relogement.eventail,
                convoitees=partagees,
            )
            for relogement in relogements
        )

    def _reloger(
        self,
        session: Session,
        sejour: Reservation,
        chambre_immobilisee: NumeroChambre,
        jour: date,
        temps_maximal: float | None,
        preferences: Preferences,
        deja_proposees: list[Reservation] | None = None,
    ) -> SejourARelogerr:
        """Etablit les options de relogement ouvertes a un sejour.

        Le parc soumis exclut la chambre immobilisee, ce qui evite qu'elle ne
        soit proposee a nouveau. Les occupations concurrentes demeurent prises
        en compte: reloger un client dans une chambre deja retenue par un autre
        deplacerait le probleme.

        Les preferences exprimees sur l'incident s'appliquent a chaque
        relogement: un responsable qui souhaite reloger a proximite l'entend
        pour l'ensemble des clients deplaces, non pour le premier seulement.
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
            parc,
            sejour.avec_chambre(None),
            occupations,
            jour=jour,
            preferences=preferences,
        )
        return SejourARelogerr(
            reservation=sejour,
            eventail=self._options.executer(
                demande, OPTIONS_PAR_DEFAUT, temps_maximal
            ),
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
                alternatives = (
                    f", ou {len(relogement.eventail.options) - 1} autres possibles"
                    if relogement.offre_un_choix
                    else ""
                )
                enonces.append(
                    f"{relogement.reference} peut etre reloge en "
                    f"{relogement.chambre_proposee}{alternatives}."
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
