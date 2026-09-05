"""Essai de la production de plusieurs options d'affectation.

Le script restitue les options etablies pour un sejour, avec ce qui les
distingue. Il permet de verifier que le systeme ouvre un arbitrage au
responsable plutot que de lui imposer une proposition unique.

Emploi:
    python -m scripts.essayer_options --reference R-00042
    python -m scripts.essayer_options --reference R-00042 --pres-de 318
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
from src.orchestration.options import ProposerDesOptions

RACINE = Path(__file__).resolve().parents[2] / "connaissances"


def main() -> int:
    """Etablit les options pour un sejour et les restitue."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stdout)

    analyseur = argparse.ArgumentParser(prog="essayer_options")
    analyseur.add_argument("--reference", required=True)
    analyseur.add_argument("--pres-de", dest="pres_de")
    analyseur.add_argument("--nombre", type=int, default=3)
    analyseur.add_argument("--jour", default="2026-08-12")
    arguments = analyseur.parse_args()

    jour = date.fromisoformat(arguments.jour)
    cas = ProposerDesOptions(creer_cas_usage(RACINE))
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

            preferences = Preferences()
            if arguments.pres_de:
                preferences = preferences.avec(
                    Preference(
                        nature=NatureDeLaPreference.PROXIMITE.value,
                        reference=arguments.pres_de,
                    )
                )

            eventail = cas.executer(
                demande_depuis(
                    parc,
                    sejour.avec_chambre(None),
                    occupations,
                    jour=jour,
                    preferences=preferences,
                ),
                arguments.nombre,
                temps_maximal=15.0,
            )
    finally:
        moteur.dispose()

    print(f"\n  sejour: {arguments.reference}")
    if arguments.pres_de:
        print(f"  souhait: une chambre proche de la {arguments.pres_de}")

    print(f"\n  {eventail.resumer()}")

    for option in eventail.options:
        marque = "  -> " if option.est_preferee else "     "
        print(f"\n{marque}{option.chambre}  (cout {option.cout})")

        for avantage in option.avantages:
            print(f"       + {avantage}")
        for contrepartie in option.contreparties:
            print(f"       - {contrepartie}")

        if not option.avantages and not option.contreparties:
            print("       equivalente aux autres sur les criteres evalues")

    if eventail.offre_un_choix:
        print("\n  Un arbitrage demeure ouvert.")
    elif eventail.preferee:
        print("\n  Aucune alternative: cette chambre est la seule possible.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
