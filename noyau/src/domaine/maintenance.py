"""Entites du service de maintenance technique.

Le service traite les defaillances portant sur les equipements de
l'etablissement, qu'elles affectent une chambre ou un equipement commun. Il se
distingue du service des chambres en ce qu'il repare, la ou celui-ci reloge:
une meme fuite appelle les deux, selon des competences et des delais
differents.

Les entites sont immuables. Une intervention dont l'etat pourrait etre modifie
en place rendrait impossible de reconstituer la situation sur laquelle une
decision a ete prise.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum, StrEnum, unique

from .etats import Gravite, TypeIncident
from .valeurs import NumeroChambre


@unique
class Competence(StrEnum):
    """Qualification requise pour conduire une intervention."""

    PLOMBERIE = "plomberie"
    ELECTRICITE = "electricite"
    CLIMATISATION = "climatisation"
    SERRURERIE = "serrurerie"
    MENUISERIE = "menuiserie"
    ASCENSEUR = "ascenseur"
    POLYVALENT = "polyvalent"


@unique
class TypeDEquipementCommun(StrEnum):
    """Equipement desservant plusieurs chambres ou l'etablissement entier."""

    ASCENSEUR = "ascenseur"
    CHAUFFERIE = "chaufferie"
    GROUPE_FROID = "groupe_froid"
    RESEAU_ELECTRIQUE = "reseau_electrique"
    RESEAU_EAU = "reseau_eau"


@unique
class StatutDIntervention(StrEnum):
    """Avancement d'une intervention."""

    A_PLANIFIER = "a_planifier"
    PLANIFIEE = "planifiee"
    EN_COURS = "en_cours"
    ACHEVEE = "achevee"
    SUSPENDUE = "suspendue"


@unique
class Criticite(IntEnum):
    """Portee d'une defaillance sur l'exploitation.

    La criticite differe de la gravite: une panne mineure sur un equipement
    commun immobilise davantage qu'une panne majeure dans une chambre
    inoccupee. Elle se deduit de la nature de la defaillance et de son
    etendue, non de sa seule intensite.
    """

    DIFFEREE = 1
    COURANTE = 2
    PRIORITAIRE = 3
    IMMEDIATE = 4


COMPETENCE_PAR_INCIDENT: dict[TypeIncident, Competence] = {
    TypeIncident.DEGAT_DES_EAUX: Competence.PLOMBERIE,
    TypeIncident.PANNE_PLOMBERIE: Competence.PLOMBERIE,
    TypeIncident.PANNE_ELECTRIQUE: Competence.ELECTRICITE,
    TypeIncident.PANNE_CLIMATISATION: Competence.CLIMATISATION,
    TypeIncident.DEFAUT_SERRURE: Competence.SERRURERIE,
    TypeIncident.MOBILIER_ENDOMMAGE: Competence.MENUISERIE,
    TypeIncident.RISQUE_SECURITE: Competence.POLYVALENT,
    TypeIncident.NUISANCE_SONORE: Competence.POLYVALENT,
}

COMPETENCE_PAR_EQUIPEMENT: dict[TypeDEquipementCommun, Competence] = {
    TypeDEquipementCommun.ASCENSEUR: Competence.ASCENSEUR,
    TypeDEquipementCommun.CHAUFFERIE: Competence.PLOMBERIE,
    TypeDEquipementCommun.GROUPE_FROID: Competence.CLIMATISATION,
    TypeDEquipementCommun.RESEAU_ELECTRIQUE: Competence.ELECTRICITE,
    TypeDEquipementCommun.RESEAU_EAU: Competence.PLOMBERIE,
}

DUREE_PAR_COMPETENCE: dict[Competence, timedelta] = {
    Competence.PLOMBERIE: timedelta(minutes=90),
    Competence.ELECTRICITE: timedelta(minutes=60),
    Competence.CLIMATISATION: timedelta(minutes=120),
    Competence.SERRURERIE: timedelta(minutes=45),
    Competence.MENUISERIE: timedelta(minutes=75),
    Competence.ASCENSEUR: timedelta(minutes=180),
    Competence.POLYVALENT: timedelta(minutes=60),
}


class MaintenanceInvalideError(ValueError):
    """Signale une entite de maintenance structurellement incoherente."""


@dataclass(frozen=True, slots=True)
class IdentifiantTechnicien:
    """Reference d'un technicien de maintenance."""

    valeur: str

    def __post_init__(self) -> None:
        if not self.valeur.strip():
            raise MaintenanceInvalideError("un technicien exige une reference")

    def __str__(self) -> str:
        return self.valeur


