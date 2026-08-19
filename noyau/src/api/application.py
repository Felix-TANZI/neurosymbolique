"""Interface de programmation du systeme d'aide a la decision.

L'interface expose les cycles de decision sans jamais les appliquer: toute
recommandation demeure soumise a la validation d'un responsable. La
documentation est engendree a partir des schemas d'echange.
"""

import logging
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import RedirectResponse

from src.api.schemas import (
    Anomalie,
    ContrepartieSortante,
    DemandeAffectation,
    MotifSortant,
    OptionEcarteeSortante,
    RecommandationSortante,
)
from src.api.schemas_housekeeping import (
    AffectationSortante,
    ChargeSortante,
    DemandePlanificationEntrante,
    PlanificationSortante,
    TacheEnAttenteSortante,
)
from src.gouvernance import GabaritIntrouvableError
from src.orchestration import (
    AffecterChambre,
    ConnaissancesIndisponiblesError,
    Demande,
    DemandeInvalideError,
    DemandePlanification,
    PlanificationProposee,
    PlanifierNettoyage,
    Recommandation,
    creer_cas_usage,
    creer_cas_usage_housekeeping,
    demande_de_service,
)
from src.symbolique.ordonnancement import OrdonnancementImpossibleError
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
    """Construit le cas d'usage des chambres une seule fois.

    Le chargement des regles et des gabarits a chaque requete degraderait la
    latence sans apporter de fraicheur: la base de connaissances evolue par
    action d'administration.
    """
    return creer_cas_usage(RACINE_CONNAISSANCES)


@lru_cache(maxsize=1)
def obtenir_cas_usage_housekeeping() -> PlanifierNettoyage:
    """Construit le cas d'usage du service housekeeping une seule fois."""
    return creer_cas_usage_housekeeping(RACINE_CONNAISSANCES)


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


def fournir_cas_usage_housekeeping() -> Iterator[PlanifierNettoyage]:
    """Fournit le cas d'usage housekeeping, en signalant toute indisponibilite."""
    try:
        yield obtenir_cas_usage_housekeeping()
    except ConnaissancesIndisponiblesError as erreur:
        logger.exception("base de connaissances indisponible")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=Anomalie(
                code="connaissances_indisponibles", message=str(erreur)
            ).model_dump(),
        ) from erreur


CasUsage = Annotated[AffecterChambre, Depends(fournir_cas_usage)]
CasUsageHousekeeping = Annotated[
    PlanifierNettoyage, Depends(fournir_cas_usage_housekeeping)
]


def creer_application() -> FastAPI:
    """Construit l'application et declare ses routes."""
    application = FastAPI(
        title="Aide a la decision critique hoteliere",
        description=DESCRIPTION,
        version="0.1.0",
    )

    @application.get("/", include_in_schema=False)
    def racine() -> RedirectResponse:
        """Oriente vers la documentation de l'interface."""
        return RedirectResponse(url="/docs")

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
        tags=["chambres"],
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

    @application.post(
        "/planifications",
        response_model=PlanificationSortante,
        summary="Planifier les taches de nettoyage sur les agents en service",
        tags=["housekeeping"],
        responses={
            422: {"description": "Demande structurellement incoherente"},
            500: {"description": "Defaillance du raisonnement"},
            503: {"description": "Base de connaissances indisponible"},
        },
    )
    def planifier(
        demande: DemandePlanificationEntrante, cas: CasUsageHousekeeping
    ) -> PlanificationSortante:
        """Etablit les paires admissibles puis ordonnance les taches.

        Le planning n'est pas applique. Il est accompagne de sa justification
        et, pour chaque tache demeuree en attente, de la cause distinguant
        l'absence d'agent admissible du manque de capacite.
        """
        service = _vers_service(demande)
        proposition = _planifier(cas, service, demande.temps_maximal)
        return _vers_reponse_de_planification(proposition)

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


def _vers_service(demande: DemandePlanificationEntrante) -> DemandePlanification:
    """Convertit une demande entrante en journee de service du domaine."""
    try:
        return demande_de_service(
            taches=[tache.vers_domaine() for tache in demande.taches],
            agents=[agent.vers_domaine() for agent in demande.agents],
            competences_par_agent={
                agent.identifiant: agent.competences
                for agent in demande.agents
                if agent.competences
            },
            exigences_par_tache={
                tache.identifiant: tache.competences_requises
                for tache in demande.taches
                if tache.competences_requises
            },
            secteurs_reserves=demande.secteurs_reserves,
            poids=demande.poids,
        )
    except (DemandeInvalideError, ValueError) as erreur:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=Anomalie(code="demande_invalide", message=str(erreur)).model_dump(),
        ) from erreur


def _planifier(
    cas: PlanifierNettoyage,
    service: DemandePlanification,
    temps_maximal: float | None,
) -> PlanificationProposee:
    """Execute le cycle de planification en signalant toute defaillance."""
    try:
        return cas.executer(service, temps_maximal)
    except MoteurIndisponibleError as erreur:
        logger.exception("le moteur de regles n'a pu traiter le service")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Anomalie(
                code="raisonnement_indisponible", message=str(erreur)
            ).model_dump(),
        ) from erreur
    except OrdonnancementImpossibleError as erreur:
        logger.exception("le solveur d'ordonnancement n'a pu traiter le service")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Anomalie(
                code="ordonnancement_indisponible", message=str(erreur)
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


def _en_horaire(minutes: int) -> str:
    """Exprime un instant en minutes depuis minuit sous forme horaire."""
    return f"{minutes // 60:02d}h{minutes % 60:02d}"


def _vers_reponse_de_planification(
    proposition: PlanificationProposee,
) -> PlanificationSortante:
    """Convertit une planification du domaine en reponse publique."""
    ordonnancement = proposition.ordonnancement
    return PlanificationSortante(
        est_complete=proposition.est_complete,
        justification=list(proposition.justification),
        affectations=[
            AffectationSortante(
                tache=planifiee.tache,
                agent=planifiee.agent,
                debut=_en_horaire(planifiee.debut_minutes),
                fin=_en_horaire(planifiee.fin_minutes),
                duree_minutes=planifiee.duree_minutes,
            )
            for planifiee in sorted(
                ordonnancement.planifiees, key=lambda p: (p.agent, p.debut_minutes)
            )
        ],
        taches_en_attente=[
            TacheEnAttenteSortante(
                tache=attente.tache,
                cause=attente.cause,
                motifs=[str(motif) for motif in attente.motifs],
            )
            for attente in proposition.non_planifiees
        ],
        charges=[
            ChargeSortante(agent=agent, minutes=minutes)
            for agent, minutes in sorted(proposition.charge_par_agent.items())
        ],
        cout=ordonnancement.cout,
        optimal=ordonnancement.optimal,
        sous_reserve=proposition.sous_reserve,
    )


application = creer_application()
