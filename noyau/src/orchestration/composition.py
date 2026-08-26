"""Composition des situations operationnelles depuis l'etat persiste.

Le module lit l'etat de l'etablissement et en compose les situations soumises
au raisonnement. Il constitue la charniere entre la persistance et
l'orchestration: sans lui, chaque decision exigerait la transmission integrale
du parc.

Il ne comporte aucune logique metier: selectionner les chambres du parc et les
sejours d'une periode releve de la requete, apprecier leur adequation releve
des regles.
"""

import logging
from datetime import date

from sqlalchemy.orm import Session

from src.domaine import Chambre, Reservation
from src.donnees import (
    DepotAgents,
    DepotChambres,
    DepotIncidents,
    DepotReservations,
    DepotSecteurs,
    DepotTaches,
    EntiteIntrouvableError,
)

from .affectation import Demande, demande_depuis
from .planification import DemandePlanification, demande_de_service

logger = logging.getLogger(__name__)


class SituationIncompleteError(LookupError):
    """Signale une situation que l'etat persiste ne permet pas de composer."""


def composer_affectation(
    session: Session,
    reference_reservation: str,
    poids: dict[str, int] | None = None,
) -> Demande:
    """Compose la situation d'affectation d'un sejour depuis l'etat persiste.

    Le parc soumis est celui de l'etablissement; les occupations retenues sont
    les sejours deja affectes dont la periode chevauche celle du sejour a
    traiter. Restreindre les occupations a la periode evite de soumettre au
    raisonnement des sejours sans incidence sur la decision.
    """
    depot_reservations = DepotReservations(session)

    try:
        reservation = depot_reservations.retrouver(reference_reservation)
    except EntiteIntrouvableError as erreur:
        raise SituationIncompleteError(str(erreur)) from erreur

    parc = DepotChambres(session).lister()
    if not parc:
        raise SituationIncompleteError(
            "l'etablissement ne comporte aucune chambre; constituez la base"
        )

    occupations = [
        occupation
        for occupation in depot_reservations.lister_affectees_sur_periode(
            reservation.periode
        )
        if occupation.identifiant != reservation.identifiant
    ]

    logger.debug(
        "situation composee pour %s: %d chambres, %d occupations",
        reference_reservation,
        len(parc),
        len(occupations),
    )
    return demande_depuis(parc, reservation, occupations, poids)


def composer_planification(
    session: Session,
    secteur: str | None = None,
    poids: dict[str, int] | None = None,
) -> DemandePlanification:
    """Compose la journee de service depuis l'etat persiste.

    Le perimetre peut etre restreint a un secteur: la gouvernante d'un etage
    n'a pas a soumettre l'integralite de l'etablissement pour organiser son
    propre service.
    """
    depot_taches = DepotTaches(session)
    depot_agents = DepotAgents(session)

    taches = (
        [
            tache
            for tache in depot_taches.lister_a_planifier()
            if str(tache.secteur) == secteur
        ]
        if secteur
        else depot_taches.lister_a_planifier()
    )
    agents = (
        depot_agents.lister_par_secteur(secteur) if secteur else depot_agents.lister()
    )

    if not taches:
        raise SituationIncompleteError(
            f"aucune tache a planifier{f' sur le secteur {secteur}' if secteur else ''}"
        )
    if not agents:
        raise SituationIncompleteError(
            f"aucun agent{f' sur le secteur {secteur}' if secteur else ''}"
        )

    logger.debug(
        "service compose: %d taches, %d agents, secteur %s",
        len(taches),
        len(agents),
        secteur or "tous",
    )
    return demande_de_service(
        taches=taches,
        agents=agents,
        competences_par_agent=depot_agents.competences(),
        exigences_par_tache=depot_taches.exigences(),
        secteurs_reserves=DepotSecteurs(session).lister_reserves(),
        poids=poids,
    )


def chambres_du_parc(session: Session) -> list[Chambre]:
    """Restitue l'integralite du parc."""
    return DepotChambres(session).lister()


def arrivees_a_traiter(session: Session, jour: date) -> list[Reservation]:
    """Restitue les sejours arrivant un jour donne sans chambre affectee.

    Ce sont les situations que le responsable a effectivement a traiter.
    """
    return DepotReservations(session).lister_a_affecter(jour)


def etat_de_l_etablissement(session: Session, jour: date) -> dict[str, int]:
    """Restitue les grandeurs caracteristiques de l'etat courant."""
    parc = DepotChambres(session).lister()
    return {
        "chambres": len(parc),
        "disponibles": sum(1 for chambre in parc if chambre.est_attribuable),
        "arrivees_a_traiter": len(arrivees_a_traiter(session, jour)),
        "incidents_ouverts": len(DepotIncidents(session).lister_ouverts()),
        "taches_a_planifier": len(DepotTaches(session).lister_a_planifier()),
        "agents_affectables": sum(
            1 for agent in DepotAgents(session).lister() if agent.est_affectable
        ),
    }
