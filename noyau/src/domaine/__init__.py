"""Domaine metier des operations internes hotelieres.

Ce module ne depend d'aucune technologie: ni base de donnees, ni ontologie,
ni cadre applicatif. Il decrit ce qui est vrai par nature dans l'exploitation
d'un etablissement. Ce qui releve d'une decision de l'etablissement appartient
a la base de connaissances, editable sans modification du code.
"""

from .entites import Chambre, Client, Incident, Reservation
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

__all__ = [
    "Categorie",
    "Chambre",
    "Client",
    "Equipement",
    "EtatOccupation",
    "EtatProprete",
    "EtatTechnique",
    "Exigence",
    "Gravite",
    "HeureArrivee",
    "IdentifiantReservation",
    "Incident",
    "NumeroChambre",
    "Periode",
    "Reservation",
    "StatutFidelite",
    "TypeIncident",
    "ValeurInvalideError",
]
