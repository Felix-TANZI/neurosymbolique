"""Essai du traitement complet d'un incident.

Le script signale un incident sur une chambre occupee et restitue les
consequences etablies: immobilisation, sejours concernes et propositions de
relogement.

Emploi:
    python -m scripts.essayer_incident --chambre 312
"""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from src.domaine import Gravite, TypeIncident
from src.donnees import creer_fabrique_de_sessions, creer_moteur, session_de_travail
from src.orchestration import (
    ProposerDesOptions,
    SignalementDIncident,
    TraiterUnIncident,
    creer_cas_usage,
)

RACINE_CONNAISSANCES = Path(__file__).resolve().parents[2] / "connaissances"


def main() -> int:
    """Signale un incident et restitue ses consequences."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stdout)

    analyseur = argparse.ArgumentParser(prog="essayer_incident")
    analyseur.add_argument("--chambre", required=True)
    analyseur.add_argument("--jour", default="2026-08-12")
    arguments = analyseur.parse_args()

    cas = TraiterUnIncident(ProposerDesOptions(creer_cas_usage(RACINE_CONNAISSANCES)))
    moteur = creer_moteur()
    fabrique = creer_fabrique_de_sessions(moteur)

    try:
        with session_de_travail(fabrique) as session:
            consequences = cas.executer(
                session,
                SignalementDIncident(
                    chambre=arguments.chambre,
                    type_incident=TypeIncident.DEGAT_DES_EAUX,
                    gravite=Gravite.MAJEURE,
                    description="fuite signalee par le client",
                    jour=date.fromisoformat(arguments.jour),
                ),
                temps_maximal=10.0,
            )
    finally:
        moteur.dispose()

    print()
    for enonce in consequences.justification:
        print(f"  {enonce}")

    print(f"\n  sejours concernes : {consequences.nombre_de_sejours}")
    print(f"  sans solution     : {len(consequences.sejours_sans_solution)}")
    print(f"  entierement resolu: {consequences.est_entierement_resolu}")

    for relogement in consequences.sejours_a_reloger:
        eventail = relogement.eventail
        sejour = relogement.reservation
        print(f"\n  {relogement.reference}")
        print(
            f"    {sejour.nombre_personnes} personnes, "
            f"categorie {sejour.categorie_contractee.name.lower()}, "
            f"du {sejour.periode.arrivee} au {sejour.periode.depart}"
        )
        exigences = ", ".join(
            equipement.value for equipement in sejour.exigences_obligatoires
        )
        print(f"    exigences: {exigences or 'aucune'}")
        print(f"    {eventail.resumer()}")

        for option in eventail.options:
            print(f"    {option}")
            for avantage in option.avantages:
                print(f"      + {avantage}")
            for contrepartie in option.contreparties:
                print(f"      - {contrepartie}")

        if relogement.options_partagees:
            print(
                f"    attention: {', '.join(relogement.options_partagees)} "
                f"egalement proposees a un autre sejour"
            )

        if eventail.est_vide:
            print("    motifs de rejet:")
            for motif, compte in eventail.motifs_dominants:
                print(f"      {motif}: {compte} chambres")
            deja = [
                str(autre.chambre_proposee)
                for autre in consequences.sejours_a_reloger
                if autre.chambre_proposee is not None
                and autre.reference != relogement.reference
            ]
            print(f"    deja proposees a d'autres: {deja}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
