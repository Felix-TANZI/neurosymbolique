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
from src.orchestration import (
    AffecterChambre,
    ConnaissancesIndisponiblesError,
    PlanifierNettoyage,
    creer_cas_usage,
    creer_cas_usage_housekeeping,
)

logger = logging.getLogger(__name__)

RACINE_CONNAISSANCES = Path(__file__).resolve().parents[2].parent / "connaissances"


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


CasUsage = Annotated[AffecterChambre, Depends(fournir_cas_usage)]
CasUsageHousekeeping = Annotated[
    PlanifierNettoyage, Depends(fournir_cas_usage_housekeeping)
]
SessionDeBase = Annotated[Session, Depends(fournir_session)]
