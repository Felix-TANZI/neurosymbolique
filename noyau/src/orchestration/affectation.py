"""Orchestration du cycle de decision d'affectation.

Le cas d'usage enchaine les composants et traite leurs defaillances. Il ne
comporte aucune logique metier: le choix d'une chambre releve des regles, la
formulation des justifications releve des gabarits. Une condition metier
apparaissant ici serait mal placee.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Final

from src.domaine import Chambre, Reservation
from src.gouvernance import (
    CatalogueInvalideError,
    GabaritIntrouvableError,
    Justification,
    Reformulateur,
    creer_generateur,
)
from src.symbolique.regles import (
    MoteurIndisponibleError,
    ReglesIntrouvablesError,
    Rejet,
    Resultat,
    charger_regles,
    resoudre,
    traduire_situation,
)

logger = logging.getLogger(__name__)

FICHIER_DECISION: Final = "decision_chambres.lp"
FICHIER_DIAGNOSTIC: Final = "diagnostic_chambres.lp"
FICHIER_GABARITS: Final = "gabarits_chambres.toml"


class DemandeInvalideError(ValueError):
    """Signale une demande structurellement incoherente.

    La verification porte sur la forme de la demande, non sur les regles: un
    parc entierement indisponible constitue une situation legitime a laquelle
    le systeme repond par l'absence de solution et ses motifs.
    """


class ConnaissancesIndisponiblesError(RuntimeError):
    """Signale l'impossibilite de charger les regles ou les gabarits."""


@dataclass(frozen=True, slots=True)
class Demande:
    """Situation operationnelle soumise au raisonnement."""

    parc: tuple[Chambre, ...]
    reservation: Reservation
    occupations: tuple[Reservation, ...] = ()
    poids: dict[str, int] | None = None
    jour: date | None = None

    def __post_init__(self) -> None:
        if not self.parc:
            raise DemandeInvalideError("le parc soumis ne comporte aucune chambre")
        numeros = [chambre.numero for chambre in self.parc]
        if len(numeros) != len(set(numeros)):
            raise DemandeInvalideError("le parc comporte des chambres en double")
        if self.reservation in self.occupations:
            raise DemandeInvalideError(
                f"la reservation {self.reservation.identifiant} figure a la fois "
                "parmi les demandes et parmi les occupations"
            )


@dataclass(frozen=True, slots=True)
class OptionEcartee:
    """Chambre non retenue, accompagnee des motifs l'ayant ecartee."""

    chambre: str
    motifs: tuple[Rejet, ...]
    formulations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Recommandation:
    """Issue complete d'un cycle de decision, prete a etre presentee.

    Aucune recommandation n'est appliquee: la validation par un responsable
    demeure requise avant toute mise en oeuvre.
    """

    resultat: Resultat
    justification: Justification
    options_ecartees: tuple[OptionEcartee, ...] = field(default_factory=tuple)

    @property
    def a_conclu(self) -> bool:
        return self.resultat.a_conclu

    @property
    def chambre_proposee(self) -> str | None:
        return self.resultat.chambre_retenue

    @property
    def nombre_examinees(self) -> int:
        return self.resultat.nombre_examinees

    @property
    def sous_reserve(self) -> bool:
        """Indique qu'une recommandation conforme n'est pas garantie optimale."""
        return self.resultat.interrompu


