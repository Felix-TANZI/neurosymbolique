"""Essai des preferences exprimees sur une affectation.

Le script soumet une meme demande avec et sans preference, afin de verifier que
la preference modifie effectivement le choix. Une preference qui n'aurait aucun
effet observable ne serait pas exploitee par le moteur.

Emploi:
    python -m scripts.essayer_preferences --reference R-00167 --pres-de 405
"""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from src.domaine import NatureDeLaPreference, Preference, Preferences
from src.donnees import (
    DepotChambres,
    DepotReservations,
    creer_fabrique_de_sessions,
    creer_moteur,
    session_de_travail,
)
from src.orchestration import creer_cas_usage
from src.orchestration.affectation import demande_depuis

RACINE = Path(__file__).resolve().parents[2] / "connaissances"


def main() -> int:
    """Compare une affectation avec et sans preference exprimee."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stdout)

    analyseur = argparse.ArgumentParser(prog="essayer_preferences")
    analyseur.add_argument("--reference", required=True)
    analyseur.add_argument("--pres-de", dest="pres_de")
    analyseur.add_argument("--loin-de", dest="loin_de")
    analyseur.add_argument("--jour", default="2026-08-12")
    arguments = analyseur.parse_args()

    jour = date.fromisoformat(arguments.jour)
    cas = creer_cas_usage(RACINE)
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

            exprimees = Preferences()
            if arguments.pres_de:
                exprimees = exprimees.avec(
                    Preference(
                        nature=NatureDeLaPreference.PROXIMITE.value,
                        reference=arguments.pres_de,
                        intensite=1,
                    )
                )
            if arguments.loin_de:
                exprimees = exprimees.avec(
                    Preference(
                        nature=NatureDeLaPreference.ELOIGNEMENT.value,
                        reference=arguments.loin_de,
                        intensite=1,
                    )
                )

            sans = cas.executer(
                demande_depuis(
                    parc, sejour.avec_chambre(None), occupations, jour=jour
                ),
                15.0,
            )
            avec = cas.executer(
                demande_depuis(
                    parc,
                    sejour.avec_chambre(None),
                    occupations,
                    jour=jour,
                    preferences=exprimees,
                ),
                15.0,
            )
    finally:
        moteur.dispose()

    print(f"\n  sejour: {arguments.reference}")
    print(f"  preferences: {[str(p) for p in exprimees] or 'aucune'}")
    print(f"\n  sans preference : {sans.chambre_proposee}")
    print(f"  avec preference : {avec.chambre_proposee}")

    if avec.chambre_proposee and arguments.pres_de:
        from src.domaine import NumeroChambre, distance_entre

        for titre, resultat in (("sans", sans), ("avec", avec)):
            if resultat.chambre_proposee:
                distance = distance_entre(
                    NumeroChambre(resultat.chambre_proposee.removeprefix("c")),
                    NumeroChambre(arguments.pres_de),
                )
                print(f"  distance {titre} preference: {distance}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
