"""Entrainement et evaluation de la couche d'interpretation.

L'entrainement suit les pratiques etablies pour un modele appris depuis
l'initialisation sur un corpus restreint: echauffement du taux
d'apprentissage, decroissance progressive, ecretage des gradients et arret sur
la validation.

L'echauffement repond a une difficulte propre a ce cas: au demarrage, les
representations sont aleatoires et les gradients erratiques; un taux
d'apprentissage eleve deplacerait les parametres dans une direction que les
lots suivants dementiraient. La montee progressive laisse le modele etablir
des representations exploitables avant d'apprendre vite.

L'arret sur la validation repond au risque de surapprentissage, particulierement
present sur un corpus engendre par patrons: un modele qui memorise les
formulations obtient une justesse elevee en entrainement et s'effondre sur des
tournures inconnues.
"""

import json
import logging
import math
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from random import Random

import torch
from torch import Tensor, nn
from torch.utils.data import DataLoader, Dataset

from .corpus import Corpus, EnonceAnnote
from .modele import (
    ConfigurationDuModele,
    InterpreteDEnonces,
    PerteConjointe,
    creer_modele,
)
from .taxonomie import (
    ETIQUETTE_HORS_ENTITE,
    indices_des_etiquettes,
    indices_des_intentions,
)
from .tokeniseur import JETON_INCONNU, Tokeniseur

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ConfigurationDEntrainement:
    """Parametres de conduite de l'entrainement."""

    epoques: int = 12
    taille_de_lot: int = 32
    taux_d_apprentissage: float = 3e-4
    part_d_echauffement: float = 0.1
    decroissance_des_poids: float = 0.01
    ecretage_des_gradients: float = 1.0
    coefficient_d_etiquetage: float = 2.0
    part_masquee: float = 0.25
    lissage_des_etiquettes: float = 0.1
    patience: int = 5
    progres_minimal: float = 1e-4
    graine: int = 20260812


@dataclass(frozen=True, slots=True)
class Mesures:
    """Grandeurs relevees sur une partition du corpus."""

    perte: float = 0.0
    justesse_d_intention: float = 0.0
    precision_des_entites: float = 0.0
    rappel_des_entites: float = 0.0
    mesure_f1_des_entites: float = 0.0
    justesse_complete: float = 0.0

    def resumer(self) -> str:
        return (
            f"perte {self.perte:.4f} | intention {self.justesse_d_intention:.4f} "
            f"| F1 entites {self.mesure_f1_des_entites:.4f} "
            f"| enonces exacts {self.justesse_complete:.4f}"
        )


@dataclass(frozen=True, slots=True)
class Historique:
    """Suivi de l'entrainement, epoque par epoque."""

    epoques: list[dict[str, float]] = field(default_factory=list)
    meilleure_epoque: int = 0
    meilleures_mesures: Mesures = field(default_factory=Mesures)
    duree_secondes: float = 0.0


