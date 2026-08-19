"""Orchestration du cycle de decision de planification du nettoyage.

Le cas d'usage enchaine les composants et traite leurs defaillances. Il ne
comporte aucune logique metier: l'admissibilite des paires releve des regles,
l'ordonnancement releve du solveur, la formulation releve des gabarits.

Le cycle comporte une etape de plus que celui de l'affectation des chambres:
le moteur logique etablit les paires tache-agent admissibles, puis le solveur
de contraintes ordonnance les taches sur les seules paires retenues.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from typing import Final

from src.domaine import AgentEtage, ServiceEtage, TacheNettoyage
from src.gouvernance import (
    CatalogueInvalideError,
    GabaritIntrouvableError,
    GenerateurDePlanification,
    creer_generateur_de_planification,
)
from src.symbolique.ordonnancement import (
    Ordonnancement,
    OrdonnancementImpossibleError,
    TachePlanifiee,
    ordonnancer,
)
from src.symbolique.regles import (
    ConstatDePaires,
    MoteurIndisponibleError,
    ReglesIntrouvablesError,
    RejetDePaire,
    charger_regles,
    diagnostiquer_paires,
    identifiant_tache,
    traduire_service,
    vers_agents_disponibles,
    vers_taches_a_ordonnancer,
)

from .affectation import ConnaissancesIndisponiblesError, DemandeInvalideError

logger = logging.getLogger(__name__)

FICHIER_DIAGNOSTIC: Final = "diagnostic_housekeeping.lp"
FICHIER_GABARITS: Final = "gabarits_housekeeping.toml"


@dataclass(frozen=True, slots=True)
class DemandePlanification:
    """Journee de service soumise a la planification."""

    service: ServiceEtage
    competences_par_agent: dict[str, tuple[str, ...]] = field(default_factory=dict)
    exigences_par_tache: dict[str, tuple[str, ...]] = field(default_factory=dict)
    secteurs_reserves: tuple[str, ...] = ()
    poids: dict[str, int] | None = None

    def __post_init__(self) -> None:
        if not self.service.agents:
            raise DemandeInvalideError("le service soumis ne comporte aucun agent")
        if not self.service.taches_a_planifier:
            raise DemandeInvalideError("le service soumis ne comporte aucune tache")


@dataclass(frozen=True, slots=True)
class TacheNonPlanifiee:
    """Tache demeurant sans affectation, accompagnee de sa cause."""

    tache: str
    sans_agent_admissible: bool
    motifs: tuple[RejetDePaire, ...]

    @property
    def cause(self) -> str:
        """Distingue l'absence d'agent admissible du manque de capacite.

        La distinction determine l'action du responsable: mobiliser une
        competence dans le premier cas, degager du temps dans le second.
        """
        if self.sans_agent_admissible:
            return "aucun_agent_admissible"
        return "capacite_insuffisante"


@dataclass(frozen=True, slots=True)
class PlanificationProposee:
    """Issue complete d'un cycle de planification, soumise a validation.

    Aucun planning n'est applique: la validation par un responsable demeure
    requise avant toute mise en oeuvre.
    """

    ordonnancement: Ordonnancement
    constat: ConstatDePaires
    non_planifiees: tuple[TacheNonPlanifiee, ...] = ()
    justification: tuple[str, ...] = ()

    @property
    def est_complete(self) -> bool:
        return self.ordonnancement.est_complet

    @property
    def sous_reserve(self) -> bool:
        """Indique qu'un planning conforme n'est pas garanti optimal."""
        return self.ordonnancement.interrompu

    @property
    def charge_par_agent(self) -> dict[str, int]:
        return self.ordonnancement.charge_par_agent

    def planning_de(self, agent: str) -> tuple[TachePlanifiee, ...]:
        return self.ordonnancement.taches_de(agent)


class ConnaissancesHousekeeping:
    """Regles et gabarits du service, charges une fois pour toutes."""

    def __init__(
        self, diagnostic: str, generateur: GenerateurDePlanification
    ) -> None:
        self.diagnostic = diagnostic
        self.generateur = generateur

    @classmethod
    def charger(cls, racine: Path) -> "ConnaissancesHousekeeping":
        """Lit les regles et les gabarits depuis la base de connaissances."""
        try:
            diagnostic = charger_regles(racine / "regles" / FICHIER_DIAGNOSTIC)
            generateur = creer_generateur_de_planification(
                racine / "explications" / FICHIER_GABARITS
            )
        except (ReglesIntrouvablesError, CatalogueInvalideError) as erreur:
            raise ConnaissancesIndisponiblesError(
                f"base de connaissances incomplete sous {racine}: {erreur}"
            ) from erreur

        logger.info("connaissances du service housekeeping chargees depuis %s", racine)
        return cls(diagnostic=diagnostic, generateur=generateur)


class PlanifierNettoyage:
    """Cas d'usage de planification des taches de nettoyage sur les agents."""

    def __init__(self, connaissances: ConnaissancesHousekeeping) -> None:
        self._connaissances = connaissances

    def executer(
        self, demande: DemandePlanification, temps_maximal: float | None = None
    ) -> PlanificationProposee:
        """Enchaine diagnostic, ordonnancement et justification."""
        situation = traduire_service(
            demande.service,
            demande.competences_par_agent,
            demande.exigences_par_tache,
            demande.secteurs_reserves,
        )

        constat = self._diagnostiquer(situation)
        planning = self._ordonnancer(demande, constat, temps_maximal)
        non_planifiees = self._rassembler_non_planifiees(constat, planning)

        proposition = PlanificationProposee(
            ordonnancement=planning,
            constat=constat,
            non_planifiees=non_planifiees,
            justification=self._justifier(planning, non_planifiees),
        )
        logger.info(
            "planification produite: %d taches planifiees, %d en attente",
            len(planning.planifiees),
            len(non_planifiees),
        )
        return proposition

    def _diagnostiquer(self, situation: str) -> ConstatDePaires:
        try:
            return diagnostiquer_paires(self._connaissances.diagnostic, situation)
        except MoteurIndisponibleError:
            logger.exception("le moteur de regles n'a pu traiter le service")
            raise

    def _ordonnancer(
        self,
        demande: DemandePlanification,
        constat: ConstatDePaires,
        temps_maximal: float | None,
    ) -> Ordonnancement:
        taches = vers_taches_a_ordonnancer(demande.service, constat)
        agents = vers_agents_disponibles(demande.service)
        arguments = {} if temps_maximal is None else {"temps_maximal": temps_maximal}
        try:
            return ordonnancer(taches, agents, demande.poids, **arguments)
        except OrdonnancementImpossibleError:
            logger.exception("le solveur d'ordonnancement n'a pu traiter le service")
            raise

    @staticmethod
    def _rassembler_non_planifiees(
        constat: ConstatDePaires,
        planning: Ordonnancement,
    ) -> tuple[TacheNonPlanifiee, ...]:
        """Qualifie chaque tache demeuree sans affectation."""
        sans_agent = constat.demandes_sans_ressource
        return tuple(
            TacheNonPlanifiee(
                tache=reference,
                sans_agent_admissible=reference in sans_agent,
                motifs=constat.rejets_de(reference),
            )
            for reference in sorted(planning.non_planifiees)
        )

    def _justifier(
        self,
        planning: Ordonnancement,
        non_planifiees: tuple[TacheNonPlanifiee, ...],
    ) -> tuple[str, ...]:
        """Formule le planning et les taches demeurees en attente."""
        try:
            return self._connaissances.generateur.justifier_planification(
                planning, non_planifiees
            )
        except GabaritIntrouvableError:
            logger.exception("un motif de raisonnement ne dispose d'aucune formulation")
            raise


