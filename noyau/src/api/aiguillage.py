"""Aiguillage d'une demande interpretee vers son traitement.

L'aiguillage constitue la charniere du systeme: il etablit, a partir de
l'intention reconnue, quel traitement la demande appelle. Une consultation
interroge l'etat; un incident etablit ses consequences; un conflit appelle un
arbitrage.

Une lecture dont la recevabilite n'est pas acquise n'est jamais aiguillee. Elle
est restituee au responsable pour confirmation, conformement au principe qu'une
decision critique ne repose pas sur une inference non verifiee.
"""

import logging
from datetime import date

from sqlalchemy.orm import Session

from src.api.schemas_incident import ConsequencesRestituees
from src.api.schemas_interpretation import LectureRestituee
from src.api.schemas_reponse import (
    ArbitrageRestitue,
    EtatRestitue,
    NatureDeLaReponse,
    PlanificationRestituee,
    PlanRestitue,
    RepartitionRestituee,
    ReponseRestituee,
    RisqueApprecie,
)
from src.domaine import Gravite, TypeIncident
from src.donnees import (
    DepotAgents,
    DepotInterventions,
    DepotTaches,
    DepotTechniciens,
)
from src.gouvernance.risque import MotifDAbstention, apprecier
from src.neuronal.inference import Interpretation
from src.neuronal.preferences_lues import chambre_concernee, relever_les_preferences
from src.neuronal.quantites_lues import relever_les_quantites
from src.neuronal.taxonomie import (
    INTENTIONS_DE_CONSULTATION,
    Intention,
    TypeDEntite,
)
from src.orchestration import (
    RepartirUneCharge,
    RepartitionImpossibleError,
    SignalementDIncident,
    TraiterUnIncident,
    composer_planification,
)
from src.orchestration.arbitrage import ArbitrerUnConflit
from src.orchestration.composition import SituationIncompleteError
from src.orchestration.consultation import ConsultationImpossibleError, consulter
from src.orchestration.maintenance import AffecterLesInterventions

logger = logging.getLogger(__name__)

INCIDENTS: dict[str, TypeIncident] = {
    incident.value: incident for incident in TypeIncident
}

INCIDENTS_COMPOSITES: frozenset[str] = frozenset(
    {Intention.INCIDENT_AVEC_PREFERENCE.value}
)

TYPE_PAR_DEFAUT = TypeIncident.DEGAT_DES_EAUX

CONSEILS_PAR_DEFAUT = (
    "Decrivez la situation pour que je puisse vous aider. Par exemple: "
    "\"il y a une fuite dans la 312\", \"deux clients ont reserve la 405\", "
    "ou \"quelles chambres sont disponibles\"."
)


