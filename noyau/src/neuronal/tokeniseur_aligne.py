"""Segmentation en sous-unites et alignement des etiquettes.

Un encodeur preentraine decoupe les mots en sous-unites: un mot absent de son
vocabulaire est represente par plusieurs morceaux, ce qui lui permet de traiter
n'importe quelle forme sans jeton inconnu.

L'etiquetage doit donc etre aligne. Seul le premier morceau d'un mot porte son
etiquette; les suivants recoivent l'indice ignore au calcul de la perte. Sans
cette convention, un mot decoupe en trois morceaux produirait trois
predictions susceptibles de se contredire sur une meme entite, et la valeur
extraite serait tronquee ou incoherente.

La restitution suit la meme convention: la prediction retenue pour un mot est
celle de son premier morceau.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from transformers import AutoTokenizer

logger = logging.getLogger(__name__)

INDICE_IGNORE = -100
LONGUEUR_PAR_DEFAUT = 32


class AlignementImpossibleError(ValueError):
    """Signale un enonce dont les etiquettes ne peuvent etre alignees."""


@dataclass(frozen=True, slots=True)
class EnonceSegmente:
    """Enonce converti en sous-unites, avec ses etiquettes alignees."""

    indices: tuple[int, ...]
    masque: tuple[int, ...]
    etiquettes: tuple[int, ...]
    rangs_des_mots: tuple[int | None, ...]

    def __post_init__(self) -> None:
        longueurs = {
            len(self.indices),
            len(self.masque),
            len(self.etiquettes),
            len(self.rangs_des_mots),
        }
        if len(longueurs) != 1:
            raise AlignementImpossibleError(
                "les indices, le masque, les etiquettes et les rangs doivent "
                "avoir meme longueur"
            )

    @property
    def positions_des_mots(self) -> tuple[int, ...]:
        """Restitue les positions portant l'etiquette d'un mot.

        Ce sont les positions des premiers morceaux, seules a porter une
        prediction exploitable.
        """
        positions: list[int] = []
        precedent: int | None = None
        for position, rang in enumerate(self.rangs_des_mots):
            if rang is not None and rang != precedent:
                positions.append(position)
            precedent = rang
        return tuple(positions)


class TokeniseurAligne:
    """Segmente un enonce en sous-unites et aligne ses etiquettes."""

    def __init__(
        self,
        encodeur: str = "camembert-base",
        longueur_maximale: int = LONGUEUR_PAR_DEFAUT,
    ) -> None:
        segmenteur: Any = AutoTokenizer.from_pretrained(encodeur)
        if not segmenteur.is_fast:
            raise AlignementImpossibleError(
                f"le segmenteur de {encodeur} ne restitue pas le rang des mots, "
                "l'alignement des etiquettes est impossible"
            )
        self._segmenteur = segmenteur
        self.longueur_maximale = longueur_maximale
        self.encodeur = encodeur

    @property
    def taille(self) -> int:
        return int(self._segmenteur.vocab_size)

    @property
    def indice_de_remplissage(self) -> int:
        return int(self._segmenteur.pad_token_id)

    def encoder(
        self, mots: Sequence[str], etiquettes: Sequence[int] | None = None
    ) -> EnonceSegmente:
        """Segmente une suite de mots et aligne leurs etiquettes.

        Les mots sont fournis deja segmentes: la segmentation en mots releve du
        domaine, celle en sous-unites de l'encodeur. Les confondre ferait
        dependre l'annotation du vocabulaire de l'encodeur.
        """
        if etiquettes is not None and len(etiquettes) != len(mots):
            raise AlignementImpossibleError(
                f"desalignement: {len(mots)} mots, {len(etiquettes)} etiquettes"
            )

        encode = self._segmenteur(
            list(mots),
            is_split_into_words=True,
            truncation=True,
            max_length=self.longueur_maximale,
            padding="max_length",
            return_tensors=None,
        )
        rangs = encode.word_ids()

        alignees: list[int] = []
        precedent: int | None = None
        for rang in rangs:
            if rang is None or rang == precedent or etiquettes is None:
                alignees.append(INDICE_IGNORE)
            else:
                alignees.append(etiquettes[rang])
            precedent = rang

        return EnonceSegmente(
            indices=tuple(encode["input_ids"]),
            masque=tuple(encode["attention_mask"]),
            etiquettes=tuple(alignees),
            rangs_des_mots=tuple(rangs),
        )

    def encoder_texte(self, texte: str) -> tuple[EnonceSegmente, list[str]]:
        """Segmente un enonce brut et restitue ses mots.

        La segmentation en mots emploie celle du domaine, afin que les entites
        extraites correspondent aux formes attendues par le systeme.
        """
        from .tokeniseur import segmenter

        mots = segmenter(texte)
        return self.encoder(mots), mots

    def morceaux(self, mots: Sequence[str]) -> list[str]:
        """Restitue les sous-unites produites, utile a la verification."""
        encode = self._segmenteur(
            list(mots),
            is_split_into_words=True,
            truncation=True,
            max_length=self.longueur_maximale,
        )
        return list(self._segmenteur.convert_ids_to_tokens(encode["input_ids"]))

    def enregistrer(self, destination: Any) -> None:
        """Consigne le segmenteur auprès du modele qu'il accompagne."""
        self._segmenteur.save_pretrained(destination)
        logger.info("segmenteur consigne dans %s", destination)


def etiquettes_par_mot(
    predictions: Sequence[int], segmente: EnonceSegmente
) -> list[int]:
    """Restitue une etiquette par mot a partir des predictions par sous-unite.

    Seule la prediction du premier morceau est retenue: c'est elle qui a ete
    entrainee, les suivantes n'ayant jamais contribue a la perte.
    """
    return [predictions[position] for position in segmente.positions_des_mots]
