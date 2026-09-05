"""Trace les penalites effectivement produites par le moteur.

Le script expose les penalites que le programme logique engendre pour une
situation donnee. Une preference qui ne modifie pas le choix peut n'avoir
produit aucune penalite, ou en avoir produit sans que l'optimisation les prenne
en compte: seul l'examen des atomes obtenus permet de trancher.

Emploi:
    python -m scripts.tracer_penalites --reference R-00167 --pres-de 405
"""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

import clingo
from src.domaine import NatureDeLaPreference, Preference, Preferences
from src.donnees import (
    DepotChambres,
    DepotReservations,
    creer_fabrique_de_sessions,
    creer_moteur,
    session_de_travail,
)
from src.symbolique.regles.execution import charger_regles
from src.symbolique.regles.traduction import traduire_situation

RACINE = Path(__file__).resolve().parents[2] / "connaissances" / "regles"


def main() -> int:
    """Restitue les penalites produites pour une situation."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stdout)

    analyseur = argparse.ArgumentParser(prog="tracer_penalites")
    analyseur.add_argument("--reference", required=True)
    analyseur.add_argument("--pres-de", dest="pres_de", required=True)
    analyseur.add_argument("--jour", default="2026-08-12")
    arguments = analyseur.parse_args()

    jour = date.fromisoformat(arguments.jour)
    moteur = creer_moteur()
    fabrique = creer_fabrique_de_sessions(moteur)

    try:
        with session_de_travail(fabrique) as session:
            sejour = DepotReservations(session).retrouver(arguments.reference)
            parc = DepotChambres(session).lister()
            occupations = [
                autre
                for autre in DepotReservations(session).lister_affectees_sur_periode(
                    sejour.periode
                )
                if autre.identifiant != sejour.identifiant
            ]
    finally:
        moteur.dispose()

    preferences = Preferences().avec(
        Preference(
            nature=NatureDeLaPreference.PROXIMITE.value,
            reference=arguments.pres_de,
        )
    )
    situation = traduire_situation(
        parc, sejour.avec_chambre(None), occupations, None, jour, preferences
    )

    programme = (
        charger_regles(RACINE / "decision_chambres.lp")
        + "\n"
        + charger_regles(RACINE / "diagnostic_chambres.lp")
        + "\n"
        + situation
    )

    controle = clingo.Control(["--opt-mode=optN", "--models=0"])
    controle.add("base", [], programme)
    controle.ground([("base", [])])

    dernier: list[str] = []
    with controle.solve(yield_=True) as recherche:
        for modele in recherche:
            dernier = [str(atome) for atome in modele.symbols(shown=True)]

    affectations = [a for a in dernier if a.startswith("affectation(")]
    penalites = [a for a in dernier if a.startswith("penalite(")]

    print(f"\n  affectation: {affectations}")
    print(f"  penalites  : {len(penalites)}")
    for penalite in sorted(penalites):
        print(f"    {penalite}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
