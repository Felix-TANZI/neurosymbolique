"""Interface de programmation du systeme d'aide a la decision.

L'interface expose le cycle de decision sans jamais l'appliquer: toute
recommandation demeure soumise a la validation d'un responsable. La
documentation est engendree a partir des schemas d'echange.
"""

import logging
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status

from src.api.schemas import (
    Anomalie,
    ContrepartieSortante,
    DemandeAffectation,
    MotifSortant,
    OptionEcarteeSortante,
    RecommandationSortante,
)
from src.gouvernance import GabaritIntrouvableError
from src.orchestration import (
    AffecterChambre,
    ConnaissancesIndisponiblesError,
    Demande,
    DemandeInvalideError,
    Recommandation,
    creer_cas_usage,
)
from src.symbolique.regles import MoteurIndisponibleError

logger = logging.getLogger(__name__)

RACINE_CONNAISSANCES = Path(__file__).resolve().parents[2].parent / "connaissances"

DESCRIPTION = """
Systeme de raisonnement neuro-symbolique pour l'aide a la decision critique
dans la gestion des operations internes d'un hotel.

Le systeme etablit les options admissibles au regard des contraintes dures,
ordonne celles-ci selon les preferences souples, et restitue pour chaque
option ecartee le motif de son rejet. Aucune recommandation n'est appliquee:
la validation par un responsable demeure requise.
"""


@lru_cache(maxsize=1)
def obtenir_cas_usage() -> AffecterChambre:
    """Construit le cas d'usage une seule fois pour la duree du service.

    Le chargement des regles et des gabarits a chaque requete degraderait la
    latence sans apporter de fraicheur: la base de connaissances evolue par
    action d'administration.
    """
    return creer_cas_usage(RACINE_CONNAISSANCES)


def fournir_cas_usage() -> Iterator[AffecterChambre]:
    """Fournit le cas d'usage aux routes, en signalant toute indisponibilite."""
    try:
        yield obtenir_cas_usage()
    except ConnaissancesIndisponiblesError as erreur:
        logger.exception("base de connaissances indisponible")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=Anomalie(
                code="connaissances_indisponibles", message=str(erreur)
            ).model_dump(),
        ) from erreur


CasUsage = Annotated[AffecterChambre, Depends(fournir_cas_usage)]


def creer_application() -> FastAPI:
    """Construit l'application et declare ses routes."""
    application = FastAPI(
        title="Aide a la decision critique hoteliere",
        description=DESCRIPTION,
        version="0.1.0",
    )

    @application.get(
        "/sante",
        summary="Verifier la disponibilite du service",
        tags=["service"],
    )
    def sante() -> dict[str, str]:
        """Indique que le service repond et que ses connaissances sont chargees."""
        obtenir_cas_usage()
        return {"etat": "disponible"}

    @application.post(
        "/affectations",
        response_model=RecommandationSortante,
        summary="Recommander une chambre pour une reservation",
        tags=["affectation"],
        responses={
            422: {"description": "Demande structurellement incoherente"},
            500: {"description": "Defaillance du raisonnement"},
            503: {"description": "Base de connaissances indisponible"},
        },
    )
    def recommander(
        demande: DemandeAffectation, cas: CasUsage
    ) -> RecommandationSortante:
        """Etablit les options admissibles et recommande la plus adaptee.

        La recommandation n'est pas appliquee. Elle est accompagnee de sa
        justification, des preferences sacrifiees et du motif de rejet de
        chaque option ecartee.
        """
        situation = _vers_domaine(demande)
        recommandation = _raisonner(cas, situation, demande.temps_maximal)
        return _vers_reponse(recommandation)

    return application


def _vers_domaine(demande: DemandeAffectation) -> Demande:
    """Convertit une demande entrante en situation du domaine."""
    try:
        return Demande(
            parc=tuple(chambre.vers_domaine() for chambre in demande.parc),
            reservation=demande.reservation.vers_domaine(),
            occupations=tuple(
                occupation.vers_domaine() for occupation in demande.occupations
            ),
            poids=demande.poids,
        )
    except (DemandeInvalideError, ValueError) as erreur:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=Anomalie(code="demande_invalide", message=str(erreur)).model_dump(),
        ) from erreur


def _raisonner(
    cas: AffecterChambre, situation: Demande, temps_maximal: float | None
) -> Recommandation:
    """Execute le cycle de decision en signalant toute defaillance."""
    try:
        return cas.executer(situation, temps_maximal)
    except MoteurIndisponibleError as erreur:
        logger.exception("le moteur de regles n'a pu traiter la situation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Anomalie(
                code="raisonnement_indisponible", message=str(erreur)
            ).model_dump(),
        ) from erreur
    except GabaritIntrouvableError as erreur:
        logger.exception("un motif de raisonnement ne dispose d'aucune formulation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Anomalie(
                code="justification_incomplete", message=str(erreur)
            ).model_dump(),
        ) from erreur


def _vers_reponse(recommandation: Recommandation) -> RecommandationSortante:
    """Convertit une recommandation du domaine en reponse publique."""
    resultat = recommandation.resultat
    contreparties = [
        ContrepartieSortante(
            code=penalite.motif,
            poids=penalite.poids,
            formulation=enonce.texte,
        )
        for penalite, enonce in zip(
            resultat.penalites,
            recommandation.justification.contreparties,
            strict=True,
        )
    ]
    return RecommandationSortante(
        a_conclu=recommandation.a_conclu,
        chambre_proposee=recommandation.chambre_proposee,
        justification=recommandation.justification.en_texte(),
        chambres_examinees=recommandation.nombre_examinees,
        chambres_admissibles=sorted(resultat.admissibles),
        cout=resultat.cout,
        optimal=resultat.optimal,
        sous_reserve=recommandation.sous_reserve,
        contreparties=contreparties,
        options_ecartees=[
            OptionEcarteeSortante(
                chambre=option.chambre,
                motifs=[
                    MotifSortant(code=motif.motif, detail=motif.detail)
                    for motif in option.motifs
                ],
                formulations=list(option.formulations),
            )
            for option in recommandation.options_ecartees
        ],
    )


application = creer_application()
