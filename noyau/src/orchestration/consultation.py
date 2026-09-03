"""Restitution de l'etat de l'etablissement en reponse a une consultation.

Une consultation interroge l'etat courant et le restitue; elle n'engage aucun
raisonnement et n'appelle aucune validation. La distinction avec un arbitrage
est structurelle: une consultation etablit ce qui est, un arbitrage etablit ce
qu'il convient de faire.

Les reponses sont formulees a partir des seules donnees relevees. Aucune
inference n'y intervient: une consultation qui avancerait une conclusion non
verifiee tromperait le responsable sur la nature de ce qu'il lit.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from src.domaine import (
    Chambre,
    EtatOccupation,
    EtatProprete,
    EtatTechnique,
    NumeroChambre,
    Periode,
    Reservation,
)
from src.donnees import (
    DepotAgents,
    DepotChambres,
    DepotReservations,
    DepotTaches,
    EntiteIntrouvableError,
)
from src.neuronal.inference import Interpretation
from src.neuronal.taxonomie import Intention, TypeDEntite

logger = logging.getLogger(__name__)


class ConsultationImpossibleError(ValueError):
    """Signale une consultation que l'etat disponible ne permet pas d'honorer."""


@dataclass(frozen=True, slots=True)
class Reponse:
    """Reponse a une consultation, formulee et accompagnee de ses elements.

    L'enonce restitue la reponse en une phrase; les elements en portent le
    detail, afin qu'une interface puisse presenter l'un, l'autre ou les deux
    selon la place dont elle dispose.
    """

    enonce: str
    elements: tuple[str, ...] = ()
    nombre: int | None = None
    intention: str = ""

    @property
    def est_vide(self) -> bool:
        return not self.elements and self.nombre in (None, 0)


@dataclass(frozen=True, slots=True)
class ParametresDeConsultation:
    """Elements extraits de l'enonce et utiles a la consultation."""

    etage: int | None = None
    chambre: str | None = None
    reservation: str | None = None
    secteur: str | None = None
    jour: date = field(default_factory=date.today)

    @classmethod
    def depuis(
        cls, interpretation: Interpretation, jour: date | None = None
    ) -> "ParametresDeConsultation":
        """Releve les parametres exploitables d'une interpretation."""
        etage_lu = interpretation.valeur_de(TypeDEntite.ETAGE.value)
        return cls(
            etage=int(etage_lu) if etage_lu and etage_lu.isdigit() else None,
            chambre=interpretation.valeur_de(TypeDEntite.CHAMBRE.value),
            reservation=interpretation.valeur_de(TypeDEntite.RESERVATION.value),
            secteur=interpretation.valeur_de(TypeDEntite.SECTEUR.value),
            jour=jour or date.today(),
        )


