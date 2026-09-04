"""Essai de l'arbitrage sur un conflit d'affectation.

Le script recherche une chambre supportant plusieurs sejours concurrents et
restitue l'arbitrage etabli. En l'absence de conflit reel, il en fabrique un en
memoire afin de verifier le traitement.

Emploi:
    python -m scripts.essayer_arbitrage
    python -m scripts.essayer_arbitrage --chambre 312
"""

import argparse
import logging
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session
from src.domaine import Periode
from src.donnees import (
    DepotReservations,
    creer_fabrique_de_sessions,
    creer_moteur,
    session_de_travail,
)
from src.orchestration import creer_cas_usage
from src.orchestration.arbitrage import ArbitrerUnConflit

RACINE = Path(__file__).resolve().parents[2] / "connaissances"


def rechercher_un_conflit(session: Session, jour: date) -> str | None:
    """Recherche une chambre supportant plusieurs sejours concurrents."""
    horizon = Periode(jour, date(jour.year + 1, jour.month, jour.day))
    par_chambre: dict[str, list[str]] = defaultdict(list)

    for sejour in DepotReservations(session).lister_sur_periode(horizon):
        if sejour.chambre_affectee and sejour.periode.depart > jour:
            par_chambre[str(sejour.chambre_affectee)].append(str(sejour.identifiant))

    for chambre, sejours in par_chambre.items():
        if len(sejours) > 1:
            return chambre
    return None


def fabriquer_un_conflit(session: Session, jour: date) -> str | None:
    """Provoque un conflit en affectant deux sejours a une meme chambre.

    La modification demeure en memoire: elle sert a verifier le traitement
    d'une situation que le generateur d'etablissement ne produit pas, celui-ci
    affectant les chambres sans chevauchement.
    """
    depot = DepotReservations(session)
    horizon = Periode(jour, date(jour.year + 1, jour.month, jour.day))
    candidats = [
        sejour
        for sejour in depot.lister_sur_periode(horizon)
        if sejour.chambre_affectee and sejour.periode.arrivee <= jour
    ]

    if not candidats:
        return None

    installe = candidats[0]
    concurrent = next(
        (
            sejour
            for sejour in depot.lister_sur_periode(horizon)
            if sejour.identifiant != installe.identifiant
            and sejour.periode.chevauche(installe.periode)
        ),
        None,
    )

    if concurrent is None:
        return None

    depot.enregistrer(
        concurrent.avec_chambre(installe.chambre_affectee)
    )
    session.flush()
    return str(installe.chambre_affectee)


def main() -> int:
    """Etablit l'arbitrage sur un conflit et le restitue."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stdout)

    analyseur = argparse.ArgumentParser(prog="essayer_arbitrage")
    analyseur.add_argument("--chambre")
    analyseur.add_argument("--jour", default="2026-08-12")
    analyseur.add_argument(
        "--fabriquer",
        action="store_true",
        help="Provoque un conflit afin de verifier le traitement.",
    )
    arguments = analyseur.parse_args()

    jour = date.fromisoformat(arguments.jour)
    cas = ArbitrerUnConflit(creer_cas_usage(RACINE))
    moteur = creer_moteur()
    fabrique = creer_fabrique_de_sessions(moteur)

    try:
        with session_de_travail(fabrique) as session:
            chambre = (
                fabriquer_un_conflit(session, jour)
                if arguments.fabriquer
                else arguments.chambre or rechercher_un_conflit(session, jour)
            )

            if chambre is None:
                print("Aucun conflit d'affectation dans l'etablissement.")
                print("Precisez une chambre avec --chambre pour verifier le cas absent.")
                return 0

            print(f"\nChambre examinee: {chambre}")
            rendu = cas.executer(session, chambre, jour, temps_maximal=15.0)
    finally:
        moteur.dispose()

    print(f"\n  nature du conflit: {rendu.nature}")
    if rendu.anomalie:
        print("  ANOMALIE SIGNALEE")

    print()
    for constat in rendu.constats:
        print(f"  {constat}")

    if rendu.motif_de_l_arbitrage:
        print(f"\n  {rendu.motif_de_l_arbitrage}")

    if rendu.sejour_maintenu:
        print(f"\n  sejour maintenu : {rendu.sejour_maintenu}")
        print(f"  sejour a reloger: {rendu.sejour_a_reloger}")

    if rendu.a_trouve_une_solution and rendu.recommandation is not None:
        print(f"\n  Solution: relogement en {rendu.chambre_proposee}")
        print(f"  {rendu.recommandation.justification.decision.texte}")
    elif rendu.leviers:
        print("\n  Aucune solution directe. Leviers proposes:")
        for levier in rendu.leviers:
            print(f"    {levier.enonce}")
            if levier.chambres_ainsi_ouvertes:
                print(
                    f"      {levier.chambres_ainsi_ouvertes} chambres deviendraient "
                    f"admissibles"
                )

    return 0


if __name__ == "__main__":
    sys.exit(main())