class JeuDEnonces(Dataset[dict[str, Tensor]]):
    """Adapte le corpus annote a l'alimentation du modele.

    Un masquage aleatoire peut etre applique a l'entrainement: une fraction des
    jetons est remplacee par le jeton inconnu a chaque passage. Le modele ne
    peut alors s'appuyer sur une formulation exacte et doit reconnaitre une
    intention a partir de plusieurs indices, ce qui limite la memorisation des
    tournures du corpus.

    Le masquage ne s'applique jamais a la validation ni a l'evaluation: la
    mesure doit porter sur les enonces tels qu'ils se presentent.
    """

    def __init__(
        self,
        enonces: Sequence[EnonceAnnote],
        tokeniseur: Tokeniseur,
        part_masquee: float = 0.0,
        graine: int = 20260812,
    ) -> None:
        self._enonces = list(enonces)
        self._tokeniseur = tokeniseur
        self._intentions = indices_des_intentions()
        self._etiquettes = indices_des_etiquettes()
        self._hors_entite = self._etiquettes[ETIQUETTE_HORS_ENTITE]
        self._part_masquee = part_masquee
        self._sort = Random(graine)

    def __len__(self) -> int:
        return len(self._enonces)

    def _masquer(self, jetons: Sequence[str]) -> list[str]:
        """Remplace une fraction des jetons par le jeton inconnu."""
        return [
            JETON_INCONNU if self._sort.random() < self._part_masquee else jeton
            for jeton in jetons
        ]

    def __getitem__(self, rang: int) -> dict[str, Tensor]:
        enonce = self._enonces[rang]
        jetons = (
            self._masquer(enonce.jetons) if self._part_masquee > 0 else enonce.jetons
        )
        encode = self._tokeniseur.encoder(
            jetons,
            [self._etiquettes[etiquette] for etiquette in enonce.etiquettes],
            etiquette_de_remplissage=self._hors_entite,
        )
        return {
            "indices": torch.tensor(encode.indices, dtype=torch.long),
            "masque": torch.tensor(encode.masque, dtype=torch.long),
            "etiquettes": torch.tensor(encode.etiquettes, dtype=torch.long),
            "intention": torch.tensor(
                self._intentions[enonce.intention], dtype=torch.long
            ),
        }


def _planifier(
    optimiseur: torch.optim.Optimizer,
    pas_total: int,
    part_d_echauffement: float,
) -> torch.optim.lr_scheduler.LambdaLR:
    """Etablit l'echauffement puis la decroissance du taux d'apprentissage.

    Le taux croit lineairement pendant l'echauffement, puis decroit selon une
    demi-periode de cosinus. Cette decroissance progressive permet au modele
    d'affiner ses parametres en fin d'entrainement plutot que de continuer a
    les deplacer amplement.
    """
    pas_d_echauffement = max(1, int(pas_total * part_d_echauffement))

    def facteur(pas: int) -> float:
        if pas < pas_d_echauffement:
            return pas / pas_d_echauffement
        avancement = (pas - pas_d_echauffement) / max(
            1, pas_total - pas_d_echauffement
        )
        return 0.5 * (1.0 + math.cos(math.pi * min(1.0, avancement)))

    return torch.optim.lr_scheduler.LambdaLR(optimiseur, facteur)


def extraire_entites(etiquettes: Sequence[str]) -> set[tuple[int, int, str]]:
    """Restitue les entites sous forme d'intervalles types.

    La comparaison porte sur des intervalles complets et non sur des jetons
    isoles: une entite dont un seul jeton est correctement etiquete demeure une
    extraction fausse, puisque la valeur restituee serait tronquee.
    """
    entites: set[tuple[int, int, str]] = set()
    debut = -1
    type_courant = ""

    for rang, etiquette in enumerate(etiquettes):
        if etiquette.startswith("B-"):
            if debut >= 0:
                entites.add((debut, rang - 1, type_courant))
            debut, type_courant = rang, etiquette[2:]
        elif etiquette.startswith("I-") and debut >= 0 and etiquette[2:] == type_courant:
            continue
        else:
            if debut >= 0:
                entites.add((debut, rang - 1, type_courant))
            debut, type_courant = -1, ""

    if debut >= 0:
        entites.add((debut, len(etiquettes) - 1, type_courant))
    return entites


