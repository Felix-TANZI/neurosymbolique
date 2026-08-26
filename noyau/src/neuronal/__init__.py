"""Couche d'interpretation des enonces operationnels."""

from .corpus import (
    Corpus,
    CorpusInvalideError,
    EnonceAnnote,
    GenerateurDeCorpus,
    segmenter,
    verifier,
)
from .taxonomie import (
    ENTITES_ATTENDUES,
    ETIQUETTE_HORS_ENTITE,
    Intention,
    TypeDEntite,
    etiquettes_bio,
    indices_des_etiquettes,
    indices_des_intentions,
)

__all__ = [
    "ENTITES_ATTENDUES",
    "ETIQUETTE_HORS_ENTITE",
    "Corpus",
    "CorpusInvalideError",
    "EnonceAnnote",
    "GenerateurDeCorpus",
    "Intention",
    "TypeDEntite",
    "etiquettes_bio",
    "indices_des_etiquettes",
    "indices_des_intentions",
    "segmenter",
    "verifier",
]
