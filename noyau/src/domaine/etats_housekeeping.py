"""Vocabulaire ferme du service housekeeping.

Les valeurs propres a l'organisation du travail des etages sont declarees ici,
distinctement du vocabulaire partage avec les autres services.
"""

from enum import Enum, StrEnum, unique


@unique
class TypePrestation(StrEnum):
    """Nature de la prestation attendue sur une chambre."""

    RECOUCHE = "recouche"
    DEPART = "depart"
    REMISE_EN_ETAT = "remise_en_etat"


@unique
class StatutTache(StrEnum):
    """Avancement d'une tache de nettoyage."""

    A_PLANIFIER = "a_planifier"
    PLANIFIEE = "planifiee"
    EN_COURS = "en_cours"
    ACHEVEE = "achevee"


@unique
class DisponibiliteAgent(StrEnum):
    """Aptitude d'un agent a recevoir une affectation."""

    PRESENT = "present"
    RETARD = "retard"
    ABSENT = "absent"


@unique
class PrioriteTache(Enum):
    """Niveaux de priorite, ordonnes par urgence croissante."""

    NORMALE = 1
    ELEVEE = 2
    URGENTE = 3

    def __lt__(self, autre: "PrioriteTache") -> bool:
        return self.value < autre.value

    def __le__(self, autre: "PrioriteTache") -> bool:
        return self.value <= autre.value