def aiguiller(
    session: Session,
    interpretation: Interpretation,
    traitement: TraiterUnIncident,
    arbitrage: ArbitrerUnConflit,
    jour: date,
    modele: str,
    temps_maximal: float | None = None,
) -> ReponseRestituee:
    """Etablit le traitement appele par une demande et le conduit.

    L'aiguillage n'engage aucun traitement lorsque la lecture demeure sous
    reserve: une entite inexistante ou une confiance insuffisante appellent une
    confirmation prealable, faute de quoi le raisonnement porterait sur une
    situation que le responsable n'a pas validee.
    """
    lecture = LectureRestituee.depuis(interpretation, modele)
    appreciation = apprecier(interpretation)
    risque = RisqueApprecie.depuis(appreciation)

    if appreciation.appelle_une_abstention:
        return ReponseRestituee(
            nature=(
                NatureDeLaReponse.HORS_PERIMETRE.value
                if appreciation.abstention == MotifDAbstention.HORS_DOMAINE.value
                else NatureDeLaReponse.CONFIRMATION_REQUISE.value
            ),
            lecture=lecture,
            risque=risque,
            message=" ".join(
                partie
                for partie in (*appreciation.motifs, appreciation.precision_attendue)
                if partie
            ),
        )

    intention = Intention(interpretation.intention)

    if intention in INTENTIONS_DE_CONSULTATION:
        return _consulter(session, interpretation, lecture, jour, risque)

    if intention is Intention.CONFLIT_AFFECTATION:
        return _arbitrer(
            session,
            interpretation,
            lecture,
            arbitrage,
            jour,
            temps_maximal,
            risque,
        )

    if intention.value in INCIDENTS_COMPOSITES:
        return _traiter_l_incident(
            session,
            interpretation,
            lecture,
            traitement,
            jour,
            temps_maximal,
            risque,
            TYPE_PAR_DEFAUT,
        )

    if intention.value in INCIDENTS:
        return _traiter_l_incident(
            session,
            interpretation,
            lecture,
            traitement,
            jour,
            temps_maximal,
            risque,
        )

    if intention is Intention.REPARTIR_CHARGE:
        return _repartir(interpretation, lecture, risque)

    if intention in {
        Intention.PRIORISER_INTERVENTIONS,
        Intention.AFFECTER_TECHNICIEN,
        Intention.CONSULTER_INTERVENTIONS,
    }:
        return _planifier_les_interventions(session, lecture, risque)

    if intention is Intention.DEMANDE_PLANIFICATION:
        return _planifier_le_service(session, interpretation, lecture, risque, jour)

    if intention in {
        Intention.CONSULTER_CHARGE,
        Intention.ESTIMER_FAISABILITE,
    }:
        return _estimer_la_charge(session, interpretation, lecture, risque)

    if intention is Intention.INCIDENT_AVEC_INTERVENTION:
        return _traiter_avec_intervention(
            session, interpretation, lecture, traitement, jour, temps_maximal, risque
        )

    if intention is Intention.ARBITRER_PRIORITES:
        return _planifier_les_interventions(session, lecture, risque)

    return ReponseRestituee(
        nature=NatureDeLaReponse.HORS_PERIMETRE.value,
        lecture=lecture,
        risque=risque,
        message=(
            f"La situation « {intention.value.replace('_', ' ')} » est reconnue "
            f"mais son traitement n'est pas encore disponible."
        ),
    )


def _consulter(
    session: Session,
    interpretation: Interpretation,
    lecture: LectureRestituee,
    jour: date,
    risque: RisqueApprecie,
) -> ReponseRestituee:
    """Conduit une consultation de l'etat."""
    try:
        reponse = consulter(session, interpretation, jour)
    except ConsultationImpossibleError as erreur:
        logger.info("consultation impossible: %s", erreur)
        return ReponseRestituee(
            nature=NatureDeLaReponse.HORS_PERIMETRE.value,
            lecture=lecture,
            risque=risque,
            message=str(erreur),
        )

    return ReponseRestituee(
        nature=NatureDeLaReponse.CONSULTATION.value,
        lecture=lecture,
        risque=risque,
        etat=EtatRestitue.depuis(reponse),
    )


def _arbitrer(
    session: Session,
    interpretation: Interpretation,
    lecture: LectureRestituee,
    arbitrage: ArbitrerUnConflit,
    jour: date,
    temps_maximal: float | None,
    risque: RisqueApprecie,
) -> ReponseRestituee:
    """Conduit l'arbitrage d'un conflit d'affectation."""
    chambre = interpretation.valeur_de(TypeDEntite.CHAMBRE.value)
    if chambre is None:
        return ReponseRestituee(
            nature=NatureDeLaReponse.HORS_PERIMETRE.value,
            lecture=lecture,
            risque=risque,
            message="Precisez la chambre sur laquelle porte le conflit.",
        )

    try:
        rendu = arbitrage.executer(session, chambre, jour, temps_maximal)
    except SituationIncompleteError as erreur:
        return ReponseRestituee(
            nature=NatureDeLaReponse.HORS_PERIMETRE.value,
            lecture=lecture,
            risque=risque,
            message=str(erreur),
        )

    return ReponseRestituee(
        nature=NatureDeLaReponse.ARBITRAGE.value,
        lecture=lecture,
        risque=risque,
        arbitrage=ArbitrageRestitue.depuis(rendu),
    )


