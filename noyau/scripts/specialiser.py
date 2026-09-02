"""Specialisation de l'encodeur preentraine sur le domaine.

Le script constitue le corpus a partir des entites de l'etablissement, puis
specialise un encodeur preentraine sur les taches du domaine.

Le corpus est identique a celui employe pour le modele appris depuis
l'initialisation, meme graine comprise: les deux modeles demeurent ainsi
comparables, seul l'encodeur les distinguant.

Emploi:
    python -m scripts.specialiser
    python -m scripts.specialiser --epoques 4 --couches-gelees 10
    python -m scripts.specialiser --detaille
"""

import argparse
import json
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
from src.neuronal import GenerateurDeCorpus, verifier
from src.neuronal.modele_preentraine import (
    ConfigurationPreentrainee,
    PerteConjointeAlignee,
)
from src.neuronal.specialisation import (
    ConfigurationDeSpecialisation,
    JeuSegmente,
    evaluer_segmente,
    specialiser,
)
from src.neuronal.taxonomie import Intention, indices_des_etiquettes
from src.neuronal.tokeniseur_aligne import TokeniseurAligne
from torch.utils.data import DataLoader

RACINE_MODELES = Path(__file__).resolve().parents[1] / "modeles"
DESTINATION_PAR_DEFAUT = RACINE_MODELES / "interprete-preentraine"

logger = logging.getLogger("specialisation")


def relever_les_entites() -> dict[str, list[str]]:
    """Releve les references reelles de l'etablissement persiste."""
    moteur = creer_moteur()
    try:
        fabrique = creer_fabrique_de_sessions(moteur)
        with session_de_travail(fabrique) as session:
            depot = DepotChambres(session)
            parc = depot.lister()
            chambres = [str(chambre.numero) for chambre in parc]
            secteurs = sorted(
                {
                    depot.secteur_de(chambre.numero).replace("_", " ")
                    for chambre in parc
                }
            )
            agents = [str(agent.identifiant) for agent in DepotAgents(session).lister()]
            reservations = [
                str(sejour.identifiant)
                for sejour in DepotReservations(session).lister_sur_periode(
                    Periode(date(2026, 1, 1), date(2027, 1, 1))
                )
            ][:400]
    finally:
        moteur.dispose()

    if not chambres:
        logger.warning("etablissement absent, references de repli employees")
        return {
            "chambre": [
                f"{etage}{rang:02d}" for etage in range(1, 7) for rang in range(1, 21)
            ],
            "agent": [f"A-{rang:04d}" for rang in range(1, 13)],
            "secteur": [f"etage {etage}" for etage in range(1, 7)],
            "reservation": [f"R-{rang:05d}" for rang in range(1, 200)],
        }

    return {
        "chambre": chambres,
        "agent": agents,
        "secteur": secteurs,
        "reservation": reservations,
    }


def construire_analyseur() -> argparse.ArgumentParser:
    """Declare les options acceptees par le script."""
    analyseur = argparse.ArgumentParser(
        prog="specialiser",
        description="Specialise un encodeur preentraine sur le domaine.",
    )
    analyseur.add_argument("--encodeur", default="camembert-base")
    analyseur.add_argument("--epoques", type=int, default=4)
    analyseur.add_argument("--couches-gelees", type=int, default=10)
    analyseur.add_argument("--taille-de-lot", type=int, default=16)
    analyseur.add_argument("--longueur", type=int, default=32)
    analyseur.add_argument("--par-intention", type=int, default=800)
    analyseur.add_argument("--graine", type=int, default=20260812)
    analyseur.add_argument("--destination", type=Path, default=DESTINATION_PAR_DEFAUT)
    analyseur.add_argument("--detaille", action="store_true")
    return analyseur


def executer(arguments: argparse.Namespace) -> int:
    """Conduit la specialisation complete et restitue le code de sortie."""
    entites = relever_les_entites()
    print(
        f"\nEntites relevees: "
        f"{', '.join(f'{len(v)} {c}' for c, v in entites.items())}"
    )

    corpus = GenerateurDeCorpus(entites, graine=arguments.graine).engendrer(
        par_intention=arguments.par_intention
    )
    mesures_du_corpus = verifier(corpus)
    print(f"Corpus: {mesures_du_corpus}")

    tokeniseur = TokeniseurAligne(arguments.encodeur, arguments.longueur)
    print(f"Encodeur: {arguments.encodeur}, {tokeniseur.taille} sous-unites")

    configuration = ConfigurationPreentrainee(
        nombre_d_intentions=len(Intention),
        nombre_d_etiquettes=len(indices_des_etiquettes()),
        encodeur=arguments.encodeur,
        longueur_maximale=arguments.longueur,
        couches_gelees=arguments.couches_gelees,
    )

    print(f"\nSpecialisation sur {arguments.epoques} epoques au plus...\n")
    modele, historique = specialiser(
        corpus,
        tokeniseur,
        configuration,
        ConfigurationDeSpecialisation(
            epoques=arguments.epoques,
            taille_de_lot=arguments.taille_de_lot,
            graine=arguments.graine,
        ),
        destination=arguments.destination,
    )

    chargeur = DataLoader(
        JeuSegmente(corpus.evaluation, tokeniseur), batch_size=arguments.taille_de_lot
    )
    mesures = evaluer_segmente(modele, chargeur, PerteConjointeAlignee(2.0))

    print("\nValidation, formulations connues:")
    print(f"  {historique.meilleures_mesures.resumer()}")
    print("\nEvaluation, formulations inconnues:")
    print(f"  {mesures.resumer()}")
    print(
        f"  precision {mesures.precision_des_entites:.4f} "
        f"rappel {mesures.rappel_des_entites:.4f}"
    )
    print(
        f"\nDuree {historique.duree_secondes:.0f} s, "
        f"meilleure epoque {historique.meilleure_epoque}"
    )
    print(f"Modele consigne dans {arguments.destination}")

    (arguments.destination / "evaluation.json").write_text(
        json.dumps(
            {
                "encodeur": arguments.encodeur,
                "couches_gelees": arguments.couches_gelees,
                "corpus": mesures_du_corpus,
                "parametres": modele.nombre_de_parametres(),
                "parametres_appris": modele.nombre_de_parametres_appris(),
                "validation": {
                    "justesse_d_intention": (
                        historique.meilleures_mesures.justesse_d_intention
                    ),
                    "mesure_f1_des_entites": (
                        historique.meilleures_mesures.mesure_f1_des_entites
                    ),
                    "justesse_complete": historique.meilleures_mesures.justesse_complete,
                },
                "evaluation": {
                    "justesse_d_intention": mesures.justesse_d_intention,
                    "precision_des_entites": mesures.precision_des_entites,
                    "rappel_des_entites": mesures.rappel_des_entites,
                    "mesure_f1_des_entites": mesures.mesure_f1_des_entites,
                    "justesse_complete": mesures.justesse_complete,
                },
                "graine": arguments.graine,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


def main() -> int:
    """Point d'entree du script."""
    logging.basicConfig(
        level=logging.DEBUG if "--detaille" in sys.argv else logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    return executer(construire_analyseur().parse_args())


if __name__ == "__main__":
    sys.exit(main())
