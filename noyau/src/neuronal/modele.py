"""Modele conjoint de reconnaissance d'intention et d'extraction d'entites.

L'architecture suit le principe etabli par les travaux sur la comprehension
d'enonces: un encodeur unique, partage par les deux taches, surmonte de deux
tetes. La representation du jeton de classification alimente la tete
d'intention; la representation de chaque jeton alimente la tete d'etiquetage.
L'apprentissage conjoint permet a chaque tache de beneficier des
representations construites pour l'autre.

L'encodeur est entraine depuis l'initialisation, sans representation
prealable. Cette voie est exigeante sur petit corpus, mais la litterature
etablit qu'elle demeure praticable des lors que l'initialisation et
l'optimisation sont conduites avec soin: l'initialisation est donc controlee,
la normalisation placee en amont de chaque sous-couche, et le taux
d'apprentissage soumis a un echauffement.
"""

import logging
import math
from dataclasses import dataclass

import torch
from torch import Tensor, nn

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ConfigurationDuModele:
    """Parametres structurels de l'encodeur et de ses tetes."""

    taille_du_vocabulaire: int
    nombre_d_intentions: int
    nombre_d_etiquettes: int
    dimension: int = 256
    nombre_de_couches: int = 4
    nombre_de_tetes: int = 8
    dimension_interne: int = 1024
    longueur_maximale: int = 48
    abandon: float = 0.1
    indice_de_remplissage: int = 0

    def __post_init__(self) -> None:
        if self.dimension % self.nombre_de_tetes != 0:
            raise ConfigurationInvalideError(
                f"la dimension {self.dimension} doit se repartir entre "
                f"{self.nombre_de_tetes} tetes"
            )
        if self.taille_du_vocabulaire < 4:
            raise ConfigurationInvalideError("vocabulaire trop restreint")

    @property
    def dimension_par_tete(self) -> int:
        return self.dimension // self.nombre_de_tetes


class ConfigurationInvalideError(ValueError):
    """Signale une configuration structurellement incoherente."""


@dataclass(frozen=True, slots=True)
class SortieDuModele:
    """Sorties brutes du modele, avant conversion en decisions."""

    scores_d_intention: Tensor
    scores_d_etiquettes: Tensor


class PositionsApprises(nn.Module):
    """Representation de la position d'un jeton dans l'enonce.

    Les positions sont apprises plutot que calculees: les enonces traites sont
    courts et de structure repetitive, ce dont un tableau appris rend compte
    plus finement qu'une formule fixe.
    """

    def __init__(self, longueur_maximale: int, dimension: int) -> None:
        super().__init__()
        self.table = nn.Embedding(longueur_maximale, dimension)

    def forward(self, sequences: Tensor) -> Tensor:
        longueur = sequences.size(1)
        positions = torch.arange(longueur, device=sequences.device)
        encodees: Tensor = self.table(positions)
        return encodees.unsqueeze(0)


class AttentionMultiTete(nn.Module):
    """Attention multi-tete avec masquage du remplissage.

    Le masquage est indispensable: sans lui, les jetons de remplissage
    participeraient a la representation des jetons reels, et un enonce court
    serait interprete differemment selon la longueur du lot qui le contient.
    """

    def __init__(self, configuration: ConfigurationDuModele) -> None:
        super().__init__()
        self.nombre_de_tetes = configuration.nombre_de_tetes
        self.dimension_par_tete = configuration.dimension_par_tete
        self.projection_requete = nn.Linear(configuration.dimension, configuration.dimension)
        self.projection_cle = nn.Linear(configuration.dimension, configuration.dimension)
        self.projection_valeur = nn.Linear(configuration.dimension, configuration.dimension)
        self.projection_sortie = nn.Linear(configuration.dimension, configuration.dimension)
        self.abandon = nn.Dropout(configuration.abandon)

    def _repartir(self, tenseur: Tensor) -> Tensor:
        lot, longueur, _ = tenseur.shape
        return tenseur.view(
            lot, longueur, self.nombre_de_tetes, self.dimension_par_tete
        ).transpose(1, 2)

    def forward(self, etats: Tensor, masque: Tensor) -> Tensor:
        lot, longueur, dimension = etats.shape

        requetes = self._repartir(self.projection_requete(etats))
        cles = self._repartir(self.projection_cle(etats))
        valeurs = self._repartir(self.projection_valeur(etats))

        scores = requetes @ cles.transpose(-2, -1) / math.sqrt(self.dimension_par_tete)
        interdit = masque[:, None, None, :] == 0
        scores = scores.masked_fill(interdit, float("-inf"))

        poids = self.abandon(torch.softmax(scores, dim=-1))
        melange = poids @ valeurs

        assemblees = melange.transpose(1, 2).reshape(lot, longueur, dimension)
        projetees: Tensor = self.projection_sortie(assemblees)
        return projetees


