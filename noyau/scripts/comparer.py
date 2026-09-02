"""Comparaison des deux modeles d'interpretation.

Le script soumet les memes enonces aux deux modeles et restitue leurs lectures
respectives. Les enonces employent des formulations absentes des deux corpus
d'entrainement: ils mesurent ce que chaque modele fait d'une tournure qu'il
n'a jamais rencontree.

Les entites extraites sont confrontees aux references de l'etablissement: une
extraction plausible mais sans correspondance reelle est signalee, ce qui
interdit qu'un raisonnement s'engage sur une reference inventee.

Emploi:
    python -m scripts.comparer
    python -m scripts.comparer --enonce "il y a une fuite dans la 407"
"""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from src.domaine import Periode
from src.donnees import (
    DepotAgents,
    DepotChambres,
    DepotReservations,
    creer_fabrique_de_sessions,
    creer_moteur,
    session_de_travail,
)
from src.neuronal.entrainement import charger
from src.neuronal.inference import (
    Interpretation,
    Interprete,
    referentiel_depuis,
    verifier_les_entites,
)
from src.neuronal.inference_preentrainee import InterpretePreentraineDEnonces
from src.neuronal.specialisation import charger_specialise

RACINE_MODELES = Path(__file__).resolve().parents[1] / "modeles"

ENONCES: tuple[str, ...] = (
    "il y a une fuite dans la 407",
    "la moquette de la 512 est trempee",
    "le plafond de la 308 goutte",
    "la clim de la 405 ne marche plus",
    "impossible de regler la temperature en 201",
    "le client de la 610 est bloque dehors",
    "plus aucune lumiere dans la 302",
    "A-0003 est absent aujourd'hui",
    "personne pour remplacer A-0007 sur etage 4",
    "organiser le service du secteur etage 5",
    "la 415 doit etre prete pour 13h",
    "bloquer la 512 jusqu'a nouvel ordre",
    "il y a une fuite dans la 999",
    "bonjour, comment allez vous",
)

logger = logging.getLogger("comparaison")


def relever_le_referentiel() -> tuple[list[str], list[str], list[str], list[str]]:
    """Releve les references de l'etablissement persiste."""
    moteur = creer_moteur()
    try:
        fabrique = creer_fabrique_de_sessions(moteur)
        with session_de_travail(fabrique) as session:
            depot = DepotChambres(session)
            parc = depot.lister()
            return (
                [str(chambre.numero) for chambre in parc],
                [
                    str(sejour.identifiant)
                    for sejour in DepotReservations(session).lister_sur_periode(
                        Periode(date(2026, 1, 1), date(2027, 1, 1))
                    )
                ][:400],
                [str(agent.identifiant) for agent in DepotAgents(session).lister()],
                sorted(
                    {
                        depot.secteur_de(chambre.numero).replace("_", " ")
                        for chambre in parc
                    }
                ),
            )
    finally:
        moteur.dispose()


def restituer(titre: str, interpretation: Interpretation) -> None:
    """Affiche une lecture sous forme lisible."""
    entites = ", ".join(
        f"{entite.type_d_entite}={entite.valeur}"
        + ("" if entite.existe is not False else " [inexistante]")
        for entite in interpretation.entites
    )
    print(
        f"    {titre:<14} {interpretation.intention or 'aucune':<28} "
        f"{interpretation.confiance_d_intention:.2f}  {entites}"
    )
    if interpretation.reserves:
        motifs = ", ".join(str(reserve) for reserve in interpretation.reserves)
        print(f"    {'':<14} reserve: {motifs}")


def executer(arguments: argparse.Namespace) -> int:
    """Soumet les enonces aux deux modeles et restitue leurs lectures."""
    chambres, reservations, agents, secteurs = relever_le_referentiel()
    referentiel = referentiel_depuis(chambres, reservations, agents, secteurs)

    depuis_zero = RACINE_MODELES / "interprete"
    preentraine = RACINE_MODELES / "interprete-preentraine"

    interpretes: list[tuple[str, object]] = []

    if (depuis_zero / "parametres.pt").is_file():
        modele, tokeniseur = charger(depuis_zero)
        interpretes.append(("depuis zero", Interprete(modele, tokeniseur)))
    else:
        print(f"Modele absent: {depuis_zero}")

    if (preentraine / "parametres.pt").is_file():
        modele_p, tokeniseur_p = charger_specialise(preentraine)
        interpretes.append(
            ("preentraine", InterpretePreentraineDEnonces(modele_p, tokeniseur_p))
        )
    else:
        print(f"Modele absent: {preentraine}")

    if not interpretes:
        return 1

    enonces = (arguments.enonce,) if arguments.enonce else ENONCES

    for enonce in enonces:
        print(f"\n  {enonce}")
        for titre, interprete in interpretes:
            lecture = verifier_les_entites(
                interprete.interpreter(enonce), referentiel  # type: ignore[attr-defined]
            )
            restituer(titre, lecture)

    return 0


def construire_analyseur() -> argparse.ArgumentParser:
    """Declare les options acceptees par le script."""
    analyseur = argparse.ArgumentParser(
        prog="comparer",
        description="Compare les lectures des deux modeles d'interpretation.",
    )
    analyseur.add_argument("--enonce", help="Enonce unique a soumettre.")
    return analyseur


def main() -> int:
    """Point d'entree du script."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stdout)
    return executer(construire_analyseur().parse_args())


if __name__ == "__main__":
    sys.exit(main())
