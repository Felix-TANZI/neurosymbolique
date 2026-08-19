"""Entites du service housekeeping.

Comme les entites du service de gestion des chambres, celles-ci possedent une
identite propre et demeurent immuables: toute evolution produit une nouvelle
instance.
"""

from dataclasses import dataclass, field, replace
from datetime import time

from .etats_housekeeping import (
    DisponibiliteAgent,
    PrioriteTache,
    StatutTache,
    TypePrestation,
)
from .valeurs import NumeroChambre, ValeurInvalideError
from .valeurs_housekeeping import IdentifiantAgent, PlageDeService, Secteur

DUREES_PAR_DEFAUT: dict[TypePrestation, int] = {
    TypePrestation.RECOUCHE: 20,
    TypePrestation.DEPART: 40,
    TypePrestation.REMISE_EN_ETAT: 75,
}


@dataclass(frozen=True, slots=True, eq=False)
class AgentEtage:
    """Personne assurant les prestations de nettoyage sur un secteur."""

    identifiant: IdentifiantAgent
    secteur: Secteur
    plage: PlageDeService
    disponibilite: DisponibiliteAgent = DisponibiliteAgent.PRESENT
    minutes_deja_affectees: int = 0

    def __post_init__(self) -> None:
        if self.minutes_deja_affectees < 0:
            raise ValeurInvalideError(f"charge negative pour l'agent {self.identifiant}")
        if self.minutes_deja_affectees > self.plage.duree_minutes:
            raise ValeurInvalideError(
                f"charge de l'agent {self.identifiant} superieure a sa plage de service"
            )

    def __eq__(self, autre: object) -> bool:
        if not isinstance(autre, AgentEtage):
            return NotImplemented
        return self.identifiant == autre.identifiant

    def __hash__(self) -> int:
        return hash(self.identifiant)

    @property
    def est_affectable(self) -> bool:
        """Indique si l'agent peut recevoir une affectation.

        Ne prejuge pas de l'adequation a une tache donnee, qui releve des
        regles de l'etablissement.
        """
        return (
            self.disponibilite is DisponibiliteAgent.PRESENT
            and self.minutes_restantes > 0
        )

    @property
    def minutes_restantes(self) -> int:
        return self.plage.duree_minutes - self.minutes_deja_affectees

    def avec_disponibilite(self, disponibilite: DisponibiliteAgent) -> "AgentEtage":
        return replace(self, disponibilite=disponibilite)

    def avec_charge(self, minutes: int) -> "AgentEtage":
        return replace(self, minutes_deja_affectees=minutes)


@dataclass(frozen=True, slots=True, eq=False)
class TacheNettoyage:
    """Prestation a realiser sur une chambre avant une echeance donnee."""

    identifiant: str
    chambre: NumeroChambre
    prestation: TypePrestation
    secteur: Secteur
    echeance: time | None = None
    priorite: PrioriteTache = PrioriteTache.NORMALE
    statut: StatutTache = StatutTache.A_PLANIFIER
    duree_minutes: int = 0
    agent_affecte: IdentifiantAgent | None = None

    def __post_init__(self) -> None:
        if not self.identifiant.strip():
            raise ValeurInvalideError("l'identifiant de tache ne peut etre vide")
        if self.duree_minutes < 0:
            raise ValeurInvalideError(f"duree negative pour la tache {self.identifiant}")

    def __eq__(self, autre: object) -> bool:
        if not isinstance(autre, TacheNettoyage):
            return NotImplemented
        return self.identifiant == autre.identifiant

    def __hash__(self) -> int:
        return hash(self.identifiant)

    @property
    def duree_effective(self) -> int:
        """Restitue la duree retenue, celle de la prestation a defaut."""
        if self.duree_minutes > 0:
            return self.duree_minutes
        return DUREES_PAR_DEFAUT[self.prestation]

    @property
    def est_sous_echeance(self) -> bool:
        """Indique que la tache doit etre achevee avant une heure imposee."""
        return self.echeance is not None

    @property
    def est_a_planifier(self) -> bool:
        return self.statut is StatutTache.A_PLANIFIER

    def avec_priorite(self, priorite: PrioriteTache) -> "TacheNettoyage":
        return replace(self, priorite=priorite)

    def avec_echeance(self, echeance: time | None) -> "TacheNettoyage":
        return replace(self, echeance=echeance)

    def avec_agent(self, agent: IdentifiantAgent | None) -> "TacheNettoyage":
        return replace(self, agent_affecte=agent)

    def avec_statut(self, statut: StatutTache) -> "TacheNettoyage":
        return replace(self, statut=statut)


@dataclass(frozen=True, slots=True)
class ServiceEtage:
    """Ensemble des taches et des agents d'une journee de service."""

    taches: frozenset[TacheNettoyage] = field(default_factory=frozenset)
    agents: frozenset[AgentEtage] = field(default_factory=frozenset)

    @property
    def taches_a_planifier(self) -> frozenset[TacheNettoyage]:
        return frozenset(tache for tache in self.taches if tache.est_a_planifier)

    @property
    def agents_affectables(self) -> frozenset[AgentEtage]:
        return frozenset(agent for agent in self.agents if agent.est_affectable)

    @property
    def charge_totale_minutes(self) -> int:
        return sum(tache.duree_effective for tache in self.taches_a_planifier)

    @property
    def capacite_totale_minutes(self) -> int:
        return sum(agent.minutes_restantes for agent in self.agents_affectables)

    @property
    def est_sous_capacite(self) -> bool:
        """Indique que la charge excede la capacite disponible.

        Ce constat n'est pas une decision: il signale une situation ou toutes
        les taches ne pourront etre planifiees.
        """
        return self.charge_totale_minutes > self.capacite_totale_minutes
