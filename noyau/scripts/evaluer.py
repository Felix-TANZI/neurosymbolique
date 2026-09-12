"""Evaluation comparative des trois approches.

Le script conduit chaque approche sur l'ensemble des scenarios et restitue les
mesures etablies. Son objet n'est pas de conclure a la superiorite d'une
approche, mais d'etablir dans quelles situations leur composition apporte ce
qu'aucune ne procure seule.

Emploi:
    python -m scripts.evaluer
    python -m scripts.evaluer --sortie evaluation/resultats.json
"""

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

from src.donnees import creer_fabrique_de_sessions, creer_moteur, session_de_travail
from src.evaluation.approches import Approche, Conduite
from src.evaluation.banc import BancDEvaluation
from src.evaluation.mesures import Mesure, mesurer
from src.evaluation.scenarios import SCENARIOS, denombrer_par_epreuve
from src.neuronal.inference_preentrainee import InterpretePreentraineDEnonces
from src.neuronal.specialisation import charger_specialise
from src.orchestration import TraiterUnIncident, creer_cas_usage
from src.orchestration.arbitrage import ArbitrerUnConflit
from src.orchestration.options import ProposerDesOptions

RACINE = Path(__file__).resolve().parents[2] / "connaissances"
MODELE = Path(__file__).resolve().parents[1] / "modeles" / "interprete-preentraine"

LIBELLES: dict[str, str] = {
    Approche.NEURONALE.value: "Neuronale seule",
    Approche.SYMBOLIQUE.value: "Symbolique seule",
    Approche.COMPOSEE.value: "Composee",
}


def restituer(mesures: dict[str, Mesure]) -> None:
    """Affiche les mesures sous forme de tableau."""
    print("\n" + "=" * 78)
    print("  MESURES GLOBALES")
    print("=" * 78)
    print(
        f"\n  {'Approche':<20} {'Conduite':>10} {'Intention':>11} "
        f"{'Entites':>9} {'References':>12} {'Duree':>9}"
    )
    print("  " + "-" * 74)

    for approche, mesure in mesures.items():
        print(
            f"  {LIBELLES[approche]:<20} "
            f"{mesure.justesse_de_conduite:>10.3f} "
            f"{mesure.justesse_d_intention:>11.3f} "
            f"{mesure.justesse_des_entites:>9.3f} "
            f"{mesure.detection_des_references:>12.3f} "
            f"{mesure.duree_moyenne:>7.0f}ms"
        )

    print("\n" + "=" * 78)
    print("  ABSTENTION")
    print("=" * 78)
    print(f"\n  {'Approche':<20} {'Justes':>12} {'Abusives':>12}")
    print("  " + "-" * 46)

    for approche, mesure in mesures.items():
        print(
            f"  {LIBELLES[approche]:<20} "
            f"{mesure.abstentions_justes:>4}/{mesure.abstentions_attendues:<7} "
            f"{mesure.abstentions_abusives:>12}"
        )

    print("\n" + "=" * 78)
    print("  RESULTATS PAR EPREUVE")
    print("=" * 78)

    epreuves = sorted(
        {
            resultat.epreuve
            for mesure in mesures.values()
            for resultat in mesure.par_epreuve
        }
    )

    print(f"\n  {'Epreuve':<18}", end="")
    for approche in mesures:
        print(f"{LIBELLES[approche]:>20}", end="")
    print()
    print("  " + "-" * 74)

    for epreuve in epreuves:
        print(f"  {epreuve:<18}", end="")
        for mesure in mesures.values():
            resultat = next(
                (r for r in mesure.par_epreuve if r.epreuve == epreuve), None
            )
            valeur = (
                f"{resultat.reussites}/{resultat.total}" if resultat else "-"
            )
            print(f"{valeur:>20}", end="")
        print()


def restituer_les_ecarts(
    conduites: dict[str, list[Conduite]],
) -> None:
    """Expose les scenarios ou les approches divergent.

    Un scenario ou toutes les approches concordent n'eclaire rien: la
    comparaison ne s'etablit que sur les divergences.
    """
    print("\n" + "=" * 78)
    print("  DIVERGENCES")
    print("=" * 78)

    par_scenario: dict[str, dict[str, str]] = {}
    for approche, liste in conduites.items():
        for observee in liste:
            par_scenario.setdefault(observee.scenario, {})[approche] = (
                observee.conduite
            )

    for scenario in SCENARIOS:
        obtenues = par_scenario.get(scenario.identifiant, {})
        if len(set(obtenues.values())) < 2:
            continue

        print(f"\n  {scenario.identifiant}  {scenario.enonce}")
        print(f"    attendu : {scenario.conduite}")
        for approche, restituee in obtenues.items():
            marque = "  " if restituee == scenario.conduite else " x"
            print(f"   {marque} {LIBELLES[approche]:<20} {restituee}")


def main() -> int:
    """Conduit l'evaluation et restitue les mesures."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stdout)

    analyseur = argparse.ArgumentParser(prog="evaluer")
    analyseur.add_argument("--jour", default="2026-08-12")
    analyseur.add_argument("--sortie", type=Path)
    arguments = analyseur.parse_args()

    if not (MODELE / "parametres.pt").is_file():
        print(f"Aucun modele consigne sous {MODELE}.")
        return 1

    jour = date.fromisoformat(arguments.jour)
    modele, tokeniseur = charger_specialise(MODELE)
    cas = creer_cas_usage(RACINE)
    options = ProposerDesOptions(cas)

    banc = BancDEvaluation(
        InterpretePreentraineDEnonces(modele, tokeniseur),
        TraiterUnIncident(options),
        ArbitrerUnConflit(cas),
    )

    print(f"\n  {len(SCENARIOS)} scenarios: {denombrer_par_epreuve()}")

    conduites: dict[str, list[Conduite]] = {}
    mesures: dict[str, Mesure] = {}

    moteur = creer_moteur()
    fabrique = creer_fabrique_de_sessions(moteur)

    try:
        for approche in Approche:
            print(f"\n  Conduite de l'approche {LIBELLES[approche.value]}...")
            observees: list[Conduite] = []

            for scenario in SCENARIOS:
                with session_de_travail(fabrique) as session:
                    observees.append(
                        banc.conduire(session, scenario, jour, approche.value)
                    )

            conduites[approche.value] = observees
            mesures[approche.value] = mesurer(
                approche.value, SCENARIOS, observees
            )
    finally:
        moteur.dispose()

    restituer(mesures)
    restituer_les_ecarts(conduites)

    if arguments.sortie:
        arguments.sortie.parent.mkdir(parents=True, exist_ok=True)
        arguments.sortie.write_text(
            json.dumps(
                {
                    "jour": arguments.jour,
                    "scenarios": len(SCENARIOS),
                    "mesures": {
                        approche: asdict(mesure)
                        for approche, mesure in mesures.items()
                    },
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"\n  Resultats consignes dans {arguments.sortie}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
