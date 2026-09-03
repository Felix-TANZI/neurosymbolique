"""Essai des consultations sur l'etablissement persiste.

Le script soumet des interrogations en langue naturelle et restitue les
reponses etablies. Il permet de verifier, avant tout branchement, que chaque
consultation interroge correctement l'etat et le formule intelligiblement.

Emploi:
    python -m scripts.essayer_consultation
    python -m scripts.essayer_consultation --enonce "combien de chambres avons-nous"
"""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from src.donnees import creer_fabrique_de_sessions, creer_moteur, session_de_travail
from src.neuronal.inference_preentrainee import InterpretePreentraineDEnonces
from src.neuronal.specialisation import charger_specialise
from src.neuronal.taxonomie import Intention, appelle_un_raisonnement
from src.orchestration.consultation import ConsultationImpossibleError, consulter

MODELE = Path(__file__).resolve().parents[1] / "modeles" / "interprete-preentraine"

ENONCES: tuple[str, ...] = (
    "combien de chambres avons-nous",
    "quelles chambres sont disponibles",
    "quelles chambres sont hors service a l'etage 4",
    "quelles sont les arrivees du jour",
    "quels agents travaillent aujourd'hui",
    "combien de taches restent a faire",
    "quel est l'etat de la 312",
    "quel est le detail de R-00042",
    "il y a une fuite dans la 319",
)


def main() -> int:
    """Soumet chaque enonce et restitue la reponse etablie."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stdout)

    analyseur = argparse.ArgumentParser(prog="essayer_consultation")
    analyseur.add_argument("--enonce")
    analyseur.add_argument("--jour", default="2026-08-12")
    arguments = analyseur.parse_args()

    if not (MODELE / "parametres.pt").is_file():
        print(f"Aucun modele consigne sous {MODELE}.")
        return 1

    modele, tokeniseur = charger_specialise(MODELE)
    interprete = InterpretePreentraineDEnonces(modele, tokeniseur)
    jour = date.fromisoformat(arguments.jour)

    moteur = creer_moteur()
    fabrique = creer_fabrique_de_sessions(moteur)

    try:
        with session_de_travail(fabrique) as session:
            for enonce in (arguments.enonce,) if arguments.enonce else ENONCES:
                lecture = interprete.interpreter(enonce)
                print(f"\n  {enonce}")
                print(
                    f"    intention: {lecture.intention} "
                    f"({lecture.confiance_d_intention:.2f})"
                )

                if appelle_un_raisonnement(Intention(lecture.intention)):
                    print("    -> arbitrage, hors du perimetre de ce script")
                    continue

                try:
                    reponse = consulter(session, lecture, jour)
                except ConsultationImpossibleError as erreur:
                    print(f"    -> {erreur}")
                    continue

                print(f"    {reponse.enonce}")
                for element in reponse.elements[:5]:
                    print(f"      {element}")
                if len(reponse.elements) > 5:
                    print(f"      ... et {len(reponse.elements) - 5} autres")
    finally:
        moteur.dispose()

    return 0


if __name__ == "__main__":
    sys.exit(main())
