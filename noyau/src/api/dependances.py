"""Fourniture des ressources partagees aux routes.

Les cas d'usage et le moteur de base sont construits une seule fois pour la
duree du service: leur reconstruction a chaque requete degraderait la latence
sans apporter de fraicheur, la base de connaissances evoluant par action
d'administration.

Les sessions de base, en revanche, sont ouvertes et refermees a chaque requete:
une session partagee entre requetes concurrentes exposerait a des lectures
incoherentes.
"""

import logging
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.api.schemas import Anomalie
from src.donnees import (
    BaseIndisponibleError,
    creer_fabrique_de_sessions,
    creer_moteur,
    session_de_travail,
)
from src.neuronal.inference_preentrainee import InterpretePreentraineDEnonces
from src.neuronal.specialisation import charger_specialise
from src.orchestration import (
    AffecterChambre,
    ConnaissancesIndisponiblesError,
    PlanifierNettoyage,
    TraiterUnIncident,
    creer_cas_usage,
    creer_cas_usage_housekeeping,
)
from src.orchestration.arbitrage import ArbitrerUnConflit

logger = logging.getLogger(__name__)

RACINE_CONNAISSANCES = Path(__file__).resolve().parents[2].parent / "connaissances"
RACINE_MODELES = Path(__file__).resolve().parents[2] / "modeles"
MODELE_PREENTRAINE = RACINE_MODELES / "interprete-preentraine"


class InterpreteIndisponibleError(RuntimeError):
    """Signale l'absence d'un modele d'interpretation exploitable."""


def _anomalie(code: str, message: str, statut: int) -> HTTPException:
    """Construit une reponse d'anomalie exploitable par le client."""
    return HTTPException(
        status_code=statut,
        detail=Anomalie(code=code, message=message).model_dump(),
    )


@lru_cache(maxsize=1)
def obtenir_cas_usage() -> AffecterChambre:
    """Construit le cas d'usage des chambres une seule fois."""
    return creer_cas_usage(RACINE_CONNAISSANCES)


@lru_cache(maxsize=1)
def obtenir_cas_usage_housekeeping() -> PlanifierNettoyage:
    """Construit le cas d'usage du service housekeeping une seule fois."""
    return creer_cas_usage_housekeeping(RACINE_CONNAISSANCES)


@lru_cache(maxsize=1)
def obtenir_traitement_d_incident() -> TraiterUnIncident:
    """Construit le cas d'usage de traitement d'incident une seule fois."""
    return TraiterUnIncident(obtenir_cas_usage())


@lru_cache(maxsize=1)
def obtenir_arbitrage() -> ArbitrerUnConflit:
    """Construit le cas d'usage d'arbitrage une seule fois."""
    return ArbitrerUnConflit(obtenir_cas_usage())


@lru_cache(maxsize=1)
def obtenir_interprete() -> InterpretePreentraineDEnonces:
    """Charge le modele d'interpretation une seule fois.

    Le modele fonde sur un encodeur preentraine est retenu: la mesure etablit
    qu'il reconnait les intentions exprimees en des termes absents du corpus
    d'entrainement, ce dont le modele appris depuis l'initialisation demeure
    incapable.
    """
    if not (MODELE_PREENTRAINE / "parametres.pt").is_file():
        raise InterpreteIndisponibleError(
            f"aucun modele d'interpretation sous {MODELE_PREENTRAINE}; "
            "executez le script de specialisation"
        )
    modele, tokeniseur = charger_specialise(MODELE_PREENTRAINE)
    logger.info("modele d'interpretation charge depuis %s", MODELE_PREENTRAINE)
    return InterpretePreentraineDEnonces(modele, tokeniseur)


@lru_cache(maxsize=1)
def obtenir_moteur() -> Engine:
    """Construit le moteur de base une seule fois."""
    return creer_moteur()


def fournir_cas_usage() -> Iterator[AffecterChambre]:
    """Fournit le cas d'usage des chambres, en signalant toute indisponibilite."""
    try:
        yield obtenir_cas_usage()
    except ConnaissancesIndisponiblesError as erreur:
        logger.exception("base de connaissances indisponible")
        raise _anomalie(
            "connaissances_indisponibles",
            str(erreur),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from erreur


def fournir_cas_usage_housekeeping() -> Iterator[PlanifierNettoyage]:
    """Fournit le cas d'usage housekeeping, en signalant toute indisponibilite."""
    try:
        yield obtenir_cas_usage_housekeeping()
    except ConnaissancesIndisponiblesError as erreur:
        logger.exception("base de connaissances indisponible")
        raise _anomalie(
            "connaissances_indisponibles",
            str(erreur),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from erreur


def fournir_traitement_d_incident() -> Iterator[TraiterUnIncident]:
    """Fournit le traitement d'incident, en signalant toute indisponibilite."""
    try:
        yield obtenir_traitement_d_incident()
    except ConnaissancesIndisponiblesError as erreur:
        logger.exception("base de connaissances indisponible")
        raise _anomalie(
            "connaissances_indisponibles",
            str(erreur),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from erreur


def fournir_arbitrage() -> Iterator[ArbitrerUnConflit]:
    """Fournit l'arbitrage, en signalant toute indisponibilite."""
    try:
        yield obtenir_arbitrage()
    except ConnaissancesIndisponiblesError as erreur:
        logger.exception("base de connaissances indisponible")
        raise _anomalie(
            "connaissances_indisponibles",
            str(erreur),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from erreur


def fournir_interprete() -> Iterator[InterpretePreentraineDEnonces]:
    """Fournit l'interprete, en signalant toute indisponibilite."""
    try:
        yield obtenir_interprete()
    except InterpreteIndisponibleError as erreur:
        logger.exception("modele d'interpretation indisponible")
        raise _anomalie(
            "interprete_indisponible",
            str(erreur),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from erreur


def fournir_session() -> Iterator[Session]:
    """Ouvre une session de base pour la duree d'une requete."""
    try:
        fabrique = creer_fabrique_de_sessions(obtenir_moteur())
    except BaseIndisponibleError as erreur:
        logger.exception("base de donnees indisponible")
        raise _anomalie(
            "base_indisponible", str(erreur), status.HTTP_503_SERVICE_UNAVAILABLE
        ) from erreur

    try:
        with session_de_travail(fabrique) as session:
            yield session
    except SQLAlchemyError as erreur:
        logger.exception("defaillance de la base de donnees")
        raise _anomalie(
            "base_indisponible",
            "l'etat de l'etablissement n'a pu etre consulte",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from erreur


Arbitrage = Annotated[ArbitrerUnConflit, Depends(fournir_arbitrage)]
CasUsage = Annotated[AffecterChambre, Depends(fournir_cas_usage)]
CasUsageHousekeeping = Annotated[
    PlanifierNettoyage, Depends(fournir_cas_usage_housekeeping)
]
InterpreteDEnonces = Annotated[
    InterpretePreentraineDEnonces, Depends(fournir_interprete)
]
SessionDeBase = Annotated[Session, Depends(fournir_session)]
TraitementDIncident = Annotated[
    TraiterUnIncident, Depends(fournir_traitement_d_incident)
]
