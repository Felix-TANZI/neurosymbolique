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

    cas = TraiterUnIncident(creer_cas_usage(RACINE_CONNAISSANCES))
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
        recommandation = relogement.recommandation
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
        print(
            f"    {recommandation.nombre_examinees} chambres examinees, "
            f"{len(recommandation.resultat.admissibles)} admissibles"
        )

        if not recommandation.a_conclu:
            motifs: dict[str, int] = {}
            for option in recommandation.options_ecartees:
                for motif in option.motifs:
                    motifs[motif.motif] = motifs.get(motif.motif, 0) + 1
            print("    motifs de rejet:")
            for code, compte in sorted(
                motifs.items(), key=lambda paire: -paire[1]
            ):
                print(f"      {code}: {compte} chambres")

        if not recommandation.a_conclu and recommandation.resultat.admissibles:
            admissibles = sorted(recommandation.resultat.admissibles)
            print(f"    admissibles au diagnostic: {admissibles}")
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