def evaluer(
    modele: InterpreteDEnonces,
    chargeur: DataLoader[dict[str, Tensor]],
    perte_conjointe: PerteConjointe,
    etiquettes_lisibles: Sequence[str],
) -> Mesures:
    """Mesure les performances du modele sur une partition.

    La mesure F1 porte sur les entites completes. La justesse complete exige
    que l'intention et l'integralite des entites soient correctes: c'est la
    seule mesure qui rende compte de l'exploitabilite reelle d'une
    interpretation, une entite manquante suffisant a rendre la situation
    incomplete.
    """
    modele.eval()
    perte_cumulee = 0.0
    lots = 0
    intentions_exactes = 0
    enonces = 0
    enonces_exacts = 0
    entites_correctes = 0
    entites_predites = 0
    entites_attendues = 0

    with torch.no_grad():
        for lot in chargeur:
            sortie = modele(lot["indices"], lot["masque"])
            totale, _, _ = perte_conjointe(
                sortie, lot["intention"], lot["etiquettes"], lot["masque"]
            )
            perte_cumulee += float(totale.item())
            lots += 1

            intentions = sortie.scores_d_intention.argmax(dim=-1)
            etiquettes = sortie.scores_d_etiquettes.argmax(dim=-1)

            for rang in range(lot["indices"].size(0)):
                enonces += 1
                utile = int(lot["masque"][rang].sum().item())
                intention_exacte = bool(
                    intentions[rang].item() == lot["intention"][rang].item()
                )
                intentions_exactes += int(intention_exacte)

                predites = extraire_entites(
                    [
                        etiquettes_lisibles[int(indice)]
                        for indice in etiquettes[rang][1:utile]
                    ]
                )
                attendues = extraire_entites(
                    [
                        etiquettes_lisibles[int(indice)]
                        for indice in lot["etiquettes"][rang][1:utile]
                    ]
                )

                entites_predites += len(predites)
                entites_attendues += len(attendues)
                entites_correctes += len(predites & attendues)
                enonces_exacts += int(intention_exacte and predites == attendues)

    precision = entites_correctes / entites_predites if entites_predites else 0.0
    rappel = entites_correctes / entites_attendues if entites_attendues else 0.0
    mesure_f1 = (
        2 * precision * rappel / (precision + rappel) if precision + rappel else 0.0
    )

    return Mesures(
        perte=perte_cumulee / max(1, lots),
        justesse_d_intention=intentions_exactes / max(1, enonces),
        precision_des_entites=precision,
        rappel_des_entites=rappel,
        mesure_f1_des_entites=mesure_f1,
        justesse_complete=enonces_exacts / max(1, enonces),
    )


