"""Schemas du simulateur du systeme de gestion.

Le simulateur tient le role que le logiciel de gestion hoteliere occuperait
dans une installation reelle: il modifie l'etat de l'etablissement, que le
systeme d'aide a la decision se borne a interroger.

La separation n'est pas de convenance. Un systeme d'aide qui modifierait
l'exploitation retirerait au responsable la decision qu'il pretend eclairer;
l'exposer sous un prefixe distinct maintient cette frontiere visible.
"""

from typing import Annotated

from pydantic import BaseModel, Field

from src.domaine import EtatOccupation, EtatProprete, EtatTechnique
from src.domaine.maintenance import Competence

Reference = Annotated[str, Field(min_length=1, max_length=32)]


class EtatDeChambreModifie(BaseModel):
    """Nouvel etat d'une chambre."""

    etat_proprete: EtatProprete | None = None
    etat_technique: EtatTechnique | None = None
    etat_occupation: EtatOccupation | None = None


class AgentAjoute(BaseModel):
    """Agent d'etage a inscrire."""

    identifiant: Reference = Field(examples=["A-0013"])
    secteur: Reference = Field(examples=["etage_3"])
    disponible: bool = True


class TechnicienAjoute(BaseModel):
    """Technicien de maintenance a inscrire."""

    identifiant: Reference = Field(examples=["T-0004"])
    competences: list[Competence] = Field(min_length=1)
    disponible: bool = True
    charge_en_cours: int = Field(default=0, ge=0)


class DisponibiliteModifiee(BaseModel):
    """Disponibilite d'un agent ou d'un technicien."""

    disponible: bool


class ModificationConfirmee(BaseModel):
    """Confirmation d'une modification de l'etat."""

    objet: str
    modification: str
    etat_courant: dict[str, str] = Field(default_factory=dict)
