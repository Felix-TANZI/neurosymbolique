"""Interpretation d'un enonce par le modele fonde sur un encodeur preentraine.

L'interpretation suit la meme demarche que celle du modele appris depuis
l'initialisation, mais opere sur des sous-unites: les predictions sont d'abord
ramenees aux mots d'origine, puis assemblees en entites.

La restitution produit une interpretation de meme forme que celle du premier
modele, de sorte que la verification symbolique et les composants qui
l'emploient demeurent inchanges.
"""

import logging
from collections.abc import Sequence

import torch
from torch import Tensor

from .inference import (
    CONFIANCE_MINIMALE,
    EntiteExtraite,
    Interpretation,
    MotifDeReserve,
    Recevabilite,
    Reserve,
    entite_essentielle,
)
from .modele_preentraine import InterpretePreentraine
from .taxonomie import (
    ENTITES_ATTENDUES,
    ETIQUETTE_HORS_ENTITE,
    Intention,
    etiquettes_bio,
)
from .tokeniseur import segmenter
from .tokeniseur_aligne import TokeniseurAligne

logger = logging.getLogger(__name__)


class InterpretePreentraineDEnonces:
    """Applique le modele preentraine a un enonce et en restitue la lecture."""

    def __init__(
        self,
        modele: InterpretePreentraine,
        tokeniseur: TokeniseurAligne,
        confiance_minimale: float = CONFIANCE_MINIMALE,
    ) -> None:
        self._modele = modele
        self._tokeniseur = tokeniseur
        self._confiance_minimale = confiance_minimale
        self._intentions = list(Intention)
        self._etiquettes = etiquettes_bio()
        self._modele.eval()

    def interpreter(self, enonce: str) -> Interpretation:
        """Etablit l'intention et les entites d'un enonce."""
        mots = segmenter(enonce)
        if not mots:
            return Interpretation(
                enonce=enonce,
                intention="",
                confiance_d_intention=0.0,
                reserves=(
                    Reserve(MotifDeReserve.HORS_PERIMETRE.value, "enonce vide"),
                ),
                recevabilite=Recevabilite.IRRECEVABLE.value,
            )

        segmente = self._tokeniseur.encoder(mots)
        indices = torch.tensor([segmente.indices], dtype=torch.long)
        masque = torch.tensor([segmente.masque], dtype=torch.long)

        with torch.no_grad():
            sortie = self._modele(indices, masque)

        intention, confiance = self._lire_intention(sortie.scores_d_intention[0])
        positions = segmente.positions_des_mots
        etiquettes, confiances = self._lire_par_mot(
            sortie.scores_d_etiquettes[0], positions
        )

        return self._qualifier(
            Interpretation(
                enonce=enonce,
                intention=intention,
                confiance_d_intention=confiance,
                entites=self._assembler(mots, etiquettes, confiances),
            )
        )

    def _lire_intention(self, scores: Tensor) -> tuple[str, float]:
        """Retient l'intention la plus probable et sa confiance."""
        probabilites = torch.softmax(scores, dim=-1)
        confiance, rang = probabilites.max(dim=-1)
        return self._intentions[int(rang.item())].value, float(confiance.item())

    def _lire_par_mot(
        self, scores: Tensor, positions: Sequence[int]
    ) -> tuple[list[str], list[float]]:
        """Ramene les predictions par sous-unite a une prediction par mot.

        Seule la prediction du premier morceau est retenue: c'est elle qui a
        contribue a l'apprentissage, les suivantes n'ayant jamais ete
        evaluees.
        """
        probabilites = torch.softmax(scores, dim=-1)
        confiances, rangs = probabilites.max(dim=-1)

        return (
            [self._etiquettes[int(rangs[position])] for position in positions],
            [float(confiances[position]) for position in positions],
        )

    def _assembler(
        self,
        mots: Sequence[str],
        etiquettes: Sequence[str],
        confiances: Sequence[float],
    ) -> tuple[EntiteExtraite, ...]:
        """Assemble les mots etiquetes en entites completes."""
        extraites: list[EntiteExtraite] = []
        courants: list[str] = []
        confiances_courantes: list[float] = []
        type_courant = ""
        debut = 0

        for rang in range(min(len(mots), len(etiquettes))):
            etiquette = etiquettes[rang]

            if etiquette == ETIQUETTE_HORS_ENTITE:
                if courants:
                    extraites.append(
                        self._entite(
                            type_courant, courants, confiances_courantes, debut, rang
                        )
                    )
                    courants, confiances_courantes, type_courant = [], [], ""
                continue

            type_annonce = etiquette[2:]
            ouverture = etiquette.startswith("B-") or type_annonce != type_courant

            if ouverture and courants:
                extraites.append(
                    self._entite(
                        type_courant, courants, confiances_courantes, debut, rang
                    )
                )
                courants, confiances_courantes = [], []

            if ouverture:
                debut, type_courant = rang, type_annonce

            courants.append(mots[rang])
            confiances_courantes.append(confiances[rang])

        if courants:
            extraites.append(
                self._entite(
                    type_courant,
                    courants,
                    confiances_courantes,
                    debut,
                    min(len(mots), len(etiquettes)),
                )
            )

        return tuple(extraites)

    @staticmethod
    def _entite(
        type_d_entite: str,
        mots: Sequence[str],
        confiances: Sequence[float],
        debut: int,
        fin: int,
    ) -> EntiteExtraite:
        """Constitue une entite a partir de ses mots.

        Les references sont recollees sans espace: un identifiant segmente en
        lettres, separateurs et chiffres doit etre restitue sous la forme que
        l'etablissement enregistre, faute de quoi la verification symbolique
        ne trouverait aucune correspondance.

        Les designations composees de mots demeurent espacees: un secteur tel
        que "etage 3" ou une localisation telle que "sous le lavabo" perdrait
        son sens une fois recollee.
        """
        composee = any(
            len(mot) > 1 and mot.isalpha() for mot in mots
        )
        valeur = " ".join(mots) if composee else "".join(mots)

        return EntiteExtraite(
            type_d_entite=type_d_entite,
            valeur=valeur.upper() if not composee and any(
                mot.isalpha() for mot in mots
            ) else valeur,
            confiance=min(confiances) if confiances else 0.0,
            debut=debut,
            fin=fin,
        )

    def _qualifier(self, interpretation: Interpretation) -> Interpretation:
        """Etablit la recevabilite au regard de la confiance et des attentes."""
        reserves: list[Reserve] = []

        if interpretation.confiance_d_intention < self._confiance_minimale:
            reserves.append(
                Reserve(
                    MotifDeReserve.CONFIANCE_INSUFFISANTE.value,
                    f"{interpretation.confiance_d_intention:.2f}",
                )
            )

        attendues = ENTITES_ATTENDUES.get(
            Intention(interpretation.intention), frozenset()
        )
        obtenues = {entite.type_d_entite for entite in interpretation.entites}
        essentielle = entite_essentielle(attendues)

        if essentielle is not None and essentielle.value not in obtenues:
            reserves.append(
                Reserve(MotifDeReserve.ENTITE_MANQUANTE.value, essentielle.value)
            )

        return Interpretation(
            enonce=interpretation.enonce,
            intention=interpretation.intention,
            confiance_d_intention=interpretation.confiance_d_intention,
            entites=interpretation.entites,
            reserves=tuple(reserves),
            recevabilite=(
                Recevabilite.RECEVABLE.value
                if not reserves
                else Recevabilite.A_CONFIRMER.value
            ),
        )
