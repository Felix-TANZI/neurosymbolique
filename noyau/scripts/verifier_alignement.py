"""Verification de l'alignement des etiquettes sur les sous-unites.

Le script affiche, pour un enonce annote, la correspondance entre morceaux de
mots et etiquettes. Il doit etre execute avant tout entrainement du modele
preentraine: un desalignement ferait apprendre au modele des correspondances
fausses sans qu'aucune mesure ne le revele.

Emploi:
    python -m scripts.verifier_alignement
"""

import sys

from src.neuronal.taxonomie import etiquettes_bio, indices_des_etiquettes
from src.neuronal.tokeniseur_aligne import INDICE_IGNORE, TokeniseurAligne


def afficher(tokeniseur: TokeniseurAligne, mots: list[str], etiquettes: list[str]) -> bool:
    """Affiche l'alignement et restitue sa conformite."""
    indices = indices_des_etiquettes()
    noms = etiquettes_bio()

    segmente = tokeniseur.encoder(mots, [indices[nom] for nom in etiquettes])
    morceaux = tokeniseur.morceaux(mots)

    print(f"\nEnonce: {' '.join(mots)}")
    print(f"{'morceau':<14} {'rang':<6} {'etiquette'}")
    print("-" * 40)

    for rang, morceau in enumerate(morceaux):
        mot = segmente.rangs_des_mots[rang]
        etiquette = segmente.etiquettes[rang]
        libelle = "ignore" if etiquette == INDICE_IGNORE else noms[etiquette]
        print(f"{morceau:<14} {str(mot):<6} {libelle}")

    positions = segmente.positions_des_mots
    conforme = len(positions) == len(mots)
    print(f"\nmots: {len(mots)} | positions retenues: {len(positions)}")

    if conforme:
        restituees = [noms[segmente.etiquettes[position]] for position in positions]
        conforme = restituees == etiquettes
        print(f"etiquettes restituees: {restituees}")
        print(f"etiquettes attendues : {etiquettes}")

    print("conforme" if conforme else "DESALIGNEMENT")
    return conforme


def main() -> int:
    """Verifie l'alignement sur plusieurs enonces representatifs."""
    tokeniseur = TokeniseurAligne()
    print(f"Encodeur: {tokeniseur.encodeur}")
    print(f"Vocabulaire: {tokeniseur.taille} sous-unites")

    cas: list[tuple[list[str], list[str]]] = [
        (
            ["il", "y", "a", "une", "fuite", "dans", "la", "407"],
            ["O", "O", "O", "O", "O", "O", "O", "B-chambre"],
        ),
        (
            ["a", "-", "0003", "est", "absent", "sur", "etage", "4"],
            ["B-agent", "I-agent", "I-agent", "O", "O", "O", "B-secteur", "I-secteur"],
        ),
        (
            ["la", "moquette", "de", "la", "612", "est", "trempee"],
            ["O", "O", "O", "O", "B-chambre", "O", "O"],
        ),
        (
            ["r", "-", "00042", "arrive", "a", "13h"],
            ["B-reservation", "I-reservation", "I-reservation", "O", "O", "B-heure"],
        ),
    ]

    conformes = [afficher(tokeniseur, mots, etiquettes) for mots, etiquettes in cas]

    print(f"\n{sum(conformes)}/{len(conformes)} enonces correctement alignes")
    return 0 if all(conformes) else 1


if __name__ == "__main__":
    sys.exit(main())