class ReseauParPosition(nn.Module):
    """Transformation non lineaire appliquee a chaque position independamment."""

    def __init__(self, configuration: ConfigurationDuModele) -> None:
        super().__init__()
        self.expansion = nn.Linear(configuration.dimension, configuration.dimension_interne)
        self.contraction = nn.Linear(configuration.dimension_interne, configuration.dimension)
        self.activation = nn.GELU()
        self.abandon = nn.Dropout(configuration.abandon)

    def forward(self, etats: Tensor) -> Tensor:
        transformees: Tensor = self.contraction(
            self.abandon(self.activation(self.expansion(etats)))
        )
        return transformees


class BlocEncodeur(nn.Module):
    """Bloc d'encodage: attention puis transformation par position.

    La normalisation precede chaque sous-couche plutot que de la suivre. Cette
    disposition rend l'entrainement nettement plus stable lorsque le modele est
    appris depuis l'initialisation, ce qui est ici le cas.
    """

    def __init__(self, configuration: ConfigurationDuModele) -> None:
        super().__init__()
        self.normalisation_attention = nn.LayerNorm(configuration.dimension)
        self.attention = AttentionMultiTete(configuration)
        self.normalisation_reseau = nn.LayerNorm(configuration.dimension)
        self.reseau = ReseauParPosition(configuration)
        self.abandon = nn.Dropout(configuration.abandon)

    def forward(self, etats: Tensor, masque: Tensor) -> Tensor:
        attendues: Tensor = self.attention(
            self.normalisation_attention(etats), masque
        )
        residuelles: Tensor = self.abandon(attendues)
        etats = etats + residuelles
        transformees: Tensor = self.reseau(self.normalisation_reseau(etats))
        ajustees: Tensor = self.abandon(transformees)
        return etats + ajustees


