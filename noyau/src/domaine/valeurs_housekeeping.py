"""Objets-valeurs du service housekeeping."""

from dataclasses import dataclass
from datetime import time

from .valeurs import ValeurInvalideError


@dataclass(frozen=True, slots=True)
class IdentifiantAgent:
    """Reference d'un agent d'etage dans le systeme."""

    valeur: str

    def __post_init__(self) -> None:
        if not self.valeur.strip():
            raise ValeurInvalideError("l'identifiant d'agent ne peut etre vide")

    def __str__(self) -> str:
        return self.valeur


@dataclass(frozen=True, slots=True)
class Secteur:
    """Zone de l'etablissement confiee a un agent."""

    nom: str

    def __post_init__(self) -> None:
        if not self.nom.strip():
            raise ValeurInvalideError("le nom de secteur ne peut etre vide")

    def __str__(self) -> str:
        return self.nom


@dataclass(frozen=True, slots=True)
class PlageDeService:
    """Intervalle durant lequel un agent peut recevoir des affectations."""

    debut: time
    fin: time

    def __post_init__(self) -> None:
        if self.fin <= self.debut:
            raise ValeurInvalideError(
                f"la fin de service ({self.fin}) doit suivre le debut ({self.debut})"
            )

    @property
    def duree_minutes(self) -> int:
        depart = self.debut.hour * 60 + self.debut.minute
        arrivee = self.fin.hour * 60 + self.fin.minute
        return arrivee - depart

    def contient(self, instant: time) -> bool:
        return self.debut <= instant < self.fin