class Connaissances:
    """Regles et gabarits charges une fois pour l'ensemble des decisions.

    Le chargement a chaque decision degraderait la latence sans apporter de
    fraicheur: la base de connaissances evolue par action d'administration,
    non a chaque situation soumise.
    """

    def __init__(
        self, decision: str, diagnostic: str, generateur: Reformulateur
    ) -> None:
        self.decision = decision
        self.diagnostic = diagnostic
        self.generateur = generateur

    @classmethod
    def charger(cls, racine: Path) -> "Connaissances":
        """Lit les regles et les gabarits depuis la base de connaissances."""
        try:
            decision = charger_regles(racine / "regles" / FICHIER_DECISION)
            diagnostic = charger_regles(racine / "regles" / FICHIER_DIAGNOSTIC)
            generateur = creer_generateur(racine / "explications" / FICHIER_GABARITS)
        except (ReglesIntrouvablesError, CatalogueInvalideError) as erreur:
            raise ConnaissancesIndisponiblesError(
                f"base de connaissances incomplete sous {racine}: {erreur}"
            ) from erreur

        logger.info("base de connaissances chargee depuis %s", racine)
        return cls(decision=decision, diagnostic=diagnostic, generateur=generateur)


class AffecterChambre:
    """Cas d'usage d'affectation d'une chambre a une reservation."""

    def __init__(self, connaissances: Connaissances) -> None:
        self._connaissances = connaissances

    def executer(
        self, demande: Demande, temps_maximal: float | None = None
    ) -> Recommandation:
        """Enchaine le cycle de decision et restitue une recommandation.

        Le temps de calcul est borne. En cas de depassement, la recommandation
        demeure conforme mais son optimalite n'est pas garantie.
        """
        situation = traduire_situation(
            demande.parc,
            demande.reservation,
            demande.occupations,
            demande.poids,
            demande.jour,
        )

        resultat = self._raisonner(situation, temps_maximal)
        justification = self._justifier(resultat)

        recommandation = Recommandation(
            resultat=resultat,
            justification=justification,
            options_ecartees=self._rassembler_ecartees(resultat, justification),
        )
        logger.info(
            "decision produite pour %s: %s (%d examinees, %d admissibles)",
            demande.reservation.identifiant,
            recommandation.chambre_proposee or "aucune",
            recommandation.nombre_examinees,
            len(resultat.admissibles),
        )
        return recommandation

    def _raisonner(self, situation: str, temps_maximal: float | None) -> Resultat:
        arguments = {} if temps_maximal is None else {"temps_maximal": temps_maximal}
        try:
            return resoudre(
                self._connaissances.decision,
                self._connaissances.diagnostic,
                situation,
                **arguments,
            )
        except MoteurIndisponibleError:
            logger.exception("le moteur de regles n'a pu traiter la situation")
            raise

    def _justifier(self, resultat: Resultat) -> Justification:
        try:
            return self._connaissances.generateur.justifier(resultat)
        except GabaritIntrouvableError:
            logger.exception("un motif de raisonnement ne dispose d'aucune formulation")
            raise

    @staticmethod
    def _rassembler_ecartees(
        resultat: Resultat, justification: Justification
    ) -> tuple[OptionEcartee, ...]:
        """Regroupe par chambre les motifs de rejet et leurs formulations."""
        chambres = sorted({rejet.chambre for rejet in resultat.rejets})
        ecartees: list[OptionEcartee] = []
        for chambre in chambres:
            motifs = resultat.rejets_de(chambre)
            formulations = tuple(
                enonce.texte
                for enonce in justification.options_ecartees
                if enonce.origine.startswith(f"rejet:{chambre}:")
            )
            ecartees.append(
                OptionEcartee(chambre=chambre, motifs=motifs, formulations=formulations)
            )
        return tuple(ecartees)


def creer_cas_usage(racine_connaissances: Path) -> AffecterChambre:
    """Construit le cas d'usage a partir d'une base de connaissances."""
    return AffecterChambre(Connaissances.charger(racine_connaissances))


def demande_depuis(
    parc: Sequence[Chambre],
    reservation: Reservation,
    occupations: Sequence[Reservation] = (),
    poids: dict[str, int] | None = None,
    jour: date | None = None,
) -> Demande:
    """Construit une demande a partir de sequences quelconques."""
    return Demande(
        parc=tuple(parc),
        reservation=reservation,
        occupations=tuple(occupations),
        poids=poids,
        jour=jour,
    )
