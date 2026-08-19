"""Generation des justifications a partir de la trace de raisonnement.

La justification est derivee exclusivement de la trace produite par la couche
symbolique. Le generateur ne peut enoncer que ce que la trace contient: la
fidelite est ainsi garantie par construction plutot qu'esperee.

Un point d'extension est prevu par le protocole Reformulateur. Toute autre
implementation devra etre accompagnee d'un verificateur comparant le texte
produit a la trace, sans quoi l'exigence de fidelite ne serait plus tenue.
"""

import logging
import tomllib
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.symbolique.regles import Penalite, Rejet, Resultat

logger = logging.getLogger(__name__)

SECTIONS_ATTENDUES = ("decision", "rejet", "penalite", "regroupement")


class GabaritIntrouvableError(KeyError):
    """Signale un motif de raisonnement sans formulation associee.

    Toute regle produisant un motif doit disposer d'un gabarit: sans lui, une
    contrainte determinante resterait inexpliquee.
    """


class CatalogueInvalideError(ValueError):
    """Signale un catalogue de gabarits incomplet ou mal forme."""


@dataclass(frozen=True, slots=True)
class Enonce:
    """Fragment de justification rattache a un element de la trace."""

    texte: str
    origine: str

    def __str__(self) -> str:
        return self.texte


@dataclass(frozen=True, slots=True)
class Justification:
    """Restitution lisible d'un raisonnement, derivee de sa trace."""

    decision: Enonce
    contreparties: tuple[Enonce, ...] = ()
    options_ecartees: tuple[Enonce, ...] = ()
    reserve: Enonce | None = None

    @property
    def enonces(self) -> tuple[Enonce, ...]:
        """Restitue l'ensemble des enonces, dans l'ordre de lecture."""
        reserve = (self.reserve,) if self.reserve is not None else ()
        return (self.decision, *reserve, *self.contreparties, *self.options_ecartees)

    @property
    def origines(self) -> frozenset[str]:
        """Restitue les elements de trace ayant fonde la justification."""
        return frozenset(enonce.origine for enonce in self.enonces)

    def en_texte(self) -> str:
        return "\n".join(enonce.texte for enonce in self.enonces)


class Reformulateur(Protocol):
    """Point d'extension pour une autre strategie de mise en forme.

    L'implementation par defaut opere par gabarits. Une implementation fondee
    sur un modele generatif devrait etre assortie d'un verificateur rejetant
    toute mention absente de la trace.
    """

    def justifier(self, resultat: Resultat) -> Justification: ...


def charger_catalogue(
    chemin: Path, sections_attendues: tuple[str, ...] = SECTIONS_ATTENDUES
) -> dict[str, dict[str, str]]:
    """Lit et valide un catalogue de gabarits."""
    if not chemin.is_file():
        raise CatalogueInvalideError(f"catalogue introuvable: {chemin}")

    contenu = tomllib.loads(chemin.read_text(encoding="utf-8"))
    manquantes = [section for section in sections_attendues if section not in contenu]
    if manquantes:
        raise CatalogueInvalideError(
            f"sections absentes du catalogue {chemin.name}: {', '.join(manquantes)}"
        )
    return {section: dict(contenu[section]) for section in sections_attendues}


class GenerateurParGabarits:
    """Produit une justification en completant des formulations predefinies."""

    def __init__(self, catalogue: Mapping[str, Mapping[str, str]]) -> None:
        self._catalogue = catalogue

    def justifier(self, resultat: Resultat) -> Justification:
        """Derive la justification complete d'un resultat de raisonnement."""
        return Justification(
            decision=self._enoncer_decision(resultat),
            reserve=self._enoncer_reserve(resultat),
            contreparties=self._enoncer_contreparties(resultat.penalites),
            options_ecartees=self._enoncer_rejets(resultat.rejets),
        )

    def _enoncer_decision(self, resultat: Resultat) -> Enonce:
        variables = {
            "examinees": resultat.nombre_examinees,
            "admissibles": len(resultat.admissibles),
        }
        if resultat.chambre_retenue is None:
            return Enonce(
                texte=self._formuler("decision", "sans_solution", variables),
                origine="decision:sans_solution",
            )
        return Enonce(
            texte=self._formuler(
                "decision",
                "retenue",
                {**variables, "chambre": resultat.chambre_retenue},
            ),
            origine=f"affectation:{resultat.chambre_retenue}",
        )

    def _enoncer_reserve(self, resultat: Resultat) -> Enonce | None:
        if not resultat.interrompu:
            return None
        return Enonce(
            texte=self._formuler("decision", "optimalite_non_garantie", {}),
            origine="decision:optimalite_non_garantie",
        )

    def _enoncer_contreparties(
        self, penalites: tuple[Penalite, ...]
    ) -> tuple[Enonce, ...]:
        return tuple(
            Enonce(
                texte=self._formuler(
                    "penalite", penalite.motif, {"poids": penalite.poids}
                ),
                origine=f"penalite:{penalite.motif}",
            )
            for penalite in penalites
        )

    def _enoncer_rejets(self, rejets: tuple[Rejet, ...]) -> tuple[Enonce, ...]:
        par_motif: dict[str, list[Rejet]] = defaultdict(list)
        for rejet in rejets:
            par_motif[rejet.motif].append(rejet)

        enonces: list[Enonce] = []
        for motif in sorted(par_motif):
            for rejet in par_motif[motif]:
                enonces.append(
                    Enonce(
                        texte=self._formuler(
                            "rejet",
                            rejet.motif,
                            {
                                "chambre": rejet.chambre,
                                "detail": rejet.detail or "",
                            },
                        ),
                        origine=f"rejet:{rejet.chambre}:{rejet.motif}",
                    )
                )
        return tuple(enonces)

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


def creer_generateur(chemin_catalogue: Path) -> GenerateurParGabarits:
    """Construit le generateur par defaut a partir d'un catalogue."""
    generateur = GenerateurParGabarits(charger_catalogue(chemin_catalogue))
    logger.debug("catalogue de gabarits charge depuis %s", chemin_catalogue)
    return generateur
