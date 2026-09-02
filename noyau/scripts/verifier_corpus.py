"""Verification de la disjonction des partitions du corpus.

Le script identifie les enonces communs aux partitions d'entrainement et
d'evaluation. Leur presence invaliderait la mesure de generalisation: un
enonce vu a l'entrainement et repris en evaluation mesure une memorisation.

Emploi:
    python -m scripts.verifier_corpus
"""

import sys
from collections import defaultdict

from scripts.specialiser import relever_les_entites
from src.neuronal import GenerateurDeCorpus


def main() -> int:
    """Releve les enonces communs aux partitions et leur origine."""
    corpus = GenerateurDeCorpus(relever_les_entites()).engendrer(par_intention=800)

    entrainement = {enonce.texte: enonce.intention for enonce in corpus.entrainement}
    validation = {enonce.texte: enonce.intention for enonce in corpus.validation}
    connus = entrainement | validation

    communs: dict[str, list[str]] = defaultdict(list)
    for enonce in corpus.evaluation:
        if enonce.texte in connus:
            communs[enonce.intention].append(enonce.texte)

    if not communs:
        print("Aucun recouvrement entre les partitions.")
        return 0

    total = sum(len(textes) for textes in communs.values())
    print(f"{total} enonces d'evaluation figurent parmi les enonces connus.\n")

    for intention in sorted(communs):
        textes = communs[intention]
        print(f"{intention}: {len(textes)} enonces")
        for texte in sorted(set(textes))[:4]:
            print(f"    {texte}")
        print()

    return 1


if __name__ == "__main__":
    sys.exit(main())