def _traiter_l_incident(
    session: Session,
    interpretation: Interpretation,
    lecture: LectureRestituee,
    traitement: TraiterUnIncident,
    jour: date,
    temps_maximal: float | None,
    risque: RisqueApprecie,
    type_impose: TypeIncident | None = None,
) -> ReponseRestituee:
    """Etablit les consequences d'un incident signale.

    Une intention composite ne precise pas la nature de l'incident: elle
    signale qu'une chambre pose probleme et qu'une preference accompagne le
    relogement. La nature retenue par defaut immobilise la chambre, ce qui
    correspond a la conduite attendue lorsque le responsable demande un
    relogement.
    """
    chambre = chambre_concernee(interpretation)
    if chambre is None:
        return ReponseRestituee(
            nature=NatureDeLaReponse.HORS_PERIMETRE.value,
            lecture=lecture,
            risque=risque,
            message="Precisez la chambre concernee par l'incident.",
        )

    try:
        consequences = traitement.executer(
            session,
            SignalementDIncident(
                chambre=chambre,
                type_incident=type_impose
                or INCIDENTS[interpretation.intention],
                gravite=Gravite.MAJEURE,
                description=interpretation.enonce,
                jour=jour,
                preferences=relever_les_preferences(interpretation),
            ),
            temps_maximal,
        )
    except SituationIncompleteError as erreur:
        return ReponseRestituee(
            nature=NatureDeLaReponse.HORS_PERIMETRE.value,
            lecture=lecture,
            risque=risque,
            message=str(erreur),
        )

    return ReponseRestituee(
        nature=NatureDeLaReponse.CONSEQUENCES.value,
        lecture=lecture,
        risque=risque,
        consequences=ConsequencesRestituees.depuis(consequences),
    )


def _repartir(
    interpretation: Interpretation,
    lecture: LectureRestituee,
    risque: RisqueApprecie,
) -> ReponseRestituee:
    """Repartit une charge decrite dans l'enonce.

    Les quantites doivent etre qualifiees: une repartition fondee sur une
    lecture erronee des nombres produirait une conduite inexploitable, sans
    qu'aucun signal ne le revele.
    """
    lue = relever_les_quantites(interpretation)

    if not lue.est_exploitable:
        return ReponseRestituee(
            nature=NatureDeLaReponse.CONFIRMATION_REQUISE.value,
            lecture=lecture,
            risque=risque,
            message=f"Precisez {lue.manque}.",
        )

    try:
        proposee = RepartirUneCharge().executer(lue.charge or 0, lue.effectif or 0)
    except RepartitionImpossibleError as erreur:
        return ReponseRestituee(
            nature=NatureDeLaReponse.HORS_PERIMETRE.value,
            lecture=lecture,
            risque=risque,
            message=str(erreur),
        )

    return ReponseRestituee(
        nature=NatureDeLaReponse.REPARTITION.value,
        lecture=lecture,
        risque=risque,
        repartition=RepartitionRestituee.depuis(proposee),
    )


def _planifier_les_interventions(
    session: Session,
    lecture: LectureRestituee,
    risque: RisqueApprecie,
) -> ReponseRestituee:
    """Etablit le plan d'intervention de la maintenance."""
    interventions = list(DepotInterventions(session).lister())
    techniciens = list(DepotTechniciens(session).lister())

    plan = AffecterLesInterventions().executer(interventions, techniciens)

    return ReponseRestituee(
        nature=NatureDeLaReponse.PLAN_D_INTERVENTION.value,
        lecture=lecture,
        risque=risque,
        plan=PlanRestitue.depuis(plan),
    )