class InterpreteDEnonces(nn.Module):
    """Encodeur partage surmonte des tetes d'intention et d'etiquetage."""

    def __init__(self, configuration: ConfigurationDuModele) -> None:
        super().__init__()
        self.configuration = configuration

        self.plongements = nn.Embedding(
            configuration.taille_du_vocabulaire,
            configuration.dimension,
            padding_idx=configuration.indice_de_remplissage,
        )
        self.positions = PositionsApprises(
            configuration.longueur_maximale, configuration.dimension
        )
        self.abandon_entree = nn.Dropout(configuration.abandon)

        self.blocs = nn.ModuleList(
            BlocEncodeur(configuration) for _ in range(configuration.nombre_de_couches)
        )
        self.normalisation_finale = nn.LayerNorm(configuration.dimension)

        self.tete_d_intention = nn.Linear(
            configuration.dimension, configuration.nombre_d_intentions
        )
        self.tete_d_etiquetage = nn.Linear(
            configuration.dimension, configuration.nombre_d_etiquettes
        )

        self.apply(self._initialiser)

    @staticmethod
    def _initialiser(module: nn.Module) -> None:
        """Initialise les parametres selon une loi de faible ecart type.

        Un ecart type reduit maintient les activations dans une plage ou les
        gradients demeurent exploitables au fil des couches, ce qui conditionne
        la convergence d'un modele appris depuis l'initialisation.
        """
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.padding_idx is not None:
                with torch.no_grad():
                    module.weight[module.padding_idx].fill_(0)
        elif isinstance(module, nn.LayerNorm):
            nn.init.ones_(module.weight)
            nn.init.zeros_(module.bias)

    def encoder(self, indices: Tensor, masque: Tensor) -> Tensor:
        """Produit la representation contextuelle de chaque jeton."""
        plonges: Tensor = self.plongements(indices)
        etats: Tensor = self.abandon_entree(plonges + self.positions(indices))
        for bloc in self.blocs:
            etats = bloc(etats, masque)
        normalises: Tensor = self.normalisation_finale(etats)
        return normalises

    def forward(self, indices: Tensor, masque: Tensor) -> SortieDuModele:
        """Restitue les scores d'intention et d'etiquetage.

        Les deux tetes partagent le meme encodeur: la representation servant a
        reconnaitre l'intention est celle qui sert a etiqueter les jetons, ce
        qui fait beneficier chaque tache des regularites apprises pour l'autre.
        """
        etats = self.encoder(indices, masque)
        return SortieDuModele(
            scores_d_intention=self.tete_d_intention(etats[:, 0, :]),
            scores_d_etiquettes=self.tete_d_etiquetage(etats),
        )

    def nombre_de_parametres(self) -> int:
        """Denombre les parametres appris."""
        return sum(parametre.numel() for parametre in self.parameters())


class PerteConjointe(nn.Module):
    """Perte combinant reconnaissance d'intention et etiquetage.

    La combinaison est une somme ponderee: le coefficient regle le poids relatif
    de l'etiquetage, dont les exemples sont bien plus nombreux puisqu'il y a un
    exemple par jeton contre un par enonce.

    Les positions de remplissage sont exclues du calcul: leur inclusion ferait
    apprendre au modele a predire une etiquette pour des jetons qui n'existent
    pas, au detriment des jetons reels.

    Un lissage peut etre applique a la cible d'intention: au lieu d'exiger une
    certitude absolue, la cible repartit une faible masse sur les autres
    classes. Le modele s'interdit ainsi de devenir excessivement confiant sur
    des indices superficiels, ce qui l'incite a fonder sa decision sur
    plusieurs elements de l'enonce.
    """

    def __init__(
        self,
        coefficient_d_etiquetage: float = 1.0,
        lissage_des_etiquettes: float = 0.0,
        indice_ignore: int = -100,
    ) -> None:
        super().__init__()
        self.coefficient = coefficient_d_etiquetage
        self.indice_ignore = indice_ignore
        self.entropie_d_intention = nn.CrossEntropyLoss(
            label_smoothing=lissage_des_etiquettes
        )
        self.entropie_d_etiquetage = nn.CrossEntropyLoss(ignore_index=indice_ignore)

    def forward(
        self,
        sortie: SortieDuModele,
        intentions: Tensor,
        etiquettes: Tensor,
        masque: Tensor,
    ) -> tuple[Tensor, Tensor, Tensor]:
        perte_intention = self.entropie_d_intention(
            sortie.scores_d_intention, intentions
        )

        attendues = etiquettes.masked_fill(masque == 0, self.indice_ignore)
        perte_etiquetage = self.entropie_d_etiquetage(
            sortie.scores_d_etiquettes.reshape(-1, sortie.scores_d_etiquettes.size(-1)),
            attendues.reshape(-1),
        )

        totale = perte_intention + self.coefficient * perte_etiquetage
        return totale, perte_intention, perte_etiquetage


def creer_modele(configuration: ConfigurationDuModele) -> InterpreteDEnonces:
    """Construit le modele et consigne son dimensionnement."""
    modele = InterpreteDEnonces(configuration)
    logger.info(
        "modele construit: %d parametres, %d couches, dimension %d",
        modele.nombre_de_parametres(),
        configuration.nombre_de_couches,
        configuration.dimension,
    )
    return modele
