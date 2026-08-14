"""Objets-valeurs du domaine.

Un objet-valeur est defini par son contenu et non par une identite. Deux
instances de meme contenu sont egales. Les invariants sont verifies a la
construction: une valeur incoherente ne peut pas exister dans le programme.
"""

from dataclasses import dataclass
from datetime import date, time

from .etats import Equipement


class ValeurInvalideError(ValueError):
    """Signale une valeur du domaine ne respectant pas ses invariants."""


@dataclass(frozen=True, slots=True)
class NumeroChambre:
    """Identifiant commercial d'une chambre, tel qu'affiche sur la porte."""

    valeur: str

    def __post_init__(self) -> None:
        if not self.valeur.strip():
            raise ValeurInvalideError("le numero de chambre ne peut etre vide")

    def __str__(self) -> str:
        return self.valeur


@dataclass(frozen=True, slots=True)
class IdentifiantReservation:
    """Reference unique d'une reservation dans le systeme."""

    valeur: str

    def __post_init__(self) -> None:
        if not self.valeur.strip():
            raise ValeurInvalideError("l'identifiant de reservation ne peut etre vide")

    def __str__(self) -> str:
        return self.valeur


@dataclass(frozen=True, slots=True)
class Periode:
    """Intervalle de sejour, borne d'arrivee incluse et borne de depart exclue."""

    arrivee: date
    depart: date

    def __post_init__(self) -> None:
        if self.depart <= self.arrivee:
            raise ValeurInvalideError(
                f"le depart ({self.depart}) doit suivre l'arrivee ({self.arrivee})"
            )

    @property
    def nombre_nuitees(self) -> int:
        return (self.depart - self.arrivee).days

    def chevauche(self, autre: "Periode") -> bool:
        """Indique si deux periodes partagent au moins une nuitee."""
        return self.arrivee < autre.depart and autre.arrivee < self.depart

    def contient(self, jour: date) -> bool:
        """Indique si une nuitee donnee appartient a la periode."""
        return self.arrivee <= jour < self.depart


@dataclass(frozen=True, slots=True)
class Exigence:
    """Besoin exprime par une reservation, satisfait par un equipement de chambre."""

    equipement: Equipement
    obligatoire: bool

    @property
    def est_bloquante(self) -> bool:
        """Une exigence obligatoire non satisfaite rend une chambre inadmissible."""
        return self.obligatoire


@dataclass(frozen=True, slots=True)
class HeureArrivee:
    """Heure d'arrivee prevue, distincte de l'heure contractuelle d'acces a la chambre."""

    prevue: time
    contractuelle: time

    def est_anticipee(self) -> bool:
        """Indique si le client se presente avant l'heure d'acces garantie."""
        return self.prevue < self.contractuelle
