"""Domaine metier des operations internes hotelieres.

Ce module ne depend d'aucune technologie: ni base de donnees, ni ontologie,
ni cadre applicatif. Il decrit ce qui est vrai par nature dans l'exploitation
d'un etablissement. Ce qui releve d'une decision de l'etablissement appartient
a la base de connaissances, editable sans modification du code.
"""

from .entites import Chambre, Client, Incident, Reservation
from .entites_housekeeping import (
    DUREES_PAR_DEFAUT,
    AgentEtage,
    ServiceEtage,
    TacheNettoyage,
)
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
from .etats_housekeeping import (
    DisponibiliteAgent,
    PrioriteTache,
    StatutTache,
    TypePrestation,
)
from .valeurs import (
    Exigence,
    HeureArrivee,
    IdentifiantReservation,
    NumeroChambre,
    Periode,
    ValeurInvalideError,
)
from .valeurs_housekeeping import IdentifiantAgent, PlageDeService, Secteur

__all__ = [
    "DUREES_PAR_DEFAUT",
    "AgentEtage",
    "Categorie",
    "Chambre",
    "Client",
    "DisponibiliteAgent",
    "Equipement",
    "EtatOccupation",
    "EtatProprete",
    "EtatTechnique",
    "Exigence",
    "Gravite",
    "HeureArrivee",
    "IdentifiantAgent",
    "IdentifiantReservation",
    "Incident",
    "NumeroChambre",
    "Periode",
    "PlageDeService",
    "PrioriteTache",
    "Reservation",
    "Secteur",
    "ServiceEtage",
    "StatutFidelite",
    "StatutTache",
    "TacheNettoyage",
    "TypeIncident",
    "TypePrestation",
    "ValeurInvalideError",
]
