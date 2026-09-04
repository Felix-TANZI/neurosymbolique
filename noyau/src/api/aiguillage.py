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
    ReponseRestituee,
)
from src.domaine import Gravite, TypeIncident
from src.neuronal.inference import Interpretation
from src.neuronal.taxonomie import (
    INTENTIONS_DE_CONSULTATION,
    Intention,
    TypeDEntite,
)
from src.orchestration import SignalementDIncident, TraiterUnIncident
from src.orchestration.arbitrage import ArbitrerUnConflit
from src.orchestration.composition import SituationIncompleteError
from src.orchestration.consultation import ConsultationImpossibleError, consulter

logger = logging.getLogger(__name__)

INCIDENTS: dict[str, TypeIncident] = {
    incident.value: incident for incident in TypeIncident
}

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

    if not interpretation.intention:
        return ReponseRestituee(
            nature=NatureDeLaReponse.HORS_PERIMETRE.value,
            lecture=lecture,
            message="Cet enonce ne releve d'aucune situation que je traite.",
        )

    intention = Intention(interpretation.intention)

    if intention is Intention.DEMANDE_CONSEIL:
        return ReponseRestituee(
            nature=NatureDeLaReponse.HORS_PERIMETRE.value,
            lecture=lecture,
            message=CONSEILS_PAR_DEFAUT,
        )

    if intention in INTENTIONS_DE_CONSULTATION:
        return _consulter(session, interpretation, lecture, jour)

    if not interpretation.est_recevable:
        return ReponseRestituee(
            nature=NatureDeLaReponse.CONFIRMATION_REQUISE.value,
            lecture=lecture,
            message=(
                "Confirmez cette lecture avant que le raisonnement ne "
                "s'engage."
            ),
        )

    if intention is Intention.CONFLIT_AFFECTATION:
        return _arbitrer(
            session, interpretation, lecture, arbitrage, jour, temps_maximal
        )

    if intention.value in INCIDENTS:
        return _traiter_l_incident(
            session, interpretation, lecture, traitement, jour, temps_maximal
        )

    return ReponseRestituee(
        nature=NatureDeLaReponse.HORS_PERIMETRE.value,
        lecture=lecture,
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
) -> ReponseRestituee:
    """Conduit une consultation de l'etat."""
    try:
        reponse = consulter(session, interpretation, jour)
    except ConsultationImpossibleError as erreur:
        logger.info("consultation impossible: %s", erreur)
        return ReponseRestituee(
            nature=NatureDeLaReponse.HORS_PERIMETRE.value,
            lecture=lecture,
            message=str(erreur),
        )

    return ReponseRestituee(
        nature=NatureDeLaReponse.CONSULTATION.value,
        lecture=lecture,
        etat=EtatRestitue.depuis(reponse),
    )


def _arbitrer(
    session: Session,
    interpretation: Interpretation,
    lecture: LectureRestituee,
    arbitrage: ArbitrerUnConflit,
    jour: date,
    temps_maximal: float | None,
) -> ReponseRestituee:
    """Conduit l'arbitrage d'un conflit d'affectation."""
    chambre = interpretation.valeur_de(TypeDEntite.CHAMBRE.value)
    if chambre is None:
        return ReponseRestituee(
            nature=NatureDeLaReponse.HORS_PERIMETRE.value,
            lecture=lecture,
            message="Precisez la chambre sur laquelle porte le conflit.",
        )

    try:
        rendu = arbitrage.executer(session, chambre, jour, temps_maximal)
    except SituationIncompleteError as erreur:
        return ReponseRestituee(
            nature=NatureDeLaReponse.HORS_PERIMETRE.value,
            lecture=lecture,
            message=str(erreur),
        )

    return ReponseRestituee(
        nature=NatureDeLaReponse.ARBITRAGE.value,
        lecture=lecture,
        arbitrage=ArbitrageRestitue.depuis(rendu),
    )


def _traiter_l_incident(
    session: Session,
    interpretation: Interpretation,
    lecture: LectureRestituee,
    traitement: TraiterUnIncident,
    jour: date,
    temps_maximal: float | None,
) -> ReponseRestituee:
    """Etablit les consequences d'un incident signale."""
    chambre = interpretation.valeur_de(TypeDEntite.CHAMBRE.value)
    if chambre is None:
        return ReponseRestituee(
            nature=NatureDeLaReponse.HORS_PERIMETRE.value,
            lecture=lecture,
            message="Precisez la chambre concernee par l'incident.",
        )

    try:
        consequences = traitement.executer(
            session,
            SignalementDIncident(
                chambre=chambre,
                type_incident=INCIDENTS[interpretation.intention],
                gravite=Gravite.MAJEURE,
                description=interpretation.enonce,
                jour=jour,
            ),
            temps_maximal,
        )
    except SituationIncompleteError as erreur:
        return ReponseRestituee(
            nature=NatureDeLaReponse.HORS_PERIMETRE.value,
            lecture=lecture,
            message=str(erreur),
        )

    return ReponseRestituee(
        nature=NatureDeLaReponse.CONSEQUENCES.value,
        lecture=lecture,
        consequences=ConsequencesRestituees.depuis(consequences),
    )
