"""Schemas d'echange du journal des decisions.

Le journal expose ce qui a ete demande, propose et decide. Il ne restitue aucun
etat de l'etablissement: une decision consignee etablit qu'une proposition a
recu une suite, non que l'exploitation en a ete modifiee.
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from src.orchestration.journal import EntreeDuJournal, SuiteDonnee

Texte = Annotated[str, Field(min_length=1, max_length=2048)]


class DecisionSoumise(BaseModel):
    """Suite donnee par un responsable a une proposition."""

    service: Annotated[str, Field(min_length=1, max_length=64)] = Field(
        examples=["chambres"]
    )
    situation: Texte = Field(examples=["il y a une fuite dans la 319"])
    proposition: Texte = Field(examples=["c406 pour R-00017"])
    justification: str = Field(default="", max_length=4096)
    issue: SuiteDonnee = Field(
        description=(
            "validee: la proposition est retenue. "
            "corrigee: une autre decision est prise. "
            "refusee: la proposition est ecartee. "
            "differee: la decision est reportee."
        )
    )
    valideur: str = Field(default="", max_length=128)
    motif: str = Field(
        default="",
        max_length=1024,
        description=(
            "Decision effectivement retenue lors d'une correction, ou raison "
            "d'un refus. Le motif constitue le signal le plus utile du "
            "journal: il designe un ecart entre le raisonnement et le jugement."
        ),
    )


class DecisionConsultee(BaseModel):
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
    marque_un_ecart: bool = Field(
        description="Le responsable s'est ecarte de la proposition"
    )

    @classmethod
    def depuis(cls, entree: EntreeDuJournal) -> "DecisionConsultee":
        return cls(
            identifiant=entree.identifiant,
            horodatage=entree.horodatage,
            service=entree.service,
            situation=entree.situation,
            proposition=entree.proposition,
            justification=entree.justification,
            issue=entree.issue,
            motif=entree.motif,
            valideur=entree.valideur,
            marque_un_ecart=entree.marque_un_ecart,
        )
