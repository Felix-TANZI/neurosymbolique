"""Schemas de restitution d'une demande interpretee.

La restitution distingue trois natures de reponse. Une consultation restitue un
etat. Un arbitrage restitue une proposition assortie de sa justification. Une
demande hors perimetre ou non interpretable restitue le motif de son rejet.

Cette distinction est exposee a l'interface afin qu'elle presente chaque nature
comme il convient: une reponse a une question n'appelle aucune validation, une
proposition de decision en appelle une.
"""

from enum import StrEnum, unique
from typing import Annotated

from pydantic import BaseModel, Field

from src.api.schemas_incident import ConsequencesRestituees
from src.api.schemas_interpretation import LectureRestituee
from src.orchestration.arbitrage import ArbitrageRendu
from src.orchestration.consultation import Reponse


@unique
class NatureDeLaReponse(StrEnum):
    """Nature de la reponse restituee."""

    CONSULTATION = "consultation"
    ARBITRAGE = "arbitrage"
    CONSEQUENCES = "consequences"
    CONFIRMATION_REQUISE = "confirmation_requise"
    HORS_PERIMETRE = "hors_perimetre"


class EtatRestitue(BaseModel):
    """Reponse a une consultation de l'etat de l'etablissement."""

    enonce: str = Field(examples=["19 chambres sont libres et pretes."])
    elements: list[str]
    nombre: int | None

    @classmethod
    def depuis(cls, reponse: Reponse) -> "EtatRestitue":
        return cls(
            enonce=reponse.enonce,
            elements=list(reponse.elements),
            nombre=reponse.nombre,
        )


class LevierRestitue(BaseModel):
    """Contrainte dont la levee ouvrirait une solution."""

    relachement: str
    enonce: str
    chambres_ainsi_ouvertes: int


class ArbitrageRestitue(BaseModel):
    """Conduite etablie face a un conflit d'affectation."""

    nature: str
    chambre: str
    sejour_maintenu: str | None
    sejour_a_reloger: str | None
    motif: str
    chambre_proposee: str | None
    justification: str
    constats: list[str]
    leviers: list[LevierRestitue]
    anomalie: bool
    demande_une_intervention: bool

    @classmethod
    def depuis(cls, rendu: ArbitrageRendu) -> "ArbitrageRestitue":
        return cls(
            nature=rendu.nature,
            chambre=rendu.chambre,
            sejour_maintenu=rendu.sejour_maintenu,
            sejour_a_reloger=rendu.sejour_a_reloger,
            motif=rendu.motif_de_l_arbitrage,
            chambre_proposee=rendu.chambre_proposee,
            justification=(
                rendu.recommandation.justification.decision.texte
                if rendu.recommandation is not None
                else ""
            ),
            constats=list(rendu.constats),
            leviers=[
                LevierRestitue(
                    relachement=levier.relachement,
                    enonce=levier.enonce,
                    chambres_ainsi_ouvertes=levier.chambres_ainsi_ouvertes,
                )
                for levier in rendu.leviers
            ],
            anomalie=rendu.anomalie,
            demande_une_intervention=rendu.demande_une_intervention,
        )


class DemandeSoumise(BaseModel):
    """Demande formulee en langue naturelle."""

    enonce: Annotated[str, Field(min_length=1, max_length=512)] = Field(
        examples=["quelles chambres sont hors service a l'etage 4"]
    )
    jour: str | None = Field(
        default=None, description="Jour de reference. Le jour courant a defaut."
    )
    temps_maximal: float | None = Field(default=None, gt=0, le=60)


class ReponseRestituee(BaseModel):
    """Reponse complete a une demande interpretee.

    La lecture est toujours restituee: elle expose ce que le systeme a compris,
    ce qui permet au responsable de constater une interpretation erronee avant
    d'en tirer les consequences.
    """

    nature: str = Field(
        description=(
            "consultation: un etat est restitue. "
            "arbitrage: une proposition de decision est soumise. "
            "consequences: les effets d'un incident sont etablis. "
            "confirmation_requise: la lecture doit etre confirmee. "
            "hors_perimetre: la demande ne peut etre traitee."
        )
    )
    lecture: LectureRestituee
    etat: EtatRestitue | None = None
    arbitrage: ArbitrageRestitue | None = None
    consequences: ConsequencesRestituees | None = None
    message: str = Field(
        default="",
        description="Conduite proposee lorsqu'aucun traitement n'est engage.",
    )
