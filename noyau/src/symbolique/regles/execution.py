"""Execution des programmes logiques et lecture des constats.

Le module rassemble ce qui est commun a tous les services: la construction et
le fondement d'un programme logique, et la lecture des constats d'admissibilite
portant sur des paires d'entites.

Le constat par paires convient aux services dont la decision porte sur
plusieurs entites simultanement, tel l'ordonnancement des taches de nettoyage
sur les agents d'etage.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import clingo

logger = logging.getLogger(__name__)


class MoteurIndisponibleError(RuntimeError):
    """Signale une defaillance du moteur de regles ou de son chargement."""


class ReglesIntrouvablesError(FileNotFoundError):
    """Signale l'absence du fichier de regles attendu."""


@dataclass(frozen=True, slots=True)
class RejetDePaire:
    """Motif pour lequel une entite a ete ecartee pour une autre."""

    demande: str
    ressource: str
    motif: str
    detail: str | None = None

    def __str__(self) -> str:
        if self.detail is None:
            return f"{self.demande}/{self.ressource}: {self.motif}"
        return f"{self.demande}/{self.ressource}: {self.motif}({self.detail})"


@dataclass(frozen=True, slots=True)
class ConstatDePaires:
    """Admissibilite etablie sur l'ensemble des paires d'une situation."""

    admissibles: frozenset[tuple[str, str]] = frozenset()
    rejets: tuple[RejetDePaire, ...] = ()

    def ressources_admissibles(self, demande: str) -> frozenset[str]:
        """Restitue les ressources admissibles pour une demande donnee."""
        return frozenset(
            ressource for entite, ressource in self.admissibles if entite == demande
        )

    def rejets_de(
        self, demande: str, ressource: str | None = None
    ) -> tuple[RejetDePaire, ...]:
        """Restitue les motifs ayant ecarte une paire ou une demande entiere."""
        return tuple(
            rejet
            for rejet in self.rejets
            if rejet.demande == demande
            and (ressource is None or rejet.ressource == ressource)
        )

    @property
    def demandes_sans_ressource(self) -> frozenset[str]:
        """Restitue les demandes pour lesquelles aucune ressource n'est admissible.

        La distinction importe: une demande sans ressource admissible ne peut
        etre satisfaite quelle que soit la charge, contrairement a une demande
        ecartee faute de capacite disponible.
        """
        pourvues = {demande for demande, _ in self.admissibles}
        concernees = {rejet.demande for rejet in self.rejets}
        return frozenset(concernees - pourvues)


def charger_regles(chemin: Path) -> str:
    """Lit un fichier de regles depuis la base de connaissances."""
    if not chemin.is_file():
        raise ReglesIntrouvablesError(f"fichier de regles introuvable: {chemin}")
    return chemin.read_text(encoding="utf-8")


def preparer(regles: str, situation: str, arguments: list[str] | None = None) -> Any:
    """Construit et fonde un programme logique.

    L'interface de clingo n'exposant pas de signature typee, la construction du
    controleur est isolee dans cette fonction.
    """
    fabrique: Any = clingo.Control
    controle = fabrique(arguments or ["--opt-mode=opt"])
    try:
        controle.add("base", [], regles)
        controle.add("base", [], situation)
        controle.ground([("base", [])])
    except RuntimeError as erreur:
        raise MoteurIndisponibleError(f"programme logique invalide: {erreur}") from erreur
    return controle


def lire_rejet_de_paire(atome: Any) -> RejetDePaire:
    """Interprete un atome de rejet, dont le motif peut porter un argument."""
    motif = atome.arguments[2]
    detail = motif.arguments[0].name if motif.arguments else None
    return RejetDePaire(
        demande=atome.arguments[0].name,
        ressource=atome.arguments[1].name,
        motif=motif.name,
        detail=detail,
    )


def diagnostiquer_paires(regles: str, situation: str) -> ConstatDePaires:
    """Etablit l'admissibilite de chaque paire et le motif des paires ecartees.

    Le diagnostic ne comporte ni choix ni optimisation: son resultat est un
    constat sur la situation, calculable meme lorsqu'aucune solution n'existe.
    C'est ce qui garantit qu'une option ecartee porte toujours son motif.
    """
    controle = preparer(regles, situation)
    admissibles: set[tuple[str, str]] = set()
    rejets: list[RejetDePaire] = []

    def retenir(modele: Any) -> None:
        admissibles.clear()
        rejets.clear()
        for atome in modele.symbols(shown=True):
            if atome.name == "admissible":
                admissibles.add((atome.arguments[0].name, atome.arguments[1].name))
            elif atome.name == "rejet":
                rejets.append(lire_rejet_de_paire(atome))

    try:
        controle.solve(on_model=retenir)
    except RuntimeError as erreur:
        raise MoteurIndisponibleError(f"echec du diagnostic: {erreur}") from erreur

    constat = ConstatDePaires(
        admissibles=frozenset(admissibles),
        rejets=tuple(sorted(rejets, key=lambda r: (r.demande, r.ressource, r.motif))),
    )
    logger.debug(
        "diagnostic acheve: %d paires admissibles, %d rejets",
        len(constat.admissibles),
        len(constat.rejets),
    )
    return constat
