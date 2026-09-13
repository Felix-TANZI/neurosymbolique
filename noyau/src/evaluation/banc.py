"""Execution des trois approches sur un meme scenario.

Chaque approche est conduite jusqu'a son terme, avec les seuls moyens dont elle
dispose. L'approche neuronale interprete et agit sur sa lecture sans la
verifier. L'approche symbolique n'accepte qu'une situation deja formalisee et
demeure impuissante devant un enonce libre. La composition interprete, verifie,
puis raisonne.

Les deux premieres ne sont pas des epouvantails: elles representent ce qu'on
obtiendrait en retenant l'une des deux couches, ce qui constitue precisement
l'alternative que la composition pretend depasser.
"""

import logging
import time
from datetime import date

from sqlalchemy.orm import Session

from src.domaine import Gravite, TypeIncident
from src.donnees import DepotAgents, DepotChambres, DepotReservations
from src.gouvernance.risque import MotifDAbstention, apprecier
from src.neuronal.inference import (
    Interpretation,
    ReferentielConnu,
    referentiel_depuis,
    verifier_les_entites,
)
from src.neuronal.inference_preentrainee import InterpretePreentraineDEnonces
from src.neuronal.preferences_lues import chambre_concernee, relever_les_preferences
from src.neuronal.taxonomie import INTENTIONS_DE_CONSULTATION, Intention, TypeDEntite
from src.orchestration import SignalementDIncident, TraiterUnIncident
from src.orchestration.arbitrage import ArbitrerUnConflit, NatureDuConflit
from src.orchestration.composition import SituationIncompleteError
from src.orchestration.consultation import ConsultationImpossibleError, consulter

from .approches import Approche, Conduite
from .scenarios import ConduiteAttendue, Scenario

logger = logging.getLogger(__name__)

INCIDENTS: dict[str, TypeIncident] = {
    incident.value: incident for incident in TypeIncident
}
COMPOSITES = {"incident_avec_preference", "changement_avec_preference"}