def entrainer(
    corpus: Corpus,
    tokeniseur: Tokeniseur,
    configuration_du_modele: ConfigurationDuModele,
    configuration: ConfigurationDEntrainement | None = None,
    destination: Path | None = None,
) -> tuple[InterpreteDEnonces, Historique]:
    """Entraine le modele et restitue celui dont la validation est la meilleure.

    Le modele restitue n'est pas celui de la derniere epoque mais celui dont la
    justesse de validation fut la plus elevee: poursuivre au-dela ne ferait que
    memoriser davantage le corpus d'entrainement.
    """
    reglages = configuration or ConfigurationDEntrainement()
    torch.manual_seed(reglages.graine)

    etiquettes_lisibles = list(indices_des_etiquettes())
    modele = creer_modele(configuration_du_modele)
    perte_conjointe = PerteConjointe(
        reglages.coefficient_d_etiquetage, reglages.lissage_des_etiquettes
    )

    chargeur_entrainement = DataLoader(
        JeuDEnonces(
            corpus.entrainement,
            tokeniseur,
            part_masquee=reglages.part_masquee,
            graine=reglages.graine,
        ),
        batch_size=reglages.taille_de_lot,
        shuffle=True,
    )
    chargeur_validation = DataLoader(
        JeuDEnonces(corpus.validation, tokeniseur),
        batch_size=reglages.taille_de_lot,
    )

    optimiseur = torch.optim.AdamW(
        modele.parameters(),
        lr=reglages.taux_d_apprentissage,
        weight_decay=reglages.decroissance_des_poids,
    )
    planificateur = _planifier(
        optimiseur,
        len(chargeur_entrainement) * reglages.epoques,
        reglages.part_d_echauffement,
    )

    suivi: list[dict[str, float]] = []
    meilleure = -1.0
    meilleure_perte = float("inf")
    meilleures_mesures = Mesures()
    meilleure_epoque = 0
    meilleurs_parametres = {
        nom: valeur.clone() for nom, valeur in modele.state_dict().items()
    }
    epoques_sans_progres = 0
    debut = time.perf_counter()

    for epoque in range(1, reglages.epoques + 1):
        modele.train()
        perte_cumulee = 0.0

        for lot in chargeur_entrainement:
            optimiseur.zero_grad(set_to_none=True)
            sortie = modele(lot["indices"], lot["masque"])
            totale, _, _ = perte_conjointe(
                sortie, lot["intention"], lot["etiquettes"], lot["masque"]
            )
            totale.backward()
            nn.utils.clip_grad_norm_(
                modele.parameters(), reglages.ecretage_des_gradients
            )
            optimiseur.step()
            planificateur.step()
            perte_cumulee += float(totale.item())

        mesures = evaluer(
            modele, chargeur_validation, perte_conjointe, etiquettes_lisibles
        )
        suivi.append(
            {
                "epoque": epoque,
                "perte_entrainement": perte_cumulee / max(1, len(chargeur_entrainement)),
                "perte_validation": mesures.perte,
                "justesse_d_intention": mesures.justesse_d_intention,
                "mesure_f1_des_entites": mesures.mesure_f1_des_entites,
                "justesse_complete": mesures.justesse_complete,
            }
        )
        logger.info("epoque %d: %s", epoque, mesures.resumer())

        if mesures.justesse_complete > meilleure:
            meilleure = mesures.justesse_complete
            meilleures_mesures = mesures
            meilleure_epoque = epoque
            meilleurs_parametres = {
                nom: valeur.clone() for nom, valeur in modele.state_dict().items()
            }

        if mesures.perte < meilleure_perte - reglages.progres_minimal:
            meilleure_perte = mesures.perte
            epoques_sans_progres = 0
        else:
            epoques_sans_progres += 1
            if epoques_sans_progres >= reglages.patience:
                logger.info(
                    "arret apres %d epoques sans reduction de la perte de validation",
                    epoques_sans_progres,
                )
                break

    modele.load_state_dict(meilleurs_parametres)
    historique = Historique(
        epoques=suivi,
        meilleure_epoque=meilleure_epoque,
        meilleures_mesures=meilleures_mesures,
        duree_secondes=time.perf_counter() - debut,
    )

    if destination is not None:
        enregistrer(modele, tokeniseur, configuration_du_modele, historique, destination)

    return modele, historique


def enregistrer(
    modele: InterpreteDEnonces,
    tokeniseur: Tokeniseur,
    configuration: ConfigurationDuModele,
    historique: Historique,
    destination: Path,
) -> None:
    """Consigne le modele, son vocabulaire et son historique.

    Les trois sont indissociables: des parametres sans vocabulaire sont
    inexploitables, et sans historique on ignore comment ils furent obtenus.
    """
    destination.mkdir(parents=True, exist_ok=True)
    torch.save(modele.state_dict(), destination / "parametres.pt")
    tokeniseur.enregistrer(destination / "vocabulaire.json")
    (destination / "configuration.json").write_text(
        json.dumps(asdict(configuration), indent=2), encoding="utf-8"
    )
    (destination / "historique.json").write_text(
        json.dumps(
            {
                "epoques": historique.epoques,
                "meilleure_epoque": historique.meilleure_epoque,
                "meilleures_mesures": asdict(historique.meilleures_mesures),
                "duree_secondes": historique.duree_secondes,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("modele consigne dans %s", destination)


def charger(destination: Path) -> tuple[InterpreteDEnonces, Tokeniseur]:
    """Restitue un modele consigne et son vocabulaire."""
    configuration = ConfigurationDuModele(
        **json.loads((destination / "configuration.json").read_text(encoding="utf-8"))
    )
    modele = creer_modele(configuration)
    modele.load_state_dict(
        torch.load(destination / "parametres.pt", map_location="cpu")
    )
    modele.eval()
    return modele, Tokeniseur.charger(destination / "vocabulaire.json")
