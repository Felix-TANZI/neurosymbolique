"""Interface de programmation du systeme d'aide a la decision.

L'interface expose deux voies d'acces au raisonnement. La premiere recoit la
situation complete et rend le noyau utilisable sans etat persiste: un client
tiers peut soumettre son propre parc. La seconde designe une entite par sa
reference et compose la situation depuis l'etat de l'etablissement.

Aucune recommandation n'est appliquee: la validation par un responsable demeure
requise. La documentation est engendree a partir des schemas d'echange.
"""

import logging
from datetime import date

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from src.api.dependances import (
    CasUsage,
    CasUsageHousekeeping,
    SessionDeBase,
    obtenir_cas_usage,
)
from src.api.schemas import (
    Anomalie,
    ContrepartieSortante,
    DemandeAffectation,
    MotifSortant,
    OptionEcarteeSortante,
    RecommandationSortante,
)
from src.api.schemas_consultation import (
    AgentConsulte,
    ChambreConsultee,
    DemandeParReference,
    EtatDeLEtablissement,
    IncidentConsulte,
    ReservationConsultee,
    TacheConsultee,
)
from src.api.schemas_housekeeping import (
    AffectationSortante,
    ChargeSortante,
    DemandePlanificationEntrante,
    PlanificationSortante,
    TacheEnAttenteSortante,
)
from src.donnees import (
    DepotAgents,
    DepotChambres,
    DepotIncidents,
    DepotReservations,
    DepotTaches,
    EntiteIntrouvableError,
)
from src.gouvernance import GabaritIntrouvableError
from src.orchestration import (
    AffecterChambre,
    Demande,
    DemandeInvalideError,
    DemandePlanification,
    PlanificationProposee,
    PlanifierNettoyage,
    Recommandation,
    SituationIncompleteError,
    composer_affectation,
    composer_planification,
    demande_de_service,
    etat_de_l_etablissement,
)
from src.symbolique.ordonnancement import OrdonnancementImpossibleError
from src.symbolique.regles import MoteurIndisponibleError

logger = logging.getLogger(__name__)

DESCRIPTION = """
Systeme de raisonnement neuro-symbolique pour l'aide a la decision critique
dans la gestion des operations internes d'un hotel.

Le systeme etablit les options admissibles au regard des contraintes dures,
ordonne celles-ci selon les preferences souples, et restitue pour chaque
option ecartee le motif de son rejet. Aucune recommandation n'est appliquee:
la validation par un responsable demeure requise.

Deux voies d'acces coexistent. Les routes recevant une situation complete
rendent le raisonnement utilisable sans etat persiste. Les routes designant
une entite par sa reference composent la situation depuis l'etat de
l'etablissement.
"""


def _anomalie(code: str, message: str, statut: int) -> HTTPException:
    """Construit une reponse d'anomalie exploitable par le client."""
    return HTTPException(
        status_code=statut, detail=Anomalie(code=code, message=message).model_dump()
    )


