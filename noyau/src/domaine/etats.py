"""Vocabulaire ferme du domaine des operations internes hotelieres.

Chaque ensemble de valeurs est declare comme une enumeration afin qu'une
valeur non prevue soit rejetee a la construction plutot que de produire une
comparaison silencieusement fausse au moment du raisonnement.
"""

from enum import Enum, StrEnum, unique


@unique
class EtatProprete(StrEnum):
    """Cycle de proprete d'une chambre, du depart du client a sa remise en service."""

    SALE = "sale"
    EN_NETTOYAGE = "en_nettoyage"
    A_CONTROLER = "a_controler"
    PRETE = "prete"


@unique
class EtatTechnique(StrEnum):
    """Aptitude technique d'une chambre a recevoir un client."""

    OPERATIONNELLE = "operationnelle"
    DEGRADEE = "degradee"
    BLOQUEE = "bloquee"


@unique
class EtatOccupation(StrEnum):
    """Occupation courante d'une chambre."""

    LIBRE = "libre"
    ATTRIBUEE = "attribuee"
    OCCUPEE = "occupee"


@unique
class Categorie(Enum):
    """Categories commerciales, ordonnees pour permettre le raisonnement sur le surclassement."""

    STANDARD = 1
    SUPERIEURE = 2
    JUNIOR_SUITE = 3
    SUITE = 4

    def __lt__(self, autre: "Categorie") -> bool:
        return self.value < autre.value

    def __le__(self, autre: "Categorie") -> bool:
        return self.value <= autre.value

    def surclasse(self, autre: "Categorie") -> bool:
        """Indique si la categorie est strictement superieure a celle attendue."""
        return self.value > autre.value


@unique
class Equipement(StrEnum):
    """Equipements dont une chambre peut disposer et qu'une reservation peut exiger."""

    LIT_SIMPLE = "lit_simple"
    LIT_DOUBLE = "lit_double"
    LIT_KING = "lit_king"
    ACCES_PMR = "acces_pmr"
    BAIGNOIRE = "baignoire"
    BALCON = "balcon"
    CLIMATISATION = "climatisation"
    COFFRE_FORT = "coffre_fort"


@unique
class TypeIncident(StrEnum):
    """Familles d'incidents pouvant affecter une chambre."""

    DEGAT_DES_EAUX = "degat_des_eaux"
    PANNE_ELECTRIQUE = "panne_electrique"
    PANNE_CLIMATISATION = "panne_climatisation"
    PANNE_PLOMBERIE = "panne_plomberie"
    DEFAUT_SERRURE = "defaut_serrure"
    MOBILIER_ENDOMMAGE = "mobilier_endommage"
    NUISANCE_SONORE = "nuisance_sonore"
    RISQUE_SECURITE = "risque_securite"


@unique
class Gravite(Enum):
    """Niveaux de gravite d'un incident, ordonnes par urgence croissante."""

    MINEURE = 1
    MODEREE = 2
    MAJEURE = 3
    CRITIQUE = 4

    def __lt__(self, autre: "Gravite") -> bool:
        return self.value < autre.value

    def __le__(self, autre: "Gravite") -> bool:
        return self.value <= autre.value


@unique
class StatutFidelite(Enum):
    """Niveaux du programme de fidelite, ordonnes par anciennete de la relation client."""

    AUCUN = 0
    BRONZE = 1
    ARGENT = 2
    OR = 3
    PLATINE = 4

    def __lt__(self, autre: "StatutFidelite") -> bool:
        return self.value < autre.value

    def __le__(self, autre: "StatutFidelite") -> bool:
        return self.value <= autre.value
