"""Generation des justifications de planification du nettoyage.

Comme pour l'affectation des chambres, la justification est derivee
exclusivement de la trace du raisonnement: elle enonce le planning retenu, les
taches demeurees en attente et leur cause, sans jamais mentionner un element
que le raisonnement n'a pas etabli.
"""

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from src.symbolique.ordonnancement import Ordonnancement, TachePlanifiee

from .explication import (
    Enonce,
    GabaritIntrouvableError,
    charger_catalogue,
)

logger = logging.getLogger(__name__)

SECTIONS_ATTENDUES = ("decision", "affectation", "non_planifiee", "rejet")


class TacheEnAttente(Protocol):
    """Tache demeuree sans affectation, telle que restituee par l'orchestration."""

    @property
    def tache(self) -> str: ...

    @property
    def cause(self) -> str: ...


class GenerateurDePlanification:
    """Produit la justification d'un planning a partir de gabarits."""

    def __init__(self, catalogue: Mapping[str, Mapping[str, str]]) -> None:
        self._catalogue = catalogue

    def justifier_planification(
        self,
        planning: Ordonnancement,
        non_planifiees: Sequence[TacheEnAttente],
    ) -> tuple[str, ...]:
        """Derive les enonces decrivant le planning et les taches en attente."""
        enonces = [self._enoncer_bilan(planning, non_planifiees)]

        if planning.interrompu:
            enonces.append(
                Enonce(
                    texte=self._formuler("decision", "optimalite_non_garantie", {}),
                    origine="decision:optimalite_non_garantie",
                )
            )

        enonces.extend(self._enoncer_affectations(planning))
        enonces.extend(self._enoncer_attentes(non_planifiees))
        return tuple(enonce.texte for enonce in enonces)

    def _enoncer_bilan(
        self, planning: Ordonnancement, non_planifiees: Sequence[TacheEnAttente]
    ) -> Enonce:
        agents = len(planning.charge_par_agent)
        variables: dict[str, object] = {
            "planifiees": len(planning.planifiees),
            "agents": agents,
            "en_attente": len(non_planifiees),
        }

        if not planning.planifiees:
            return Enonce(
                texte=self._formuler("decision", "aucune_planification", variables),
                origine="decision:aucune_planification",
            )

        if planning.est_complet:
            achevement = max(planifiee.fin_minutes for planifiee in planning.planifiees)
            return Enonce(
                texte=self._formuler(
                    "decision",
                    "planning_complet",
                    {**variables, "achevement": _en_horaire(achevement)},
                ),
                origine="decision:planning_complet",
            )

        return Enonce(
            texte=self._formuler("decision", "planning_partiel", variables),
            origine="decision:planning_partiel",
        )

    def _enoncer_affectations(self, planning: Ordonnancement) -> list[Enonce]:
        return [
            Enonce(
                texte=self._formuler(
                    "affectation",
                    "confiee",
                    {
                        "tache": planifiee.tache,
                        "agent": planifiee.agent,
                        "debut": _en_horaire(planifiee.debut_minutes),
                        "fin": _en_horaire(planifiee.fin_minutes),
                    },
                ),
                origine=f"affectation:{planifiee.tache}:{planifiee.agent}",
            )
            for planifiee in _par_agent_puis_horaire(planning)
        ]

    def _enoncer_attentes(
        self, non_planifiees: Sequence[TacheEnAttente]
    ) -> list[Enonce]:
        return [
            Enonce(
                texte=self._formuler(
                    "non_planifiee", attente.cause, {"tache": attente.tache}
                ),
                origine=f"non_planifiee:{attente.tache}:{attente.cause}",
            )
            for attente in non_planifiees
        ]

    def _formuler(
        self, section: str, motif: str, variables: Mapping[str, object]
    ) -> str:
        """Complete un gabarit, en signalant tout motif sans formulation."""
        gabarit = self._catalogue[section].get(motif)
        if gabarit is None:
            raise GabaritIntrouvableError(
                f"aucune formulation pour le motif {motif} dans la section {section}"
            )
        try:
            return gabarit.format(**variables)
        except KeyError as erreur:
            raise GabaritIntrouvableError(
                f"variable {erreur} absente de la trace pour le motif {motif}"
            ) from erreur


def _en_horaire(minutes: int) -> str:
    """Exprime un instant en minutes depuis minuit sous forme horaire."""
    return f"{minutes // 60:02d}h{minutes % 60:02d}"


def _par_agent_puis_horaire(planning: Ordonnancement) -> list[TachePlanifiee]:
    """Ordonne les affectations pour une lecture par agent."""
    return sorted(planning.planifiees, key=lambda p: (p.agent, p.debut_minutes))


def creer_generateur_de_planification(
    chemin_catalogue: Path,
) -> GenerateurDePlanification:
    """Construit le generateur de planification a partir d'un catalogue."""
    generateur = GenerateurDePlanification(
        charger_catalogue(chemin_catalogue, SECTIONS_ATTENDUES)
    )
    logger.debug("catalogue de planification charge depuis %s", chemin_catalogue)
    return generateur
