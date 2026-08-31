"""Modele conjoint fonde sur un encodeur de langue preentraine.

Le modele reprend l'architecture retenue pour la couche d'interpretation, deux
tetes sur un encodeur partage, mais substitue a l'encodeur appris depuis
l'initialisation un encodeur ayant deja appris la langue francaise sur un
corpus etendu.

La substitution repond a une limite etablie par la mesure: un encodeur appris
depuis l'initialisation ne dispose d'aucune relation entre les mots qu'il n'a
pas rencontres. Les termes d'un meme champ lexical y demeurent sans lien, de
sorte qu'une formulation employant un synonyme absent du corpus d'entrainement
ne peut etre rattachee a l'intention correspondante. Un encodeur preentraine
porte ces relations, acquises sur un volume de texte hors de portee d'un
corpus de domaine.

L'interface est identique a celle du modele appris depuis l'initialisation:
les deux se substituent l'un a l'autre sans modification des composants qui
les emploient, ce qui rend leur comparaison directe.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from torch import Tensor, nn
from transformers import AutoModel

from .modele import SortieDuModele

logger = logging.getLogger(__name__)

ENCODEUR_PAR_DEFAUT = "camembert-base"
INDICE_IGNORE = -100


@dataclass(frozen=True, slots=True)
class ConfigurationPreentrainee:
    """Parametres du modele fonde sur un encodeur preentraine."""

    nombre_d_intentions: int
    nombre_d_etiquettes: int
    encodeur: str = ENCODEUR_PAR_DEFAUT
    longueur_maximale: int = 64
    abandon: float = 0.1
    couches_gelees: int = 0

    def __post_init__(self) -> None:
        if self.couches_gelees < 0:
            raise ValueError("le nombre de couches gelees ne peut etre negatif")


class InterpretePreentraine(nn.Module):
    """Encodeur preentraine surmonte des tetes d'intention et d'etiquetage.

    Les tetes sont initialisees de zero: elles n'ont aucun equivalent dans
    l'encodeur preentraine, dont l'apprentissage portait sur la prediction de
    mots masques et non sur les taches du domaine.
    """

    def __init__(self, configuration: ConfigurationPreentrainee) -> None:
        super().__init__()
        self.configuration = configuration

        encodeur: Any = AutoModel.from_pretrained(configuration.encodeur)
        self.encodeur = encodeur
        dimension = int(encodeur.config.hidden_size)

        self.abandon = nn.Dropout(configuration.abandon)
        self.tete_d_intention = nn.Linear(dimension, configuration.nombre_d_intentions)
        self.tete_d_etiquetage = nn.Linear(dimension, configuration.nombre_d_etiquettes)

        for tete in (self.tete_d_intention, self.tete_d_etiquetage):
            nn.init.normal_(tete.weight, mean=0.0, std=0.02)
            nn.init.zeros_(tete.bias)

        if configuration.couches_gelees > 0:
            self._geler(configuration.couches_gelees)

    def _geler(self, nombre: int) -> None:
        """Fige les couches basses de l'encodeur.

        Les couches basses portent des regularites generales de la langue que
        le corpus de domaine, restreint, ne saurait ameliorer; les figer
        reduit le calcul sans deteriorer la representation.
        """
        for parametre in self.encodeur.embeddings.parameters():
            parametre.requires_grad = False
        for couche in self.encodeur.encoder.layer[:nombre]:
            for parametre in couche.parameters():
                parametre.requires_grad = False
        logger.info("%d couches basses figees, plongements compris", nombre)

    def forward(self, indices: Tensor, masque: Tensor) -> SortieDuModele:
        """Restitue les scores d'intention et d'etiquetage.

        La representation du premier jeton porte celle de l'enonce entier: elle
        alimente la tete d'intention, tandis que la representation de chaque
        jeton alimente la tete d'etiquetage.
        """
        sortie = self.encodeur(input_ids=indices, attention_mask=masque)
        etats: Tensor = self.abandon(sortie.last_hidden_state)
        return SortieDuModele(
            scores_d_intention=self.tete_d_intention(etats[:, 0, :]),
            scores_d_etiquettes=self.tete_d_etiquetage(etats),
        )

    def nombre_de_parametres(self) -> int:
        """Denombre les parametres du modele."""
        return sum(parametre.numel() for parametre in self.parameters())

    def nombre_de_parametres_appris(self) -> int:
        """Denombre les parametres effectivement ajustes a l'entrainement."""
        return sum(
            parametre.numel()
            for parametre in self.parameters()
            if parametre.requires_grad
        )


class PerteConjointeAlignee(nn.Module):
    """Perte conjointe adaptee a un etiquetage aligne sur les mots.

    Les morceaux de mot autres que le premier portent l'indice ignore: un mot
    decoupe en plusieurs unites ne doit produire qu'une seule prediction, sans
    quoi ses morceaux pourraient se contredire sur une meme entite.
    """

    def __init__(
        self,
        coefficient_d_etiquetage: float = 1.0,
        lissage_des_etiquettes: float = 0.0,
    ) -> None:
        super().__init__()
        self.coefficient = coefficient_d_etiquetage
        self.entropie_d_intention = nn.CrossEntropyLoss(
            label_smoothing=lissage_des_etiquettes
        )
        self.entropie_d_etiquetage = nn.CrossEntropyLoss(ignore_index=INDICE_IGNORE)

    def forward(
        self,
        sortie: SortieDuModele,
        intentions: Tensor,
        etiquettes: Tensor,
        masque: Tensor,
    ) -> tuple[Tensor, Tensor, Tensor]:
        """Combine les deux pertes.

        Le masque n'intervient pas au calcul: les positions de remplissage et
        les morceaux de mot autres que le premier portent deja l'indice
        ignore. Le parametre demeure neanmoins declare afin que cette perte
        soit substituable a celle du modele appris depuis l'initialisation.
        """
        del masque

        perte_intention = self.entropie_d_intention(
            sortie.scores_d_intention, intentions
        )
        perte_etiquetage = self.entropie_d_etiquetage(
            sortie.scores_d_etiquettes.reshape(-1, sortie.scores_d_etiquettes.size(-1)),
            etiquettes.reshape(-1),
        )
        totale = perte_intention + self.coefficient * perte_etiquetage
        return totale, perte_intention, perte_etiquetage


def creer_modele_preentraine(
    configuration: ConfigurationPreentrainee,
) -> InterpretePreentraine:
    """Construit le modele et consigne son dimensionnement."""
    modele = InterpretePreentraine(configuration)
    logger.info(
        "modele preentraine construit sur %s: %d parametres dont %d appris",
        configuration.encodeur,
        modele.nombre_de_parametres(),
        modele.nombre_de_parametres_appris(),
    )
    return modele


def enregistrer_preentraine(
    modele: InterpretePreentraine, destination: Path
) -> None:
    """Consigne les parametres du modele et sa configuration."""
    destination.mkdir(parents=True, exist_ok=True)
    torch.save(modele.state_dict(), destination / "parametres.pt")
    logger.info("modele preentraine consigne dans %s", destination)