def creer_cas_usage_housekeeping(racine_connaissances: Path) -> PlanifierNettoyage:
    """Construit le cas d'usage a partir d'une base de connaissances."""
    return PlanifierNettoyage(ConnaissancesHousekeeping.charger(racine_connaissances))


def demande_de_service(
    taches: Sequence[TacheNettoyage],
    agents: Sequence[AgentEtage],
    competences_par_agent: dict[str, Sequence[str]] | None = None,
    exigences_par_tache: dict[str, Sequence[str]] | None = None,
    secteurs_reserves: Sequence[str] = (),
    poids: dict[str, int] | None = None,
) -> DemandePlanification:
    """Construit une demande a partir de sequences quelconques.

    L'unicite des identifiants est verifiee sur les sequences fournies: une
    fois converties en ensembles, les entites de meme identite seraient
    silencieusement fusionnees.
    """
    _verifier_unicite([tache.identifiant for tache in taches], "taches")
    _verifier_unicite([str(agent.identifiant) for agent in agents], "agents")
    return DemandePlanification(
        service=ServiceEtage(taches=frozenset(taches), agents=frozenset(agents)),
        competences_par_agent={
            agent: tuple(competences)
            for agent, competences in (competences_par_agent or {}).items()
        },
        exigences_par_tache={
            tache: tuple(competences)
            for tache, competences in (exigences_par_tache or {}).items()
        },
        secteurs_reserves=tuple(secteurs_reserves),
        poids=poids,
    )


def _verifier_unicite(identifiants: Sequence[str], designation: str) -> None:
    """Signale toute identite apparaissant plus d'une fois."""
    if len(identifiants) != len(set(identifiants)):
        raise DemandeInvalideError(f"le service comporte des {designation} en double")


def en_heure(minutes: int) -> time:
    """Convertit un instant exprime en minutes depuis minuit en heure du jour."""
    return time(hour=minutes // 60, minute=minutes % 60)


__all__ = [
    "ConnaissancesHousekeeping",
    "DemandePlanification",
    "PlanificationProposee",
    "PlanifierNettoyage",
    "TacheNonPlanifiee",
    "creer_cas_usage_housekeeping",
    "demande_de_service",
    "en_heure",
    "identifiant_tache",
]
