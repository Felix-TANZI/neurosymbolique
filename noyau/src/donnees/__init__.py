"""Persistance de l'etat operationnel."""

from .conversion import ConversionImpossibleError
from .depots import (
    DepotAgents,
    DepotChambres,
    DepotClients,
    DepotIncidents,
    DepotReservations,
    DepotSecteurs,
    DepotTaches,
    EntiteIntrouvableError,
    JournalDesDecisions,
)
from .session import (
    BaseIndisponibleError,
    adresse_configuree,
    creer_fabrique_de_sessions,
    creer_moteur,
    initialiser_schema,
    reinitialiser_schema,
    session_de_travail,
)
from .simulation import (
    Etablissement,
    GenerateurDEtablissement,
    ProfilDEtablissement,
    ValeurDeProfilInvalideError,
    engendrer_etablissement,
)

__all__ = [
    "BaseIndisponibleError",
    "ConversionImpossibleError",
    "DepotAgents",
    "DepotChambres",
    "DepotClients",
    "DepotIncidents",
    "DepotReservations",
    "DepotSecteurs",
    "DepotTaches",
    "EntiteIntrouvableError",
    "Etablissement",
    "GenerateurDEtablissement",
    "JournalDesDecisions",
    "ProfilDEtablissement",
    "ValeurDeProfilInvalideError",
    "adresse_configuree",
    "creer_fabrique_de_sessions",
    "creer_moteur",
    "engendrer_etablissement",
    "initialiser_schema",
    "reinitialiser_schema",
    "session_de_travail",
]
