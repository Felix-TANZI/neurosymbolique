"""Entrainement de la couche d'interpretation.

Le script constitue le corpus a partir des entites de l'etablissement, entraine
le modele et consigne ses parametres, son vocabulaire et ses mesures.

Les entites employees pour engendrer le corpus sont celles de l'etablissement
persiste: un modele entraine sur des references fictives reconnaitrait mal les
references reelles, dont la forme differe.

Emploi:
    python -m scripts.entrainer
    python -m scripts.entrainer --epoques 40 --par-intention 800
    python -m scripts.entrainer --destination modeles/interprete-v2
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
from src.neuronal import (
    GenerateurDeCorpus,
    Tokeniseur,
    construire_vocabulaire,
    verifier,
)
from src.neuronal.entrainement import (
    ConfigurationDEntrainement,
    JeuDEnonces,
    entrainer,
    evaluer,
)
from src.neuronal.modele import ConfigurationDuModele, PerteConjointe
from src.neuronal.taxonomie import Intention, indices_des_etiquettes
from torch.utils.data import DataLoader

RACINE_MODELES = Path(__file__).resolve().parents[1] / "modeles"
DESTINATION_PAR_DEFAUT = RACINE_MODELES / "interprete"

logger = logging.getLogger("entrainement")


def relever_les_entites() -> dict[str, list[str]]:
    """Releve les references reelles de l'etablissement persiste.

    En l'absence d'etablissement, des references de repli sont employees: le
    modele demeure entrainable, au prix d'une moindre fidelite aux formes
    effectivement rencontrees.
    """
    moteur = creer_moteur()
    try:
        fabrique = creer_fabrique_de_sessions(moteur)
        with session_de_travail(fabrique) as session:
            depot_chambres = DepotChambres(session)
            parc = depot_chambres.lister()
            chambres = [str(chambre.numero) for chambre in parc]
            secteurs = sorted(
                {
                    depot_chambres.secteur_de(chambre.numero).replace("_", " ")
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
            "chambre": [f"{etage}{rang:02d}" for etage in range(1, 7) for rang in range(1, 21)],
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
        prog="entrainer",
        description="Entraine la couche d'interpretation des enonces.",
    )
    analyseur.add_argument("--epoques", type=int, default=40)
    analyseur.add_argument("--par-intention", type=int, default=800)
    analyseur.add_argument("--taille-de-lot", type=int, default=32)
    analyseur.add_argument("--taux", type=float, default=3e-4)
    analyseur.add_argument("--dimension", type=int, default=256)
    analyseur.add_argument("--couches", type=int, default=4)
    analyseur.add_argument("--graine", type=int, default=20260812)
    analyseur.add_argument("--destination", type=Path, default=DESTINATION_PAR_DEFAUT)
    analyseur.add_argument(
        "--detaille",
        action="store_true",
        help="Affiche l'avancement lot par lot.",
    )
    return analyseur


def executer(arguments: argparse.Namespace) -> int:
    """Conduit l'entrainement complet et restitue le code de sortie."""
    entites = relever_les_entites()
    print(f"\nEntites relevees: {', '.join(f'{len(v)} {c}' for c, v in entites.items())}")

    corpus = GenerateurDeCorpus(entites, graine=arguments.graine).engendrer(
        par_intention=arguments.par_intention
    )
    mesures_du_corpus = verifier(corpus)
    print(f"Corpus: {mesures_du_corpus}")

    vocabulaire = construire_vocabulaire(
        enonce.jetons for enonce in corpus.entrainement
    )
    tokeniseur = Tokeniseur(vocabulaire)
    print(f"Vocabulaire: {len(vocabulaire)} jetons")

    configuration = ConfigurationDuModele(
        taille_du_vocabulaire=len(vocabulaire),
        nombre_d_intentions=len(Intention),
        nombre_d_etiquettes=len(indices_des_etiquettes()),
        dimension=arguments.dimension,
        nombre_de_couches=arguments.couches,
        indice_de_remplissage=tokeniseur.indice_de_remplissage,
    )

    print(f"\nEntrainement sur {arguments.epoques} epoques au plus...\n")
    modele, historique = entrainer(
        corpus,
        tokeniseur,
        configuration,
        ConfigurationDEntrainement(
            epoques=arguments.epoques,
            taille_de_lot=arguments.taille_de_lot,
            taux_d_apprentissage=arguments.taux,
            graine=arguments.graine,
        ),
        destination=arguments.destination,
    )

    chargeur = DataLoader(
        JeuDEnonces(corpus.evaluation, tokeniseur), batch_size=arguments.taille_de_lot
    )
    mesures = evaluer(
        modele, chargeur, PerteConjointe(2.0), list(indices_des_etiquettes())
    )

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
                "corpus": mesures_du_corpus,
                "vocabulaire": len(vocabulaire),
                "parametres": modele.nombre_de_parametres(),
                "validation": {
                    "justesse_d_intention": historique.meilleures_mesures.justesse_d_intention,
                    "mesure_f1_des_entites": historique.meilleures_mesures.mesure_f1_des_entites,
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
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
    return executer(construire_analyseur().parse_args())


if __name__ == "__main__":
    sys.exit(main())