class BancDEvaluation:
    """Conduit les trois approches sur un meme jeu de scenarios."""

    def __init__(
        self,
        interprete: InterpretePreentraineDEnonces,
        traitement: TraiterUnIncident,
        arbitrage: ArbitrerUnConflit,
    ) -> None:
        self._interprete = interprete
        self._traitement = traitement
        self._arbitrage = arbitrage

    def conduire(
        self, session: Session, scenario: Scenario, jour: date, approche: str
    ) -> Conduite:
        """Conduit une approche sur un scenario et restitue ce qu'elle etablit."""
        debut = time.perf_counter()
        try:
            if approche == Approche.NEURONALE.value:
                conduite = self._neuronale(scenario)
            elif approche == Approche.SYMBOLIQUE.value:
                conduite = self._symbolique(session, scenario, jour)
            else:
                conduite = self._composee(session, scenario, jour)
        except Exception as erreur:  # noqa: BLE001
            logger.exception("defaillance sur %s", scenario.identifiant)
            return Conduite(
                approche=approche,
                scenario=scenario.identifiant,
                conduite="defaillance",
                duree_millisecondes=(time.perf_counter() - debut) * 1000,
                defaillance=str(erreur),
            )

        return Conduite(
            approche=approche,
            scenario=scenario.identifiant,
            conduite=conduite.conduite,
            intention=conduite.intention,
            entites=conduite.entites,
            chambres_proposees=conduite.chambres_proposees,
            confiance=conduite.confiance,
            duree_millisecondes=(time.perf_counter() - debut) * 1000,
        )

    def _neuronale(self, scenario: Scenario) -> Conduite:
        """Interprete l'enonce et agit sur cette seule lecture.

        Aucune verification n'intervient: une reference inexistante est
        employee comme si elle designait quelque chose, et aucune contrainte
        d'exploitation n'est opposee a la conclusion.
        """
        lecture = self._interprete.interpreter(scenario.enonce)
        entites = {
            entite.type_d_entite: entite.valeur for entite in lecture.entites
        }

        if not lecture.intention:
            conduite = ConduiteAttendue.REFUSER_HORS_PERIMETRE.value
        elif Intention(lecture.intention) in INTENTIONS_DE_CONSULTATION:
            conduite = ConduiteAttendue.REPONDRE.value
        else:
            conduite = ConduiteAttendue.PROPOSER.value

        return Conduite(
            approche=Approche.NEURONALE.value,
            scenario=scenario.identifiant,
            conduite=conduite,
            intention=lecture.intention,
            entites=entites,
            confiance=lecture.confiance_d_intention,
        )

    def _symbolique(
        self, session: Session, scenario: Scenario, jour: date
    ) -> Conduite:
        """Raisonne sur la seule situation formalisee.

        Aucune interpretation n'intervient: l'approche ne dispose que de ce
        qu'un formulaire lui aurait transmis. Un enonce libre demeure
        inexploitable, quelle que soit la clarte de sa formulation.
        """
        del session, jour
        return Conduite(
            approche=Approche.SYMBOLIQUE.value,
            scenario=scenario.identifiant,
            conduite=ConduiteAttendue.DEMANDER_CONFIRMATION.value,
        )

    def _composee(
        self, session: Session, scenario: Scenario, jour: date
    ) -> Conduite:
        """Interprete, verifie, puis raisonne."""
        lecture = verifier_les_entites(
            self._interprete.interpreter(scenario.enonce),
            _referentiel(session),
        )
        entites = {
            entite.type_d_entite: entite.valeur for entite in lecture.entites
        }

        conduite = self._conduire_sur(session, lecture, jour)

        return Conduite(
            approche=Approche.COMPOSEE.value,
            scenario=scenario.identifiant,
            conduite=conduite[0],
            intention=lecture.intention,
            entites=entites,
            chambres_proposees=conduite[1],
            confiance=lecture.confiance_d_intention,
        )

    def _conduire_sur(
        self, session: Session, lecture: Interpretation, jour: date
    ) -> tuple[str, tuple[str, ...]]:
        """Etablit la conduite appelee par une lecture verifiee.

        L'appreciation du risque precede tout traitement: une lecture dont le
        systeme ne peut repondre n'engage aucun raisonnement, et le motif de
        l'abstention determine la conduite restituee.
        """
        appreciation = apprecier(lecture)

        if appreciation.appelle_une_abstention:
            if appreciation.abstention == MotifDAbstention.HORS_DOMAINE.value:
                return ConduiteAttendue.REFUSER_HORS_PERIMETRE.value, ()
            if (
                appreciation.abstention
                == MotifDAbstention.REFERENCE_INEXISTANTE.value
            ):
                return ConduiteAttendue.SIGNALER_INEXISTANT.value, ()
            return ConduiteAttendue.DEMANDER_CONFIRMATION.value, ()

        intention = Intention(lecture.intention)

        if intention in INTENTIONS_DE_CONSULTATION:
            try:
                consulter(session, lecture, jour)
            except ConsultationImpossibleError:
                return ConduiteAttendue.SIGNALER_INEXISTANT.value, ()
            return ConduiteAttendue.REPONDRE.value, ()

        if intention is Intention.CONFLIT_AFFECTATION:
            return self._arbitrer(session, lecture, jour)

        if lecture.intention in INCIDENTS or lecture.intention in COMPOSITES:
            return self._traiter(session, lecture, jour)

        return ConduiteAttendue.REFUSER_HORS_PERIMETRE.value, ()

    def _arbitrer(
        self, session: Session, lecture: Interpretation, jour: date
    ) -> tuple[str, tuple[str, ...]]:
        """Conduit l'arbitrage et restitue ce qu'il etablit."""
        chambre = lecture.valeur_de(TypeDEntite.CHAMBRE.value)
        if chambre is None:
            return ConduiteAttendue.DEMANDER_CONFIRMATION.value, ()

        try:
            rendu = self._arbitrage.executer(session, chambre, jour, 15.0)
        except SituationIncompleteError:
            return ConduiteAttendue.SIGNALER_INEXISTANT.value, ()

        if rendu.nature == NatureDuConflit.ABSENT.value:
            return ConduiteAttendue.CONSTATER_ABSENCE_DE_CONFLIT.value, ()

        proposee = rendu.chambre_proposee
        return ConduiteAttendue.PROPOSER.value, (proposee,) if proposee else ()

    def _traiter(
        self, session: Session, lecture: Interpretation, jour: date
    ) -> tuple[str, tuple[str, ...]]:
        """Conduit le traitement d'incident et restitue les chambres proposees."""
        chambre = chambre_concernee(lecture)
        if chambre is None:
            return ConduiteAttendue.DEMANDER_CONFIRMATION.value, ()

        try:
            consequences = self._traitement.executer(
                session,
                SignalementDIncident(
                    chambre=chambre,
                    type_incident=INCIDENTS.get(
                        lecture.intention, TypeIncident.DEGAT_DES_EAUX
                    ),
                    gravite=Gravite.MAJEURE,
                    description=lecture.enonce,
                    jour=jour,
                    preferences=relever_les_preferences(lecture),
                ),
                15.0,
            )
        except SituationIncompleteError:
            return ConduiteAttendue.SIGNALER_INEXISTANT.value, ()

        proposees = tuple(
            relogement.chambre_proposee
            for relogement in consequences.sejours_a_reloger
            if relogement.chambre_proposee is not None
        )
        return ConduiteAttendue.PROPOSER.value, proposees


def _referentiel(session: Session) -> ReferentielConnu:
    """Constitue le referentiel des references de l'etablissement."""
    from datetime import timedelta

    from src.domaine import Periode

    depot = DepotChambres(session)
    parc = depot.lister()
    aujourd_hui = date(2026, 1, 1)

    return referentiel_depuis(
        chambres=[str(chambre.numero) for chambre in parc],
        reservations=[
            str(sejour.identifiant)
            for sejour in DepotReservations(session).lister_sur_periode(
                Periode(aujourd_hui, aujourd_hui + timedelta(days=365))
            )
        ],
        agents=[str(agent.identifiant) for agent in DepotAgents(session).lister()],
        secteurs=sorted(
            {depot.secteur_de(chambre.numero).replace("_", " ") for chambre in parc}
        ),
    )
