"""Segmentation et encodage des enonces operationnels.

Le vocabulaire est construit sur le corpus du domaine et non sur un corpus
generaliste: les termes d'exploitation hoteliere y sont donc representes, au
prix d'une absence de couverture hors de ce domaine.

Les suites de chiffres sont decoupees en caracteres. Un numero de chambre
apparait trop rarement pour qu'un modele en apprenne quoi que ce soit s'il
constitue un jeton entier; decoupe, il devient une suite de chiffres dont le
modele apprend la forme, ce qui lui permet de reconnaitre un numero jamais
rencontre.
"""

import json
import logging
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

JETON_REMPLISSAGE = "<vide>"
JETON_CLASSIFICATION = "<enonce>"
JETON_INCONNU = "<inconnu>"
JETONS_RESERVES: tuple[str, ...] = (
    JETON_REMPLISSAGE,
    JETON_CLASSIFICATION,
    JETON_INCONNU,
)

SEGMENTATION = re.compile(r"\d|[^\W\d_]+|[^\w\s]", re.UNICODE)


class VocabulaireInvalideError(ValueError):
    """Signale un vocabulaire incomplet ou incoherent."""


def segmenter(texte: str) -> list[str]:
    """Decoupe un enonce en jetons elementaires.

    Les mots demeurent entiers, les chiffres sont isoles un a un et la
    ponctuation est separee: un signe accole a une entite n'en fait ainsi
    jamais partie.
    """
    return SEGMENTATION.findall(texte.lower())


@dataclass(frozen=True, slots=True)
class EnonceEncode:
    """Enonce converti en indices, pret a etre soumis au modele."""

    indices: tuple[int, ...]
    etiquettes: tuple[int, ...]
    masque: tuple[int, ...]
    jetons: tuple[str, ...]

    def __post_init__(self) -> None:
        longueurs = {len(self.indices), len(self.etiquettes), len(self.masque)}
        if len(longueurs) != 1:
            raise VocabulaireInvalideError(
                "les indices, etiquettes et masque doivent avoir meme longueur"
            )


class Tokeniseur:
    """Convertit un enonce en indices et restitue son alignement."""

    def __init__(self, vocabulaire: Sequence[str], longueur_maximale: int = 48) -> None:
        manquants = [
            reserve for reserve in JETONS_RESERVES if reserve not in vocabulaire
        ]
        if manquants:
            raise VocabulaireInvalideError(
                f"jetons reserves absents du vocabulaire: {', '.join(manquants)}"
            )
        self._vocabulaire = tuple(vocabulaire)
        self._indices = {jeton: rang for rang, jeton in enumerate(self._vocabulaire)}
        self.longueur_maximale = longueur_maximale

    @property
    def taille(self) -> int:
        return len(self._vocabulaire)

    @property
    def indice_de_remplissage(self) -> int:
        return self._indices[JETON_REMPLISSAGE]

    def indice_de(self, jeton: str) -> int:
        """Restitue l'indice d'un jeton, celui du jeton inconnu a defaut."""
        return self._indices.get(jeton, self._indices[JETON_INCONNU])

    def jeton_de(self, indice: int) -> str:
        """Restitue le jeton correspondant a un indice."""
        if not 0 <= indice < len(self._vocabulaire):
            raise VocabulaireInvalideError(f"indice hors vocabulaire: {indice}")
        return self._vocabulaire[indice]

    def encoder(
        self,
        jetons: Sequence[str],
        etiquettes: Sequence[int] | None = None,
        etiquette_de_remplissage: int = 0,
    ) -> EnonceEncode:
        """Encode une suite de jetons deja segmentee.

        Le jeton de classification est place en tete: son etat final porte la
        representation de l'enonce entier, dont la tete d'intention se sert.
        Il recoit une etiquette de remplissage, ignoree au calcul de la perte.
        """
        etiquettes_reelles = (
            list(etiquettes) if etiquettes is not None else [etiquette_de_remplissage] * len(jetons)
        )
        if len(etiquettes_reelles) != len(jetons):
            raise VocabulaireInvalideError(
                f"desalignement: {len(jetons)} jetons, "
                f"{len(etiquettes_reelles)} etiquettes"
            )

        utiles = self.longueur_maximale - 1
        retenus = list(jetons[:utiles])
        retenues = etiquettes_reelles[:utiles]

        indices = [self._indices[JETON_CLASSIFICATION]] + [
            self.indice_de(jeton) for jeton in retenus
        ]
        alignees = [etiquette_de_remplissage] + retenues
        masque = [1] * len(indices)

        remplissage = self.longueur_maximale - len(indices)
        indices.extend([self.indice_de_remplissage] * remplissage)
        alignees.extend([etiquette_de_remplissage] * remplissage)
        masque.extend([0] * remplissage)

        return EnonceEncode(
            indices=tuple(indices),
            etiquettes=tuple(alignees),
            masque=tuple(masque),
            jetons=(JETON_CLASSIFICATION, *retenus),
        )

    def encoder_texte(self, texte: str) -> EnonceEncode:
        """Segmente puis encode un enonce brut."""
        return self.encoder(segmenter(texte))

    def enregistrer(self, chemin: Path) -> None:
        """Consigne le vocabulaire, afin qu'un modele demeure exploitable.

        Un modele entraine est indissociable de son vocabulaire: un indice n'a
        de sens que relativement a celui-ci.
        """
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(
            json.dumps(
                {
                    "vocabulaire": list(self._vocabulaire),
                    "longueur_maximale": self.longueur_maximale,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        logger.info("vocabulaire de %d jetons consigne dans %s", self.taille, chemin)

    @classmethod
    def charger(cls, chemin: Path) -> "Tokeniseur":
        """Restitue un tokeniseur depuis un vocabulaire consigne."""
        if not chemin.is_file():
            raise VocabulaireInvalideError(f"vocabulaire introuvable: {chemin}")
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
        return cls(
            vocabulaire=contenu["vocabulaire"],
            longueur_maximale=contenu["longueur_maximale"],
        )


def construire_vocabulaire(
    enonces: Iterable[Sequence[str]], occurrences_minimales: int = 2
) -> list[str]:
    """Constitue le vocabulaire a partir des jetons observes.

    Les jetons trop rares sont ecartes: le modele ne peut rien apprendre d'une
    forme vue une seule fois, et leur presence dilue les representations. Ils
    sont traites comme inconnus, ce qui entraine le modele a s'accommoder de
    formes qu'il ne connait pas.
    """
    comptes: Counter[str] = Counter()
    for jetons in enonces:
        comptes.update(jetons)

    retenus = sorted(
        jeton
        for jeton, compte in comptes.items()
        if compte >= occurrences_minimales and jeton not in JETONS_RESERVES
    )
    vocabulaire = [*JETONS_RESERVES, *retenus]

    logger.info(
        "vocabulaire construit: %d jetons retenus sur %d observes",
        len(vocabulaire),
        len(comptes),
    )
    return vocabulaire