class Consultation:
    """Repond aux interrogations portant sur l'etat de l'etablissement."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._chambres = DepotChambres(session)
        self._reservations = DepotReservations(session)
        self._agents = DepotAgents(session)
        self._taches = DepotTaches(session)

    def repondre(
        self, intention: Intention, parametres: ParametresDeConsultation
    ) -> Reponse:
        """Restitue la reponse correspondant a l'intention consultee."""
        traitements = {
            Intention.CONSULTER_PARC: self._parc,
            Intention.CONSULTER_DISPONIBILITE: self._disponibles,
            Intention.CONSULTER_INDISPONIBLES: self._indisponibles,
            Intention.CONSULTER_ARRIVEES: self._arrivees,
            Intention.CONSULTER_AGENTS: self._agents_en_service,
            Intention.CONSULTER_TACHES: self._taches_en_attente,
            Intention.CONSULTER_CHAMBRE: self._une_chambre,
            Intention.CONSULTER_SEJOUR: self._un_sejour,
        }

        traitement = traitements.get(intention)
        if traitement is None:
            raise ConsultationImpossibleError(
                f"l'intention {intention.value} ne releve pas d'une consultation"
            )

        reponse = traitement(parametres)
        logger.info(
            "consultation %s: %d elements", intention.value, len(reponse.elements)
        )
        return reponse

    def _parc(self, parametres: ParametresDeConsultation) -> Reponse:
        """Restitue la composition du parc."""
        del parametres
        parc = self._chambres.lister()
        par_categorie: dict[str, int] = {}
        for chambre in parc:
            nom = chambre.categorie.name.lower()
            par_categorie[nom] = par_categorie.get(nom, 0) + 1

        detail = ", ".join(
            f"{compte} {nom}" for nom, compte in sorted(par_categorie.items())
        )
        return Reponse(
            enonce=f"L'etablissement compte {len(parc)} chambres: {detail}.",
            elements=tuple(
                f"{compte} chambres de categorie {nom}"
                for nom, compte in sorted(par_categorie.items())
            ),
            nombre=len(parc),
            intention=Intention.CONSULTER_PARC.value,
        )

    def _disponibles(self, parametres: ParametresDeConsultation) -> Reponse:
        """Restitue les chambres immediatement attribuables."""
        retenues = [
            chambre
            for chambre in self._filtrer_par_etage(parametres.etage)
            if chambre.etat_technique is EtatTechnique.OPERATIONNELLE
            and chambre.etat_proprete is EtatProprete.PRETE
            and chambre.etat_occupation is EtatOccupation.LIBRE
        ]

        precision = f" a l'etage {parametres.etage}" if parametres.etage else ""
        if not retenues:
            return Reponse(
                enonce=f"Aucune chambre n'est disponible{precision}.",
                intention=Intention.CONSULTER_DISPONIBILITE.value,
            )

        return Reponse(
            enonce=(
                f"{len(retenues)} chambres sont libres et pretes{precision}."
            ),
            elements=tuple(
                f"{chambre.numero} · {chambre.categorie.name.lower()}"
                for chambre in retenues
            ),
            nombre=len(retenues),
            intention=Intention.CONSULTER_DISPONIBILITE.value,
        )

    def _indisponibles(self, parametres: ParametresDeConsultation) -> Reponse:
        """Restitue les chambres retirees de l'exploitation."""
        retenues = [
            chambre
            for chambre in self._filtrer_par_etage(parametres.etage)
            if chambre.etat_technique is not EtatTechnique.OPERATIONNELLE
        ]

        precision = f" a l'etage {parametres.etage}" if parametres.etage else ""
        if not retenues:
            return Reponse(
                enonce=f"Aucune chambre n'est hors service{precision}.",
                intention=Intention.CONSULTER_INDISPONIBLES.value,
            )

        return Reponse(
            enonce=(
                f"{len(retenues)} chambres sont hors service{precision}."
            ),
            elements=tuple(
                f"{chambre.numero} · {chambre.etat_technique.value.replace('_', ' ')}"
                for chambre in retenues
            ),
            nombre=len(retenues),
            intention=Intention.CONSULTER_INDISPONIBLES.value,
        )

    def _arrivees(self, parametres: ParametresDeConsultation) -> Reponse:
        """Restitue les sejours dont l'arrivee est prevue le jour consulte."""
        jour = parametres.jour
        attendus = [
            sejour
            for sejour in self._reservations.lister_sur_periode(
                Periode(jour, jour.replace(day=jour.day) + timedelta(days=1))
            )
            if sejour.periode.arrivee == jour
        ]
        sans_chambre = [
            sejour for sejour in attendus if sejour.chambre_affectee is None
        ]

        if not attendus:
            return Reponse(
                enonce="Aucune arrivee n'est prevue aujourd'hui.",
                intention=Intention.CONSULTER_ARRIVEES.value,
            )

        reste = (
            f", dont {len(sans_chambre)} sans chambre attribuee"
            if sans_chambre
            else ", toutes disposent d'une chambre"
        )
        return Reponse(
            enonce=f"{len(attendus)} arrivees sont prevues aujourd'hui{reste}.",
            elements=tuple(
                f"{sejour.identifiant} · {sejour.nombre_personnes} personnes"
                + (
                    f" · chambre {sejour.chambre_affectee}"
                    if sejour.chambre_affectee
                    else " · sans chambre"
                )
                for sejour in attendus
            ),
            nombre=len(attendus),
            intention=Intention.CONSULTER_ARRIVEES.value,
        )

    def _agents_en_service(self, parametres: ParametresDeConsultation) -> Reponse:
        """Restitue les agents affectables."""
        effectif = self._agents.lister()
        retenus = (
            [
                agent
                for agent in effectif
                if _correspond(str(agent.secteur), parametres.secteur)
            ]
            if parametres.secteur
            else list(effectif)
        )

        precision = f" sur le secteur {parametres.secteur}" if parametres.secteur else ""
        if not retenus:
            return Reponse(
                enonce=f"Aucun agent n'est en service{precision}.",
                intention=Intention.CONSULTER_AGENTS.value,
            )

        return Reponse(
            enonce=f"{len(retenus)} agents sont en service{precision}.",
            elements=tuple(
                f"{agent.identifiant} · secteur {agent.secteur}" for agent in retenus
            ),
            nombre=len(retenus),
            intention=Intention.CONSULTER_AGENTS.value,
        )

    def _taches_en_attente(self, parametres: ParametresDeConsultation) -> Reponse:
        """Restitue les prestations d'etage demeurant a traiter."""
        retenues = (
            list(self._taches.lister_par_secteur(parametres.secteur))
            if parametres.secteur
            else list(self._taches.lister_a_planifier())
        )

        precision = f" sur {parametres.secteur}" if parametres.secteur else ""
        if not retenues:
            return Reponse(
                enonce=f"Aucune tache n'est en attente{precision}.",
                intention=Intention.CONSULTER_TACHES.value,
            )

        return Reponse(
            enonce=f"{len(retenues)} chambres restent a traiter{precision}.",
            elements=tuple(
                f"{tache.chambre} · {tache.prestation.value.replace('_', ' ')}"
                for tache in retenues
            ),
            nombre=len(retenues),
            intention=Intention.CONSULTER_TACHES.value,
        )

    def _une_chambre(self, parametres: ParametresDeConsultation) -> Reponse:
        """Restitue l'etat d'une chambre designee."""
        if parametres.chambre is None:
            raise ConsultationImpossibleError(
                "aucune chambre n'est designee dans la demande"
            )

        try:
            chambre = self._chambres.retrouver(NumeroChambre(parametres.chambre))
        except EntiteIntrouvableError as erreur:
            raise ConsultationImpossibleError(
                f"la chambre {parametres.chambre} n'appartient pas a l'etablissement"
            ) from erreur

        return Reponse(
            enonce=_decrire_chambre(chambre),
            elements=(
                f"categorie {chambre.categorie.name.lower()}",
                f"capacite {chambre.capacite} personnes",
                f"proprete {chambre.etat_proprete.value.replace('_', ' ')}",
                f"etat technique {chambre.etat_technique.value}",
                f"occupation {chambre.etat_occupation.value}",
                *(
                    f"equipement {equipement.value.replace('_', ' ')}"
                    for equipement in sorted(
                        chambre.equipements, key=lambda e: e.value
                    )
                ),
            ),
            intention=Intention.CONSULTER_CHAMBRE.value,
        )

    def _un_sejour(self, parametres: ParametresDeConsultation) -> Reponse:
        """Restitue le detail d'un sejour designe."""
        if parametres.reservation is None:
            raise ConsultationImpossibleError(
                "aucun sejour n'est designe dans la demande"
            )

        try:
            sejour = self._reservations.retrouver(parametres.reservation)
        except EntiteIntrouvableError as erreur:
            raise ConsultationImpossibleError(
                f"le sejour {parametres.reservation} est introuvable"
            ) from erreur

        return Reponse(
            enonce=_decrire_sejour(sejour),
            elements=(
                f"{sejour.nombre_personnes} personnes",
                f"categorie {sejour.categorie_contractee.name.lower()}",
                f"du {sejour.periode.arrivee} au {sejour.periode.depart}",
                (
                    f"chambre {sejour.chambre_affectee}"
                    if sejour.chambre_affectee
                    else "aucune chambre attribuee"
                ),
                *(
                    f"exige {equipement.value.replace('_', ' ')}"
                    for equipement in sorted(
                        sejour.exigences_obligatoires, key=lambda e: e.value
                    )
                ),
            ),
            intention=Intention.CONSULTER_SEJOUR.value,
        )

    def _filtrer_par_etage(self, etage: int | None) -> list[Chambre]:
        """Restreint le parc a un etage lorsqu'il est precise."""
        parc = self._chambres.lister()
        if etage is None:
            return list(parc)
        return [chambre for chambre in parc if chambre.etage == etage]


