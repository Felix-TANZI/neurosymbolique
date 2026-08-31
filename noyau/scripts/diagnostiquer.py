"""Diagnostic des erreurs de la couche d'interpretation.

Le script analyse un modele consigne sans le reentrainer. Il etablit la
justesse par intention, les confusions les plus frequentes et la part de
jetons inconnus dans les enonces d'evaluation.

L'enjeu est de distinguer deux causes d'echec. Une confusion entre intentions
proches revele un modele insuffisamment discriminant, que davantage de donnees
ou un reglage different corrigerait. Une correlation entre erreurs et jetons
inconnus revele une limite structurelle: un mot jamais rencontre ne porte
aucun sens pour un modele appris depuis l'initialisation, faute de
representation prealable.

Emploi:
    python -m scripts.diagnostiquer
    python -m scripts.diagnostiquer --modele modeles/interprete --exemples 15
"""

import argparse
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path

from src.donnees import (
    DepotAgents,
    DepotChambres,
    DepotReservations,
    creer_fabrique_de_sessions,
    creer_moteur,
    session_de_travail,
)
from src.neuronal import GenerateurDeCorpus
from src.neuronal.corpus import EnonceAnnote
from src.neuronal.entrainement import charger
from src.neuronal.inference import Interprete
from src.neuronal.tokeniseur import JETON_INCONNU, Tokeniseur

MODELE_PAR_DEFAUT = Path(__file__).resolve().parents[1] / "modeles" / "interprete"

logger = logging.getLogger("diagnostic")


def relever_les_entites() -> dict[str, list[str]]:
    """Releve les references de l'etablissement, comme a l'entrainement."""
    from datetime import date

    from src.domaine import Periode

    moteur = creer_moteur()
    try:
        fabrique = creer_fabrique_de_sessions(moteur)
        with session_de_travail(fabrique) as session:
            depot = DepotChambres(session)
            parc = depot.lister()
            return {
                "chambre": [str(chambre.numero) for chambre in parc],
                "agent": [
                    str(agent.identifiant) for agent in DepotAgents(session).lister()
                ],
                "secteur": sorted(
                    {
                        depot.secteur_de(chambre.numero).replace("_", " ")
                        for chambre in parc
                    }
                ),
                "reservation": [
                    str(sejour.identifiant)
                    for sejour in DepotReservations(session).lister_sur_periode(
                        Periode(date(2026, 1, 1), date(2027, 1, 1))
                    )
                ][:400],
            }
    finally:
        moteur.dispose()


def part_de_jetons_inconnus(enonce: EnonceAnnote, tokeniseur: Tokeniseur) -> float:
    """Etablit la proportion de jetons absents du vocabulaire."""
    indice_inconnu = tokeniseur.indice_de(JETON_INCONNU)
    inconnus = sum(
        1 for jeton in enonce.jetons if tokeniseur.indice_de(jeton) == indice_inconnu
    )
    return inconnus / max(1, len(enonce.jetons))


def diagnostiquer(
    interprete: Interprete,
    tokeniseur: Tokeniseur,
    enonces: list[EnonceAnnote],
    exemples: int,
) -> None:
    """Analyse les erreurs et restitue les grandeurs caracteristiques."""
    justes_par_intention: Counter[str] = Counter()
    total_par_intention: Counter[str] = Counter()
    confusions: Counter[tuple[str, str]] = Counter()
    inconnus_justes: list[float] = []
    inconnus_faux: list[float] = []
    erreurs: list[tuple[str, str, str, float]] = []
    par_part_inconnue: dict[str, list[int]] = defaultdict(list)

    for enonce in enonces:
        interpretation = interprete.interpreter(enonce.texte)
        exact = interpretation.intention == enonce.intention
        part = part_de_jetons_inconnus(enonce, tokeniseur)

        total_par_intention[enonce.intention] += 1
        if exact:
            justes_par_intention[enonce.intention] += 1
            inconnus_justes.append(part)
        else:
            inconnus_faux.append(part)
            confusions[(enonce.intention, interpretation.intention)] += 1
            if len(erreurs) < exemples:
                erreurs.append(
                    (
                        enonce.texte,
                        enonce.intention,
                        interpretation.intention,
                        interpretation.confiance_d_intention,
                    )
                )

        tranche = (
            "aucun" if part == 0 else "faible" if part < 0.2 else "eleve"
        )
        par_part_inconnue[tranche].append(int(exact))

    print("\n=== Justesse par intention ===")
    for intention in sorted(total_par_intention):
        total = total_par_intention[intention]
        justes = justes_par_intention[intention]
        print(f"  {intention:32} {justes:4}/{total:4}  {justes / total:.3f}")

    print("\n=== Confusions les plus frequentes ===")
    for (attendue, obtenue), compte in confusions.most_common(10):
        print(f"  {attendue:30} lu comme {obtenue:30} {compte:4} fois")

    print("\n=== Jetons inconnus et exactitude ===")
    moyenne_justes = sum(inconnus_justes) / max(1, len(inconnus_justes))
    moyenne_faux = sum(inconnus_faux) / max(1, len(inconnus_faux))
    print(f"  part moyenne de jetons inconnus, lectures exactes : {moyenne_justes:.3f}")
    print(f"  part moyenne de jetons inconnus, lectures fausses : {moyenne_faux:.3f}")

    print("\n=== Justesse selon la part de jetons inconnus ===")
    for tranche in ("aucun", "faible", "eleve"):
        resultats = par_part_inconnue.get(tranche, [])
        if resultats:
            print(
                f"  {tranche:8} {len(resultats):5} enonces  "
                f"justesse {sum(resultats) / len(resultats):.3f}"
            )

    print("\n=== Exemples d'erreurs ===")
    for texte, attendue, obtenue, confiance in erreurs:
        print(f"  {texte}")
        print(f"     attendu {attendue}, lu {obtenue} (confiance {confiance:.2f})")


def construire_analyseur() -> argparse.ArgumentParser:
    """Declare les options acceptees par le script."""
    analyseur = argparse.ArgumentParser(
        prog="diagnostiquer",
        description="Analyse les erreurs d'un modele consigne.",
    )
    analyseur.add_argument("--modele", type=Path, default=MODELE_PAR_DEFAUT)
    analyseur.add_argument("--par-intention", type=int, default=800)
    analyseur.add_argument("--graine", type=int, default=20260812)
    analyseur.add_argument("--exemples", type=int, default=10)
    return analyseur


def executer(arguments: argparse.Namespace) -> int:
    """Conduit le diagnostic et restitue le code de sortie."""
    if not (arguments.modele / "parametres.pt").is_file():
        print(f"Aucun modele consigne sous {arguments.modele}.")
        return 1

    modele, tokeniseur = charger(arguments.modele)
    corpus = GenerateurDeCorpus(
        relever_les_entites(), graine=arguments.graine
    ).engendrer(par_intention=arguments.par_intention)

    print(f"Modele: {arguments.modele}")
    print(f"Vocabulaire: {tokeniseur.taille} jetons")
    print(f"Evaluation: {len(corpus.evaluation)} enonces")

    diagnostiquer(
        Interprete(modele, tokeniseur),
        tokeniseur,
        list(corpus.evaluation),
        arguments.exemples,
    )
    return 0


def main() -> int:
    """Point d'entree du script."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stdout)
    return executer(construire_analyseur().parse_args())


if __name__ == "__main__":
    sys.exit(main())