def _planifier_le_service(
    session: Session,
    interpretation: Interpretation,
    lecture: LectureRestituee,
    risque: RisqueApprecie,
    jour: date,
) -> ReponseRestituee:
    """Etablit le plan de nettoyage d'un secteur.

    En l'absence de secteur designe, la planification porte sur l'ensemble des
    secteurs comportant des taches: un responsable qui demande d'organiser le
    service sans preciser attend le service entier.
    """
    del jour

    secteur = interpretation.valeur_de(TypeDEntite.SECTEUR.value)
    if secteur is None:
        return ReponseRestituee(
            nature=NatureDeLaReponse.CONFIRMATION_REQUISE.value,
            lecture=lecture,
            risque=risque,
            message="Precisez le secteur a planifier.",
        )

    try:
        planification = composer_planification(session, secteur.replace(" ", "_"))
    except SituationIncompleteError as erreur:
        return ReponseRestituee(
            nature=NatureDeLaReponse.HORS_PERIMETRE.value,
            lecture=lecture,
            risque=risque,
            message=str(erreur),
        )

    return ReponseRestituee(
        nature=NatureDeLaReponse.PLANIFICATION.value,
        lecture=lecture,
        risque=risque,
        planification=PlanificationRestituee.depuis(planification),
    )


def _estimer_la_charge(
    session: Session,
    interpretation: Interpretation,
    lecture: LectureRestituee,
    risque: RisqueApprecie,
) -> ReponseRestituee:
    """Etablit la charge de travail restante et sa duree.

    L'estimation repose sur les taches enregistrees et l'effectif disponible:
    elle restitue un etat, non une proposition, et n'appelle donc aucune
    validation.
    """
    secteur = interpretation.valeur_de(TypeDEntite.SECTEUR.value)

    taches = (
        list(DepotTaches(session).lister_par_secteur(secteur.replace(" ", "_")))
        if secteur
        else list(DepotTaches(session).lister_a_planifier())
    )
    agents = [
        agent
        for agent in DepotAgents(session).lister()
        if not secteur or str(agent.secteur).replace("_", " ") == secteur
    ]

    if not taches:
        precision = f" sur {secteur}" if secteur else ""
        return ReponseRestituee(
            nature=NatureDeLaReponse.CONSULTATION.value,
            lecture=lecture,
            risque=risque,
            etat=EtatRestitue(
                enonce=f"Aucune tache n'est en attente{precision}.",
                elements=[],
                nombre=0,
            ),
        )

    if not agents:
        return ReponseRestituee(
            nature=NatureDeLaReponse.CONSULTATION.value,
            lecture=lecture,
            risque=risque,
            etat=EtatRestitue(
                enonce=(
                    f"{len(taches)} taches demeurent, mais aucun agent n'est "
                    f"affectable: la duree ne peut etre etablie."
                ),
                elements=[],
                nombre=len(taches),
            ),
        )

    try:
        proposee = RepartirUneCharge().executer(len(taches), len(agents))
    except RepartitionImpossibleError as erreur:
        return ReponseRestituee(
            nature=NatureDeLaReponse.HORS_PERIMETRE.value,
            lecture=lecture,
            risque=risque,
            message=str(erreur),
        )

    return ReponseRestituee(
        nature=NatureDeLaReponse.REPARTITION.value,
        lecture=lecture,
        risque=risque,
        repartition=RepartitionRestituee.depuis(proposee),
    )


def _traiter_avec_intervention(
    session: Session,
    interpretation: Interpretation,
    lecture: LectureRestituee,
    traitement: TraiterUnIncident,
    jour: date,
    temps_maximal: float | None,
    risque: RisqueApprecie,
) -> ReponseRestituee:
    """Etablit les consequences d'un incident et l'intervention qu'il appelle.

    Les deux services repondent a la meme situation sans se confondre: le
    service des chambres reloge les clients, celui de la maintenance repare.
    Restituer les deux ensemble evite au responsable de soumettre deux fois la
    meme situation.
    """
    reponse = _traiter_l_incident(
        session,
        interpretation,
        lecture,
        traitement,
        jour,
        temps_maximal,
        risque,
        TypeIncident.DEGAT_DES_EAUX,
    )

    if reponse.consequences is None:
        return reponse

    plan = AffecterLesInterventions().executer(
        list(DepotInterventions(session).lister()),
        list(DepotTechniciens(session).lister()),
    )

    return ReponseRestituee(
        nature=reponse.nature,
        lecture=lecture,
        risque=risque,
        consequences=reponse.consequences,
        plan=PlanRestitue.depuis(plan),
    )
