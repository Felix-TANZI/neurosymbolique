"""Schemas d'echange de la couche d'interpretation.

Les schemas exposent la lecture d'un enonce et sa recevabilite. Ils
distinguent ce que le modele a propose de ce que la verification symbolique a
etabli: une entite plausible mais sans correspondance reelle est restituee
comme telle, a charge pour l'interface de la soumettre a confirmation.
"""

from typing import Annotated

from pydantic import BaseModel, Field

from src.neuronal.inference import Interpretation


class EnonceSoumis(BaseModel):
    """Enonce libre soumis a interpretation."""

    enonce: Annotated[str, Field(min_length=1, max_length=512)] = Field(
        examples=["il y a une fuite dans la 407"],
        description="Formulation libre d'une situation operationnelle",
    )
    confiance_minimale: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Seuil en deca duquel une lecture est soumise a confirmation. "
            "Le seuil configure s'applique a defaut."
        ),
    )


class EntiteLue(BaseModel):
    """Element reconnu dans l'enonce."""

    type_d_entite: str = Field(examples=["chambre"])
    valeur: str = Field(examples=["407"])
    confiance: float
    existe: bool | None = Field(
        description=(
            "Correspondance etablie avec l'etat de l'etablissement. "
            "Nul lorsque le type ne designe aucune reference verifiable."
        )
    )


class ReserveExprimee(BaseModel):
    """Motif pour lequel une lecture appelle une confirmation."""

    motif: str = Field(examples=["entite_inexistante"])
    detail: str = Field(default="")


class LectureRestituee(BaseModel):
    """Lecture d'un enonce, soumise a confirmation ou directement exploitable.

    Aucune lecture n'entraine d'action: elle etablit ce que l'enonce exprime,
    a charge pour un responsable de confirmer avant que le raisonnement ne
    s'engage.
    """

    enonce: str
    intention: str
    confiance: float
    entites: list[EntiteLue]
    reserves: list[ReserveExprimee]
    recevabilite: str = Field(
        examples=["recevable"],
        description=(
            "recevable: la lecture peut etre soumise au raisonnement. "
            "a_confirmer: une confirmation est requise. "
            "irrecevable: l'enonce ne peut etre interprete."
        ),
    )
    modele: str = Field(description="Modele ayant produit la lecture")

    @classmethod
    def depuis(
        cls, interpretation: Interpretation, modele: str
    ) -> "LectureRestituee":
        return cls(
            enonce=interpretation.enonce,
            intention=interpretation.intention,
            confiance=round(interpretation.confiance_d_intention, 4),
            entites=[
                EntiteLue(
                    type_d_entite=entite.type_d_entite,
                    valeur=entite.valeur,
                    confiance=round(entite.confiance, 4),
                    existe=entite.existe,
                )
                for entite in interpretation.entites
            ],
            reserves=[
                ReserveExprimee(motif=reserve.motif, detail=reserve.detail)
                for reserve in interpretation.reserves
            ],
            recevabilite=interpretation.recevabilite,
            modele=modele,
        )