def creer_application() -> FastAPI:
    """Construit l'application et declare ses routes."""
    application = FastAPI(
        title="Aide a la decision critique hoteliere",
        description=DESCRIPTION,
        version="0.2.0",
    )

    @application.get("/", include_in_schema=False)
    def racine() -> RedirectResponse:
        """Oriente vers la documentation de l'interface."""
        return RedirectResponse(url="/docs")

    @application.get(
        "/sante", summary="Verifier la disponibilite du service", tags=["service"]
    )
    def sante() -> dict[str, str]:
        """Indique que le service repond et que ses connaissances sont chargees."""
        obtenir_cas_usage()
        return {"etat": "disponible"}

    @application.get(
        "/etablissement",
        response_model=EtatDeLEtablissement,
        summary="Consulter l'etat courant de l'etablissement",
        tags=["etablissement"],
    )
    def etat(
        session: SessionDeBase, jour: date | None = None
    ) -> EtatDeLEtablissement:
        """Restitue les grandeurs caracteristiques de l'etat operationnel.

        Le jour est resolu a l'appel et non a la declaration: une valeur figee
        au demarrage du service deviendrait obsolete des le lendemain.
        """
        reference = jour or date.today()
        return EtatDeLEtablissement(
            jour=reference, **etat_de_l_etablissement(session, reference)
        )

    @application.get(
        "/chambres",
        response_model=list[ChambreConsultee],
        summary="Consulter le parc de chambres",
        tags=["etablissement"],
    )
    def chambres(
        session: SessionDeBase,
        secteur: str | None = Query(default=None),
        attribuables: bool = Query(default=False),
    ) -> list[ChambreConsultee]:
        """Restitue le parc, filtre par secteur ou restreint aux chambres pretes."""
        depot = DepotChambres(session)
        parc = depot.lister_par_secteur(secteur) if secteur else depot.lister()
        retenues = [c for c in parc if c.est_attribuable] if attribuables else parc
        return [ChambreConsultee.depuis(chambre) for chambre in retenues]

    @application.get(
        "/reservations/a-traiter",
        response_model=list[ReservationConsultee],
        summary="Consulter les arrivees sans chambre affectee",
        tags=["etablissement"],
    )
    def reservations_a_traiter(
        session: SessionDeBase, jour: date | None = None
    ) -> list[ReservationConsultee]:
        """Restitue les sejours qu'un responsable a effectivement a traiter."""
        reference = jour or date.today()
        return [
            ReservationConsultee.depuis(reservation)
            for reservation in DepotReservations(session).lister_a_affecter(reference)
        ]

    @application.get(
        "/reservations/{reference}",
        response_model=ReservationConsultee,
        summary="Consulter un sejour",
        tags=["etablissement"],
        responses={404: {"description": "Sejour absent de l'etablissement"}},
    )
    def reservation(session: SessionDeBase, reference: str) -> ReservationConsultee:
        """Restitue un sejour designe par sa reference."""
        try:
            return ReservationConsultee.depuis(
                DepotReservations(session).retrouver(reference)
            )
        except EntiteIntrouvableError as erreur:
            raise _anomalie(
                "entite_introuvable", str(erreur), status.HTTP_404_NOT_FOUND
            ) from erreur

    @application.get(
        "/agents",
        response_model=list[AgentConsulte],
        summary="Consulter les agents d'etage",
        tags=["etablissement"],
    )
    def agents(
        session: SessionDeBase, secteur: str | None = Query(default=None)
    ) -> list[AgentConsulte]:
        """Restitue les agents, filtres par secteur le cas echeant."""
        depot = DepotAgents(session)
        effectif = depot.lister_par_secteur(secteur) if secteur else depot.lister()
        qualifications = depot.competences()
        return [
            AgentConsulte.depuis(agent, qualifications.get(str(agent.identifiant), ()))
            for agent in effectif
        ]

    @application.get(
        "/taches",
        response_model=list[TacheConsultee],
        summary="Consulter les prestations de nettoyage a planifier",
        tags=["etablissement"],
    )
    def taches(
        session: SessionDeBase, secteur: str | None = Query(default=None)
    ) -> list[TacheConsultee]:
        """Restitue les taches en attente de planification."""
        depot = DepotTaches(session)
        attendues = depot.lister_a_planifier()
        if secteur:
            attendues = [t for t in attendues if str(t.secteur) == secteur]
        exigences = depot.exigences()
        return [
            TacheConsultee.depuis(tache, exigences.get(tache.identifiant, ()))
            for tache in attendues
        ]

    @application.get(
        "/incidents",
        response_model=list[IncidentConsulte],
        summary="Consulter les incidents ouverts",
        tags=["etablissement"],
    )
    def incidents(session: SessionDeBase) -> list[IncidentConsulte]:
        """Restitue les incidents non resolus, du plus grave au moins grave."""
        return [
            IncidentConsulte.depuis(incident)
            for incident in DepotIncidents(session).lister_ouverts()
        ]

    @application.post(
        "/affectations",
        response_model=RecommandationSortante,
        summary="Recommander une chambre a partir d'une situation transmise",
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
        """Etablit les options admissibles a partir du parc transmis."""
        situation = _vers_domaine(demande)
        return _vers_reponse(_raisonner(cas, situation, demande.temps_maximal))

    @application.post(
        "/affectations/{reference}",
        response_model=RecommandationSortante,
        summary="Recommander une chambre pour un sejour de l'etablissement",
        tags=["chambres"],
        responses={
            404: {"description": "Sejour absent ou etablissement non constitue"},
            500: {"description": "Defaillance du raisonnement"},
            503: {"description": "Base de connaissances indisponible"},
        },
    )
    def recommander_par_reference(
        reference: str,
        cas: CasUsage,
        session: SessionDeBase,
        parametres: DemandeParReference | None = None,
    ) -> RecommandationSortante:
        """Compose la situation depuis l'etat persiste puis raisonne.

        Le parc, les occupations concurrentes et les exigences du sejour sont
        etablis depuis la base: le client n'a rien a transmettre.
        """
        options = parametres or DemandeParReference()
        try:
            situation = composer_affectation(session, reference, options.poids)
        except SituationIncompleteError as erreur:
            raise _anomalie(
                "situation_incomplete", str(erreur), status.HTTP_404_NOT_FOUND
            ) from erreur
        return _vers_reponse(_raisonner(cas, situation, options.temps_maximal))

    @application.post(
        "/planifications",
        response_model=PlanificationSortante,
        summary="Planifier a partir d'un service transmis",
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
        """Etablit les paires admissibles puis ordonnance les taches transmises."""
        service = _vers_service(demande)
        return _vers_reponse_de_planification(
            _planifier(cas, service, demande.temps_maximal)
        )

    @application.post(
        "/planifications/service",
        response_model=PlanificationSortante,
        summary="Planifier le service d'etage de l'etablissement",
        tags=["housekeeping"],
        responses={
            404: {"description": "Aucune tache ou aucun agent sur le perimetre"},
            500: {"description": "Defaillance du raisonnement"},
            503: {"description": "Base de connaissances indisponible"},
        },
    )
    def planifier_le_service(
        cas: CasUsageHousekeeping,
        session: SessionDeBase,
        secteur: str | None = Query(default=None),
        parametres: DemandeParReference | None = None,
    ) -> PlanificationSortante:
        """Compose la journee de service depuis l'etat persiste puis ordonnance.

        Le perimetre peut etre restreint a un secteur: une gouvernante d'etage
        organise son propre service sans soumettre l'etablissement entier.
        """
        options = parametres or DemandeParReference()
        try:
            service = composer_planification(session, secteur, options.poids)
        except SituationIncompleteError as erreur:
            raise _anomalie(
                "situation_incomplete", str(erreur), status.HTTP_404_NOT_FOUND
            ) from erreur
        return _vers_reponse_de_planification(
            _planifier(cas, service, options.temps_maximal)
        )

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
        raise _anomalie(
            "demande_invalide", str(erreur), status.HTTP_422_UNPROCESSABLE_CONTENT
        ) from erreur


def _raisonner(
    cas: AffecterChambre, situation: Demande, temps_maximal: float | None
) -> Recommandation:
    """Execute le cycle de decision en signalant toute defaillance."""
    try:
        return cas.executer(situation, temps_maximal)
    except MoteurIndisponibleError as erreur:
        logger.exception("le moteur de regles n'a pu traiter la situation")
        raise _anomalie(
            "raisonnement_indisponible",
            str(erreur),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from erreur
    except GabaritIntrouvableError as erreur:
        logger.exception("un motif de raisonnement ne dispose d'aucune formulation")
        raise _anomalie(
            "justification_incomplete",
            str(erreur),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from erreur


def _vers_reponse(recommandation: Recommandation) -> RecommandationSortante:
    """Convertit une recommandation du domaine en reponse publique."""
    resultat = recommandation.resultat
    return RecommandationSortante(
        a_conclu=recommandation.a_conclu,
        chambre_proposee=recommandation.chambre_proposee,
        justification=recommandation.justification.en_texte(),
        chambres_examinees=recommandation.nombre_examinees,
        chambres_admissibles=sorted(resultat.admissibles),
        cout=resultat.cout,
        optimal=resultat.optimal,
        sous_reserve=recommandation.sous_reserve,
        contreparties=[
            ContrepartieSortante(
                code=penalite.motif, poids=penalite.poids, formulation=enonce.texte
            )
            for penalite, enonce in zip(
                resultat.penalites,
                recommandation.justification.contreparties,
                strict=True,
            )
        ],
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
        raise _anomalie(
            "demande_invalide", str(erreur), status.HTTP_422_UNPROCESSABLE_CONTENT
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
        raise _anomalie(
            "raisonnement_indisponible",
            str(erreur),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from erreur
    except OrdonnancementImpossibleError as erreur:
        logger.exception("le solveur d'ordonnancement n'a pu traiter le service")
        raise _anomalie(
            "ordonnancement_indisponible",
            str(erreur),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from erreur
    except GabaritIntrouvableError as erreur:
        logger.exception("un motif de raisonnement ne dispose d'aucune formulation")
        raise _anomalie(
            "justification_incomplete",
            str(erreur),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
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
