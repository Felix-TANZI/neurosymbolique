"""Comparaison du diagnostic et de la decision sur une meme situation.

Le diagnostic etablit les options admissibles, la decision en retient une. Les
deux doivent concorder: une option declaree admissible mais qu'aucune decision
ne peut retenir revele une contrainte presente dans l'un et absente de l'autre.

Emploi:
    python -m scripts.comparer_regles --reservation R-00371
"""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from src.donnees import (
    DepotChambres,
    DepotReservations,
    creer_fabrique_de_sessions,
    creer_moteur,
    session_de_travail,
)
from src.symbolique.regles import (
    charger_regles,
    diagnostiquer,
    preparer,
    traduire_situation,
)

RACINE = Path(__file__).resolve().parents[2] / "connaissances" / "regles"


def main() -> int:
    """Confronte le diagnostic et la decision sur une situation reelle."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stdout)

    analyseur = argparse.ArgumentParser(prog="comparer_regles")
    analyseur.add_argument("--reservation", required=True)
    analyseur.add_argument("--jour", default="2026-08-12")
    arguments = analyseur.parse_args()

    jour = date.fromisoformat(arguments.jour)
    moteur = creer_moteur()
    fabrique = creer_fabrique_de_sessions(moteur)

    try:
        with session_de_travail(fabrique) as session:
            reservation = DepotReservations(session).retrouver(arguments.reservation)
            parc = DepotChambres(session).lister()
            occupations = [
                autre
                for autre in DepotReservations(session).lister_affectees_sur_periode(
                    reservation.periode
                )
                if autre.identifiant != reservation.identifiant
            ]
    finally:
        moteur.dispose()

    situation = traduire_situation(
        parc, reservation.avec_chambre(None), occupations, jour=jour
    )
    diagnostic = charger_regles(RACINE / "diagnostic_chambres.lp")
    decision = charger_regles(RACINE / "decision_chambres.lp")

    constat = diagnostiquer(diagnostic, situation)
    admissibles = sorted(constat["admissibles"])
    print(f"\nAdmissibles au diagnostic: {admissibles}")

    if not admissibles:
        return 0

    print("\nFaits decrivant chaque admissible:")
    for reference in admissibles:
        faits = [
            ligne
            for ligne in situation.splitlines()
            if f"({reference}" in ligne or f", {reference})" in ligne
        ]
        print(f"\n  {reference}")
        for fait in faits:
            print(f"    {fait}")

    print("\nContraintes de la decision:")
    controle = preparer(decision + "\n" + diagnostic, situation)
    with controle.solve(yield_=True) as recherche:
        modeles = list(recherche)
        print(f"  modeles trouves: {len(modeles)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
