"""Consignation des decisions soumises au responsable.

Le journal conserve ce qui a ete demande, ce que le systeme a compris, ce qu'il
a propose et ce que le responsable a decide. Il ne modifie pas l'etat de
l'etablissement: le systeme assiste une decision, il ne l'execute pas, et
l'exploitation demeure pilotee par ceux qui en repondent.

Le journal sert deux usages distincts. Il etablit la tracabilite d'une decision
critique, dont il doit etre possible de reconstituer le fondement a posteriori.
Il recueille par ailleurs les ecarts entre la proposition et la decision
retenue: un refus ou une correction signalent un desaccord entre le
raisonnement et le jugement du responsable, dont l'examen ulterieur peut
eclairer les regles ou le modele.

Les ecritures sont irreversibles. Un journal dont les entrees pourraient etre
modifiees ne fonderait aucune tracabilite.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum, unique

from sqlalchemy.orm import Session

from src.donnees import JournalDesDecisions

logger = logging.getLogger(__name__)


@unique
class SuiteDonnee(StrEnum):
    """Suite que le responsable donne a une proposition."""

    VALIDEE = "validee"
    CORRIGEE = "corrigee"
    REFUSEE = "refusee"
    DIFFEREE = "differee"


@dataclass(frozen=True, slots=True)
class DecisionAConsigner:
    """Decision prise par un responsable sur une proposition du systeme.

    L'enonce initial est conserve tel qu'il a ete formule: reconstituer une
    decision suppose de savoir ce qui a ete demande, et non seulement ce que le
    systeme en a compris.
    """

    service: str
    situation: str
    proposition: str
    justification: str
    issue: str
    valideur: str = ""
    motif: str = ""
    version_regles: str = ""

    def __post_init__(self) -> None:
        if self.issue not in {suite.value for suite in SuiteDonnee}:
            raise ValueError(f"issue inconnue: {self.issue}")
        if self.issue == SuiteDonnee.CORRIGEE.value and not self.motif:
            raise ValueError(
                "une correction doit preciser la decision effectivement retenue"
            )

    @property
    def marque_un_ecart(self) -> bool:
        """Indique que le responsable s'est ecarte de la proposition."""
        return self.issue in {
            SuiteDonnee.CORRIGEE.value,
            SuiteDonnee.REFUSEE.value,
        }


@dataclass(frozen=True, slots=True)
class EntreeDuJournal:
    """Decision consignee, restituee pour consultation."""

    identifiant: int
    horodatage: datetime
    service: str
    situation: str
    proposition: str
    justification: str
    issue: str
    motif: str
    valideur: str
    version_regles: str

    @property
    def marque_un_ecart(self) -> bool:
        return self.issue in {
            SuiteDonnee.CORRIGEE.value,
            SuiteDonnee.REFUSEE.value,
        }


class ConsignerUneDecision:
    """Inscrit au journal la suite donnee a une proposition."""

    def executer(self, session: Session, decision: DecisionAConsigner) -> None:
        """Consigne la decision sans rien modifier d'autre.

        L'entree est ajoutee: ni l'etat de l'etablissement ni les entrees
        precedentes ne sont affectes.
        """
        JournalDesDecisions(session).consigner(
            service=decision.service,
            situation=decision.situation,
            proposition=decision.proposition,
            justification=decision.justification,
            issue=decision.issue,
            valideur=decision.valideur,
            motif=decision.motif,
            version_regles=decision.version_regles,
        )
        logger.info(
            "decision consignee sur %s, issue %s%s",
            decision.service,
            decision.issue,
            " (ecart)" if decision.marque_un_ecart else "",
        )


class ConsulterLeJournal:
    """Restitue les decisions consignees."""

    def executer(
        self, session: Session, limite: int = 50, ecarts_seulement: bool = False
    ) -> tuple[EntreeDuJournal, ...]:
        """Restitue les decisions les plus recentes.

        Le filtrage sur les ecarts repond a l'usage d'analyse: les decisions
        conformes a la proposition n'apprennent rien, quand un refus ou une
        correction designent une situation ou le raisonnement a manque.
        """
        entrees = JournalDesDecisions(session).lister(limite)
        restituees = tuple(_convertir(entree) for entree in entrees)

        if ecarts_seulement:
            restituees = tuple(
                entree for entree in restituees if entree.marque_un_ecart
            )

        return restituees


def _convertir(enregistrement: object) -> EntreeDuJournal:
    """Constitue une entree a partir de son enregistrement."""
    return EntreeDuJournal(
        identifiant=int(getattr(enregistrement, "identifiant", 0)),
        horodatage=getattr(enregistrement, "horodatage", datetime.now()),
        service=str(getattr(enregistrement, "service", "")),
        situation=str(getattr(enregistrement, "situation", "")),
        proposition=str(getattr(enregistrement, "proposition", "")),
        justification=str(getattr(enregistrement, "justification", "")),
        issue=str(getattr(enregistrement, "issue", "")),
        motif=str(getattr(enregistrement, "motif", "")),
        valideur=str(getattr(enregistrement, "valideur", "")),
        version_regles=str(getattr(enregistrement, "version_regles", "")),
    )
