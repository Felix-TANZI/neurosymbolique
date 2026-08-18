"""Execution du moteur de regles et restitution des resultats.

Le moteur produit une affectation optimale, l'ensemble des chambres
admissibles et le motif de rejet de chaque option ecartee. Les rejets ne
dependent pas de la solution retenue: ils constituent des faits etablis sur la
situation, ce qui garantit la stabilite des justifications.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import clingo

logger = logging.getLogger(__name__)

TEMPS_DE_CALCUL_PAR_DEFAUT = 10.0


class MoteurIndisponibleError(RuntimeError):
    """Signale une defaillance du moteur de regles ou de son chargement."""


class ReglesIntrouvablesError(FileNotFoundError):
    """Signale l'absence du fichier de regles attendu."""


@dataclass(frozen=True, slots=True)
class Rejet:
    """Motif pour lequel une chambre a ete ecartee pour une reservation."""

    chambre: str
    motif: str
    detail: str | None = None

    def __str__(self) -> str:
        if self.detail is None:
            return f"{self.chambre}: {self.motif}"
        return f"{self.chambre}: {self.motif}({self.detail})"


@dataclass(frozen=True, slots=True)
class Penalite:
    """Preference souple non satisfaite par l'affectation retenue."""

    motif: str
    poids: int


@dataclass(frozen=True, slots=True)
class Resultat:
    """Issue d'un raisonnement sur une situation d'affectation."""

    reservation: str
    chambre_retenue: str | None
    admissibles: frozenset[str] = field(default_factory=frozenset)
    rejets: tuple[Rejet, ...] = ()
    penalites: tuple[Penalite, ...] = ()
    cout: int = 0
    optimal: bool = False
    interrompu: bool = False

    @property
    def a_conclu(self) -> bool:
        return self.chambre_retenue is not None

    @property
    def nombre_examinees(self) -> int:
        return len(self.admissibles) + len({rejet.chambre for rejet in self.rejets})

    def rejets_de(self, chambre: str) -> tuple[Rejet, ...]:
        """Restitue les motifs ayant ecarte une chambre donnee."""
        return tuple(rejet for rejet in self.rejets if rejet.chambre == chambre)


def charger_regles(chemin: Path) -> str:
    """Lit un fichier de regles depuis la base de connaissances."""
    if not chemin.is_file():
        raise ReglesIntrouvablesError(f"fichier de regles introuvable: {chemin}")
    return chemin.read_text(encoding="utf-8")


def diagnostiquer(regles_diagnostic: str, situation: str) -> dict[str, Any]:
    """Etablit les chambres admissibles et le motif de rejet des autres.

    Le diagnostic ne comporte ni choix ni contrainte: son resultat est un
    constat sur la situation, calculable meme lorsqu'aucune affectation n'est
    possible. C'est ce qui garantit qu'une option ecartee porte toujours son
    motif, y compris en l'absence de solution.
    """
    controle = _preparer(regles_diagnostic, situation)
    constat: dict[str, Any] = {"admissibles": [], "rejets": []}

    def retenir(modele: Any) -> None:
        constat.update(_extraire(modele))

    try:
        controle.solve(on_model=retenir)
    except RuntimeError as erreur:
        raise MoteurIndisponibleError(f"echec du diagnostic: {erreur}") from erreur

    return constat


def resoudre(
    regles_decision: str,
    regles_diagnostic: str,
    situation: str,
    temps_maximal: float = TEMPS_DE_CALCUL_PAR_DEFAUT,
) -> Resultat:
    """Execute le moteur sur une situation et restitue l'issue du raisonnement.

    Le diagnostic est etabli en premier et demeure valide quelle que soit
    l'issue de la decision. Le temps de calcul de la decision est borne: en cas
    de depassement, la meilleure solution etablie a cet instant est restituee,
    l'optimalite n'etant alors pas garantie.
    """
    constat = diagnostiquer(regles_diagnostic, situation)
    controle = _preparer(regles_decision, situation)
    modeles: list[dict[str, Any]] = []

    def retenir(modele: Any) -> None:
        modeles.append(_extraire(modele))

    try:
        with controle.solve(on_model=retenir, async_=True) as recherche:
            acheve = recherche.wait(temps_maximal)
            if not acheve:
                recherche.cancel()
                logger.warning(
                    "temps de calcul depasse apres %.1f s, optimalite non garantie",
                    temps_maximal,
                )
            statut = recherche.get()
    except RuntimeError as erreur:
        raise MoteurIndisponibleError(f"echec du moteur de regles: {erreur}") from erreur

    interrompu = not acheve
    admissibles = frozenset(constat["admissibles"])
    rejets = tuple(sorted(constat["rejets"], key=lambda r: (r.chambre, r.motif)))

    if not modeles:
        logger.info("aucune affectation admissible pour la situation soumise")
        return Resultat(
            reservation="",
            chambre_retenue=None,
            admissibles=admissibles,
            rejets=rejets,
        )

    dernier = modeles[-1]
    resultat = Resultat(
        reservation=dernier["reservation"],
        chambre_retenue=dernier["chambre"],
        admissibles=admissibles,
        rejets=rejets,
        penalites=tuple(sorted(dernier["penalites"], key=lambda p: p.motif)),
        cout=dernier["cout"],
        optimal=bool(statut.satisfiable) and not interrompu,
        interrompu=interrompu,
    )
    logger.debug(
        "resolution achevee: %d admissibles, %d rejets, cout %d",
        len(resultat.admissibles),
        len(resultat.rejets),
        resultat.cout,
    )
    return resultat


def _preparer(regles: str, situation: str) -> Any:
    """Construit et fonde le programme logique.

    L'interface de clingo n'exposant pas de signature typee, la construction du
    controleur est isolee dans cette fonction.
    """
    fabrique: Any = clingo.Control
    controle = fabrique(["--opt-mode=opt"])
    try:
        controle.add("base", [], regles)
        controle.add("base", [], situation)
        controle.ground([("base", [])])
    except RuntimeError as erreur:
        raise MoteurIndisponibleError(
            f"programme logique invalide: {erreur}"
        ) from erreur
    return controle


def _extraire(modele: Any) -> dict[str, Any]:
    """Convertit un modele du moteur en structures Python."""
    reservation = ""
    chambre: str | None = None
    penalites: list[Penalite] = []
    admissibles: list[str] = []
    rejets: list[Rejet] = []

    for atome in modele.symbols(shown=True):
        if atome.name == "affectation":
            reservation = atome.arguments[0].name
            chambre = atome.arguments[1].name
        elif atome.name == "admissible":
            admissibles.append(atome.arguments[1].name)
        elif atome.name == "rejet":
            rejets.append(_lire_rejet(atome))
        elif atome.name == "penalite":
            penalites.append(
                Penalite(
                    motif=atome.arguments[1].name,
                    poids=atome.arguments[2].number,
                )
            )

    return {
        "reservation": reservation,
        "chambre": chambre,
        "admissibles": admissibles,
        "rejets": rejets,
        "penalites": penalites,
        "cout": sum(penalite.poids for penalite in penalites),
    }


def _lire_rejet(atome: Any) -> Rejet:
    """Interprete un atome de rejet, dont le motif peut porter un argument."""
    motif = atome.arguments[2]
    if motif.arguments:
        return Rejet(
            chambre=atome.arguments[1].name,
            motif=motif.name,
            detail=motif.arguments[0].name,
        )
    return Rejet(chambre=atome.arguments[1].name, motif=motif.name)
