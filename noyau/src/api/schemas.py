"""Schemas d'echange de l'interface de programmation.

Les schemas constituent le contrat public du systeme, distinct de la
modelisation interne. Cette separation permet de faire evoluer le domaine sans
rompre les clients, et de substituer l'interface sans modifier le noyau.
"""

from datetime import date, time
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from src.domaine import (
    Categorie,
    Chambre,
    Client,
    Equipement,
    EtatOccupation,
    EtatProprete,
    EtatTechnique,
    Exigence,
    HeureArrivee,
    IdentifiantReservation,
    NumeroChambre,
    Periode,
    Reservation,
    StatutFidelite,
)

Numero = Annotated[str, Field(min_length=1, max_length=16, examples=["407"])]
Identifiant = Annotated[str, Field(min_length=1, max_length=64, examples=["R-4471"])]


class ExigenceEntrante(BaseModel):
    """Besoin exprime par une reservation."""

    equipement: Equipement = Field(description="Equipement attendu dans la chambre")
    obligatoire: bool = Field(
        default=False,
        description=(
            "Une exigence obligatoire ecarte toute chambre qui ne la satisfait "
            "pas. Une exigence souhaitee degrade seulement la qualite du choix."
        ),
    )

    def vers_domaine(self) -> Exigence:
        return Exigence(equipement=self.equipement, obligatoire=self.obligatoire)


class ChambreEntrante(BaseModel):
    """Chambre du parc soumise au raisonnement."""

    numero: Numero
    etage: int = Field(ge=0, le=60, examples=[4])
    capacite: int = Field(ge=1, le=12, examples=[2])
    categorie: Categorie = Field(examples=[Categorie.STANDARD])
    equipements: list[Equipement] = Field(default_factory=list)
    etat_proprete: EtatProprete = Field(default=EtatProprete.PRETE)
    etat_technique: EtatTechnique = Field(default=EtatTechnique.OPERATIONNELLE)
    etat_occupation: EtatOccupation = Field(default=EtatOccupation.LIBRE)
    chambres_communicantes: list[Numero] = Field(default_factory=list)

    def vers_domaine(self) -> Chambre:
        return Chambre(
            numero=NumeroChambre(self.numero),
            etage=self.etage,
            capacite=self.capacite,
            categorie=self.categorie,
            equipements=frozenset(self.equipements),
            etat_proprete=self.etat_proprete,
            etat_technique=self.etat_technique,
            etat_occupation=self.etat_occupation,
            chambres_communicantes=frozenset(
                NumeroChambre(numero) for numero in self.chambres_communicantes
            ),
        )


class ReservationEntrante(BaseModel):
    """Sejour dont l'affectation est demandee ou deja etablie."""

    identifiant: Identifiant
    client: Identifiant = Field(examples=["C-001"])
    statut_fidelite: StatutFidelite = Field(default=StatutFidelite.AUCUN)
    arrivee: date = Field(examples=["2026-08-12"])
    depart: date = Field(examples=["2026-08-15"])
    nombre_personnes: int = Field(ge=1, le=12, examples=[2])
    categorie_contractee: Categorie = Field(examples=[Categorie.STANDARD])
    heure_arrivee_prevue: time = Field(default=time(16, 0))
    heure_acces_contractuelle: time = Field(default=time(15, 0))
    exigences: list[ExigenceEntrante] = Field(default_factory=list)
    chambre_affectee: Numero | None = Field(
        default=None,
        description="Chambre deja occupee par ce sejour, le cas echeant",
    )

    @model_validator(mode="after")
    def _verifier_periode(self) -> "ReservationEntrante":
        if self.depart <= self.arrivee:
            raise ValueError("la date de depart doit suivre la date d'arrivee")
        return self

    def vers_domaine(self) -> Reservation:
        return Reservation(
            identifiant=IdentifiantReservation(self.identifiant),
            client=Client(self.client, statut_fidelite=self.statut_fidelite),
            periode=Periode(arrivee=self.arrivee, depart=self.depart),
            nombre_personnes=self.nombre_personnes,
            categorie_contractee=self.categorie_contractee,
            heure_arrivee=HeureArrivee(
                prevue=self.heure_arrivee_prevue,
                contractuelle=self.heure_acces_contractuelle,
            ),
            exigences=frozenset(exigence.vers_domaine() for exigence in self.exigences),
            chambre_affectee=(
                NumeroChambre(self.chambre_affectee)
                if self.chambre_affectee is not None
                else None
            ),
        )


class DemandeAffectation(BaseModel):
    """Situation operationnelle soumise pour affectation."""

    parc: list[ChambreEntrante] = Field(min_length=1)
    reservation: ReservationEntrante
    occupations: list[ReservationEntrante] = Field(
        default_factory=list,
        description="Sejours deja etablis, pris en compte pour les conflits",
    )
    poids: dict[str, int] | None = Field(
        default=None,
        description=(
            "Ponderation des preferences souples. Une ponderation ne peut "
            "rendre admissible une option qu'une contrainte dure ecarte."
        ),
    )
    temps_maximal: float | None = Field(
        default=None,
        gt=0,
        le=60,
        description="Duree de calcul allouee, en secondes",
    )


class MotifSortant(BaseModel):
    """Motif ayant ecarte une chambre."""

    code: str = Field(examples=["bloquee"])
    detail: str | None = Field(default=None, examples=["acces_pmr"])


class OptionEcarteeSortante(BaseModel):
    """Chambre ecartee, accompagnee de ses motifs et de leur formulation."""

    chambre: str
    motifs: list[MotifSortant]
    formulations: list[str]


class ContrepartieSortante(BaseModel):
    """Preference souple non satisfaite par la chambre retenue."""

    code: str = Field(examples=["souhait_non_satisfait"])
    poids: int
    formulation: str


class RecommandationSortante(BaseModel):
    """Issue d'un cycle de decision, soumise a validation humaine.

    Aucune recommandation n'est appliquee par le systeme: la validation par un
    responsable demeure requise.
    """

    a_conclu: bool = Field(description="Une chambre admissible a ete retenue")
    chambre_proposee: str | None
    justification: str = Field(description="Justification derivee de la trace")
    chambres_examinees: int
    chambres_admissibles: list[str]
    cout: int = Field(description="Somme des penalites des preferences sacrifiees")
    optimal: bool
    sous_reserve: bool = Field(
        description="La recommandation est conforme mais non garantie optimale"
    )
    contreparties: list[ContrepartieSortante]
    options_ecartees: list[OptionEcarteeSortante]


class Anomalie(BaseModel):
    """Description d'une defaillance survenue lors du traitement."""

    code: str = Field(examples=["demande_invalide"])
    message: str