@dataclass(frozen=True, slots=True)
class Technicien:
    """Agent de maintenance, avec ses qualifications et sa disponibilite."""

    identifiant: IdentifiantTechnicien
    competences: frozenset[Competence]
    disponible: bool = True
    charge_en_cours: int = 0

    def __post_init__(self) -> None:
        if not self.competences:
            raise MaintenanceInvalideError(
                f"le technicien {self.identifiant} n'a aucune competence"
            )
        if self.charge_en_cours < 0:
            raise MaintenanceInvalideError("une charge ne peut etre negative")

    def maitrise(self, competence: Competence) -> bool:
        """Etablit si le technicien peut conduire une intervention donnee.

        Une intervention sans specialite requise est conduite par tout
        technicien: POLYVALENT designe l'absence d'exigence, non une
        qualification supplementaire.

        Reciproquement, un technicien polyvalent couvre toute specialite, au
        prix d'une moindre maitrise que les durees de reference ne traduisent
        pas.
        """
        if competence is Competence.POLYVALENT:
            return True
        return (
            competence in self.competences
            or Competence.POLYVALENT in self.competences
        )

    @property
    def est_affectable(self) -> bool:
        return self.disponible


@dataclass(frozen=True, slots=True)
class EquipementCommun:
    """Equipement desservant plusieurs chambres."""

    identifiant: str
    type_equipement: TypeDEquipementCommun
    chambres_desservies: frozenset[NumeroChambre] = field(
        default_factory=frozenset
    )
    operationnel: bool = True

    @property
    def portee(self) -> int:
        """Denombre les chambres que sa defaillance affecterait."""
        return len(self.chambres_desservies)


@dataclass(frozen=True, slots=True)
class Intervention:
    """Reparation a conduire sur une chambre ou un equipement commun."""

    identifiant: str
    competence: Competence
    criticite: int
    duree_estimee: timedelta
    chambre: NumeroChambre | None = None
    equipement: str | None = None
    signalee_le: datetime = field(default_factory=datetime.now)
    echeance: datetime | None = None
    statut: str = StatutDIntervention.A_PLANIFIER.value
    technicien: IdentifiantTechnicien | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if self.chambre is None and self.equipement is None:
            raise MaintenanceInvalideError(
                f"l'intervention {self.identifiant} ne porte sur rien"
            )
        if self.chambre is not None and self.equipement is not None:
            raise MaintenanceInvalideError(
                f"l'intervention {self.identifiant} porte sur deux objets"
            )
        if self.duree_estimee <= timedelta():
            raise MaintenanceInvalideError("une duree doit etre positive")

    @property
    def objet(self) -> str:
        """Restitue ce sur quoi porte l'intervention."""
        return str(self.chambre) if self.chambre else str(self.equipement)

    @property
    def est_a_planifier(self) -> bool:
        return self.statut == StatutDIntervention.A_PLANIFIER.value

    @property
    def est_achevee(self) -> bool:
        return self.statut == StatutDIntervention.ACHEVEE.value

    def avec_technicien(
        self, technicien: IdentifiantTechnicien | None
    ) -> "Intervention":
        """Restitue l'intervention affectee a un technicien."""
        from dataclasses import replace

        return replace(
            self,
            technicien=technicien,
            statut=(
                StatutDIntervention.PLANIFIEE.value
                if technicien
                else StatutDIntervention.A_PLANIFIER.value
            ),
        )


def qualifier_la_criticite(
    type_incident: TypeIncident,
    gravite: Gravite,
    portee: int = 1,
) -> Criticite:
    """Etablit la portee d'une defaillance sur l'exploitation.

    La qualification combine la nature de la defaillance, son intensite et son
    etendue. Un risque de securite demeure immediat quelle que soit son
    etendue; une panne ordinaire devient prioritaire des lors qu'elle affecte
    plusieurs chambres, l'immobilisation cumulee pesant davantage que
    l'intensite de la panne.
    """
    if type_incident is TypeIncident.RISQUE_SECURITE:
        return Criticite.IMMEDIATE

    if gravite is Gravite.CRITIQUE:
        return Criticite.IMMEDIATE

    if portee > 1:
        return (
            Criticite.IMMEDIATE
            if gravite >= Gravite.MAJEURE
            else Criticite.PRIORITAIRE
        )

    if gravite >= Gravite.MAJEURE:
        return Criticite.PRIORITAIRE

    return Criticite.COURANTE if gravite is Gravite.MODEREE else Criticite.DIFFEREE


def competence_requise(
    type_incident: TypeIncident | None = None,
    equipement: TypeDEquipementCommun | None = None,
) -> Competence:
    """Etablit la qualification qu'appelle une defaillance.

    Une defaillance sans specialite identifiable restitue POLYVALENT, qui
    n'est pas une qualification supplementaire mais l'absence d'exigence: tout
    technicien peut la conduire.
    """
    if equipement is not None:
        return COMPETENCE_PAR_EQUIPEMENT.get(equipement, Competence.POLYVALENT)
    if type_incident is not None:
        return COMPETENCE_PAR_INCIDENT.get(type_incident, Competence.POLYVALENT)
    return Competence.POLYVALENT