def _normaliser(texte: str) -> str:
    """Ramene une designation a une forme comparable."""
    return texte.replace(" ", "").replace("_", "").lower()


def _correspond(valeur: str, recherchee: str | None) -> bool:
    """Compare deux designations en ignorant separateurs et casse."""
    if recherchee is None:
        return True
    return _normaliser(valeur) == _normaliser(recherchee)


def _decrire_chambre(chambre: Chambre) -> str:
    """Formule l'etat d'une chambre en une phrase."""
    if chambre.etat_technique is not EtatTechnique.OPERATIONNELLE:
        return (
            f"La chambre {chambre.numero} est hors service: "
            f"{chambre.etat_technique.value}."
        )
    if chambre.etat_occupation is not EtatOccupation.LIBRE:
        return f"La chambre {chambre.numero} est occupee."
    if chambre.etat_proprete is not EtatProprete.PRETE:
        return (
            f"La chambre {chambre.numero} est libre mais "
            f"{chambre.etat_proprete.value.replace('_', ' ')}."
        )
    return (
        f"La chambre {chambre.numero} est libre, prete et attribuable, "
        f"categorie {chambre.categorie.name.lower()}."
    )


def _decrire_sejour(sejour: Reservation) -> str:
    """Formule la situation d'un sejour en une phrase."""
    hebergement = (
        f"en chambre {sejour.chambre_affectee}"
        if sejour.chambre_affectee
        else "sans chambre attribuee"
    )
    return (
        f"Le sejour {sejour.identifiant} accueille {sejour.nombre_personnes} "
        f"personnes du {sejour.periode.arrivee} au {sejour.periode.depart}, "
        f"{hebergement}."
    )


def consulter(
    session: Session,
    interpretation: Interpretation,
    jour: date | None = None,
) -> Reponse:
    """Repond a une consultation etablie par interpretation d'un enonce."""
    return Consultation(session).repondre(
        Intention(interpretation.intention),
        ParametresDeConsultation.depuis(interpretation, jour),
    )
