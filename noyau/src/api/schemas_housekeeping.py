"""Schemas d'echange du service housekeeping.

Comme pour le service de gestion des chambres, les schemas constituent le
contrat public du systeme, distinct de la modelisation interne.
"""

from datetime import time
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from src.domaine import (
    AgentEtage,
    DisponibiliteAgent,
    IdentifiantAgent,
    NumeroChambre,
    PlageDeService,
    PrioriteTache,
    Secteur,
    StatutTache,
    TacheNettoyage,
    TypePrestation,
)

Reference = Annotated[str, Field(min_length=1, max_length=64, examples=["T-001"])]
NomSecteur = Annotated[str, Field(min_length=1, max_length=64, examples=["etage_4"])]


class AgentEntrant(BaseModel):
    """Agent d'etage soumis a la planification."""

    identifiant: Reference = Field(examples=["A-001"])
    secteur: NomSecteur
    debut_service: time = Field(default=time(8, 0))
    fin_service: time = Field(default=time(16, 0))
    disponibilite: DisponibiliteAgent = Field(default=DisponibiliteAgent.PRESENT)
    minutes_deja_affectees: int = Field(default=0, ge=0, le=1440)
    competences: list[str] = Field(
        default_factory=list,
        description="Qualifications detenues, confrontees aux exigences des taches",
    )

    @model_validator(mode="after")
    def _verifier_plage(self) -> "AgentEntrant":
        if self.fin_service <= self.debut_service:
            raise ValueError("la fin de service doit suivre le debut de service")
        return self

    def vers_domaine(self) -> AgentEtage:
        return AgentEtage(
            identifiant=IdentifiantAgent(self.identifiant),
            secteur=Secteur(self.secteur),
            plage=PlageDeService(debut=self.debut_service, fin=self.fin_service),
            disponibilite=self.disponibilite,
            minutes_deja_affectees=self.minutes_deja_affectees,
        )


class TacheEntrante(BaseModel):
    """Tache de nettoyage soumise a la planification."""

    identifiant: Reference
    chambre: Annotated[str, Field(min_length=1, max_length=16, examples=["407"])]
    prestation: TypePrestation = Field(examples=[TypePrestation.DEPART])
    secteur: NomSecteur
    echeance: time | None = Field(
        default=None,
        description="Heure avant laquelle la chambre doit etre prete",
    )
    priorite: PrioriteTache = Field(default=PrioriteTache.NORMALE)
    duree_minutes: int = Field(
        default=0,
        ge=0,
        le=480,
        description="Duree observee, celle de la prestation a defaut",
    )
    competences_requises: list[str] = Field(default_factory=list)

    def vers_domaine(self) -> TacheNettoyage:
        return TacheNettoyage(
            identifiant=self.identifiant,
            chambre=NumeroChambre(self.chambre),
            prestation=self.prestation,
            secteur=Secteur(self.secteur),
            echeance=self.echeance,
            priorite=self.priorite,
            statut=StatutTache.A_PLANIFIER,
            duree_minutes=self.duree_minutes,
        )


class DemandePlanificationEntrante(BaseModel):
    """Journee de service soumise a la planification."""

    agents: list[AgentEntrant] = Field(min_length=1)
    taches: list[TacheEntrante] = Field(min_length=1)
    secteurs_reserves: list[NomSecteur] = Field(
        default_factory=list,
        description="Secteurs dont l'acces est restreint aux agents habilites",
    )
    poids: dict[str, int] | None = Field(
        default=None,
        description=(
            "Ponderation des preferences. Une ponderation ne peut rendre "
            "admissible une paire qu'une contrainte dure ecarte."
        ),
    )
    temps_maximal: float | None = Field(default=None, gt=0, le=60)


class AffectationSortante(BaseModel):
    """Tache confiee a un agent sur un creneau determine."""

    tache: str
    agent: str
    debut: str = Field(examples=["08h00"])
    fin: str = Field(examples=["08h40"])
    duree_minutes: int


class TacheEnAttenteSortante(BaseModel):
    """Tache demeurant sans affectation, accompagnee de sa cause."""

    tache: str
    cause: str = Field(
        examples=["aucun_agent_admissible"],
        description=(
            "aucun_agent_admissible impose de mobiliser une competence ; "
            "capacite_insuffisante impose de degager du temps."
        ),
    )
    motifs: list[str]


class ChargeSortante(BaseModel):
    """Volume de travail affecte a un agent."""

    agent: str
    minutes: int


class PlanificationSortante(BaseModel):
    """Issue d'un cycle de planification, soumise a validation humaine.

    Aucun planning n'est applique par le systeme: la validation par un
    responsable demeure requise.
    """

    est_complete: bool
    justification: list[str]
    affectations: list[AffectationSortante]
    taches_en_attente: list[TacheEnAttenteSortante]
    charges: list[ChargeSortante]
    cout: int
    optimal: bool
    sous_reserve: bool = Field(
        description="Le planning est conforme mais non garanti optimal"
    )
