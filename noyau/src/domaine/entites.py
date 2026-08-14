"""Entites du domaine.

Une entite possede une identite propre et persiste dans le temps: la chambre
312 demeure la chambre 312 quel que soit son etat. L'egalite se compare sur
l'identite seule. Les entites sont immuables: toute evolution produit une
nouvelle instance, ce qui garantit qu'un etat consigne dans le journal d'audit
ne peut etre modifie retroactivement.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime

from .etats import (
    Categorie,
    Equipement,
    EtatOccupation,
    EtatProprete,
    EtatTechnique,
    Gravite,
    StatutFidelite,
    TypeIncident,
)
from .valeurs import (
    Exigence,
    HeureArrivee,
    IdentifiantReservation,
    NumeroChambre,
    Periode,
    ValeurInvalideError,
)


@dataclass(frozen=True, slots=True, eq=False)
class Chambre:
    """Unite louable de l'etablissement, caracterisee par trois etats independants."""

    numero: NumeroChambre
    etage: int
    capacite: int
    categorie: Categorie
    equipements: frozenset[Equipement] = field(default_factory=frozenset)
    etat_proprete: EtatProprete = EtatProprete.SALE
    etat_technique: EtatTechnique = EtatTechnique.OPERATIONNELLE
    etat_occupation: EtatOccupation = EtatOccupation.LIBRE
    chambres_communicantes: frozenset[NumeroChambre] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.etage < 0:
            raise ValeurInvalideError(
                f"etage negatif pour la chambre {self.numero}: {self.etage}"
            )
        if self.capacite < 1:
            raise ValeurInvalideError(
                f"capacite invalide pour la chambre {self.numero}: {self.capacite}"
            )
        if self.numero in self.chambres_communicantes:
            raise ValeurInvalideError(
                f"la chambre {self.numero} ne peut communiquer avec elle-meme"
            )

    def __eq__(self, autre: object) -> bool:
        if not isinstance(autre, Chambre):
            return NotImplemented
        return self.numero == autre.numero

    def __hash__(self) -> int:
        return hash(self.numero)

    @property
    def est_attribuable(self) -> bool:
        """Indique si la chambre peut recevoir une reservation en l'etat.

        Ne prejuge pas de l'adequation a une reservation donnee, qui releve des
        regles de l'etablissement et non du domaine.
        """
        return (
            self.etat_proprete is EtatProprete.PRETE
            and self.etat_technique is not EtatTechnique.BLOQUEE
            and self.etat_occupation is EtatOccupation.LIBRE
        )

    def dispose_de(self, equipement: Equipement) -> bool:
        return equipement in self.equipements

    def avec_etat_proprete(self, etat: EtatProprete) -> "Chambre":
        return replace(self, etat_proprete=etat)

    def avec_etat_technique(self, etat: EtatTechnique) -> "Chambre":
        return replace(self, etat_technique=etat)

    def avec_etat_occupation(self, etat: EtatOccupation) -> "Chambre":
        return replace(self, etat_occupation=etat)


@dataclass(frozen=True, slots=True, eq=False)
class Client:
    """Personne accueillie, porteuse de caracteristiques durables entre les sejours."""

    identifiant: str
    statut_fidelite: StatutFidelite = StatutFidelite.AUCUN
    besoins_permanents: frozenset[Equipement] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.identifiant.strip():
            raise ValeurInvalideError("l'identifiant client ne peut etre vide")

    def __eq__(self, autre: object) -> bool:
        if not isinstance(autre, Client):
            return NotImplemented
        return self.identifiant == autre.identifiant

    def __hash__(self) -> int:
        return hash(self.identifiant)


@dataclass(frozen=True, slots=True, eq=False)
class Reservation:
    """Sejour prevu, portant ses exigences et son engagement de categorie."""

    identifiant: IdentifiantReservation
    client: Client
    periode: Periode
    nombre_personnes: int
    categorie_contractee: Categorie
    heure_arrivee: HeureArrivee
    exigences: frozenset[Exigence] = field(default_factory=frozenset)
    chambre_affectee: NumeroChambre | None = None

    def __post_init__(self) -> None:
        if self.nombre_personnes < 1:
            raise ValeurInvalideError(
                f"nombre de personnes invalide pour {self.identifiant}: "
                f"{self.nombre_personnes}"
            )

    def __eq__(self, autre: object) -> bool:
        if not isinstance(autre, Reservation):
            return NotImplemented
        return self.identifiant == autre.identifiant

    def __hash__(self) -> int:
        return hash(self.identifiant)

    @property
    def est_affectee(self) -> bool:
        return self.chambre_affectee is not None

    @property
    def exigences_obligatoires(self) -> frozenset[Equipement]:
        """Equipements dont l'absence rend une chambre inadmissible."""
        return frozenset(
            exigence.equipement for exigence in self.exigences if exigence.obligatoire
        )

    @property
    def exigences_souhaitees(self) -> frozenset[Equipement]:
        """Equipements ameliorant la qualite de l'affectation sans la conditionner."""
        return frozenset(
            exigence.equipement
            for exigence in self.exigences
            if not exigence.obligatoire
        )

    def avec_chambre(self, numero: NumeroChambre | None) -> "Reservation":
        return replace(self, chambre_affectee=numero)


@dataclass(frozen=True, slots=True, eq=False)
class Incident:
    """Evenement technique affectant une chambre et conditionnant sa disponibilite."""

    identifiant: str
    chambre: NumeroChambre
    type_incident: TypeIncident
    gravite: Gravite
    signale_le: datetime
    description: str = ""
    resolu: bool = False

    def __post_init__(self) -> None:
        if not self.identifiant.strip():
            raise ValeurInvalideError("l'identifiant d'incident ne peut etre vide")

    def __eq__(self, autre: object) -> bool:
        if not isinstance(autre, Incident):
            return NotImplemented
        return self.identifiant == autre.identifiant

    def __hash__(self) -> int:
        return hash(self.identifiant)

    @property
    def est_ouvert(self) -> bool:
        return not self.resolu

    def avec_gravite(self, gravite: Gravite) -> "Incident":
        return replace(self, gravite=gravite)

    def resolu_maintenant(self) -> "Incident":
        return replace(self, resolu=True)
