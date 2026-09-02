"""Specialisation d'un encodeur preentraine sur le domaine.

Les reglages different de ceux employes pour un modele appris depuis
l'initialisation. Le taux d'apprentissage est reduit d'un ordre de grandeur:
un encodeur preentraine porte des representations acquises sur un volume de
texte considerable, qu'un taux eleve deteriorerait avant que le modele n'ait
appris la tache. Le nombre d'epoques est reduit pour la meme raison: la
convergence intervient rapidement, et poursuivre ferait perdre les regularites
generales au profit des particularites du corpus de domaine.

Les couches basses demeurent figees. Elles portent des regularites de la
langue qu'un corpus de dix mille enonces engendres par patrons ne saurait
ameliorer; les ajuster les degraderait tout en multipliant le calcul.
"""

import json
import logging
import math
import tempfile
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch import Tensor, nn
from torch.utils.data import DataLoader, Dataset

from .corpus import Corpus, EnonceAnnote
from .entrainement import Historique, Mesures, extraire_entites
from .modele_preentraine import (
    ConfigurationPreentrainee,
    InterpretePreentraine,
    PerteConjointeAlignee,
    creer_modele_preentraine,
)
from .taxonomie import etiquettes_bio, indices_des_etiquettes, indices_des_intentions
from .tokeniseur_aligne import INDICE_IGNORE, TokeniseurAligne

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ConfigurationDeSpecialisation:
    """Parametres de specialisation d'un encodeur preentraine."""

    epoques: int = 4
    taille_de_lot: int = 16
    taux_d_apprentissage: float = 2e-5
    taux_des_tetes: float = 1e-3
    part_d_echauffement: float = 0.1
    decroissance_des_poids: float = 0.01
    ecretage_des_gradients: float = 1.0
    coefficient_d_etiquetage: float = 2.0
    lissage_des_etiquettes: float = 0.1
    patience: int = 2
    progres_minimal: float = 1e-4
    graine: int = 20260812


class JeuSegmente(Dataset[dict[str, Tensor]]):
    """Adapte le corpus annote a un encodeur a sous-unites."""

    def __init__(
        self, enonces: Sequence[EnonceAnnote], tokeniseur: TokeniseurAligne
    ) -> None:
        self._enonces = list(enonces)
        self._tokeniseur = tokeniseur
        self._intentions = indices_des_intentions()
        self._etiquettes = indices_des_etiquettes()

    def __len__(self) -> int:
        return len(self._enonces)

    def __getitem__(self, rang: int) -> dict[str, Tensor]:
        enonce = self._enonces[rang]
        segmente = self._tokeniseur.encoder(
            enonce.jetons,
            [self._etiquettes[etiquette] for etiquette in enonce.etiquettes],
        )
        return {
            "indices": torch.tensor(segmente.indices, dtype=torch.long),
            "masque": torch.tensor(segmente.masque, dtype=torch.long),
            "etiquettes": torch.tensor(segmente.etiquettes, dtype=torch.long),
            "intention": torch.tensor(
                self._intentions[enonce.intention], dtype=torch.long
            ),
        }


def _optimiseur_par_groupes(
    modele: InterpretePreentraine, reglages: ConfigurationDeSpecialisation
) -> torch.optim.Optimizer:
    """Constitue un optimiseur distinguant l'encodeur des tetes.

    Les tetes sont initialisees de zero et doivent apprendre vite; l'encodeur
    porte des representations acquises et ne doit etre ajuste qu'avec
    parcimonie. Un taux unique conviendrait mal aux deux.
    """
    parametres_des_tetes = list(modele.tete_d_intention.parameters()) + list(
        modele.tete_d_etiquetage.parameters()
    )
    references = {id(parametre) for parametre in parametres_des_tetes}
    parametres_de_l_encodeur = [
        parametre
        for parametre in modele.parameters()
        if parametre.requires_grad and id(parametre) not in references
    ]

    return torch.optim.AdamW(
        [
            {
                "params": parametres_de_l_encodeur,
                "lr": reglages.taux_d_apprentissage,
            },
            {"params": parametres_des_tetes, "lr": reglages.taux_des_tetes},
        ],
        weight_decay=reglages.decroissance_des_poids,
    )


def _planifier(
    optimiseur: torch.optim.Optimizer, pas_total: int, part_d_echauffement: float
) -> torch.optim.lr_scheduler.LambdaLR:
    """Etablit l'echauffement puis la decroissance du taux d'apprentissage."""
    pas_d_echauffement = max(1, int(pas_total * part_d_echauffement))

    def facteur(pas: int) -> float:
        if pas < pas_d_echauffement:
            return pas / pas_d_echauffement
        avancement = (pas - pas_d_echauffement) / max(1, pas_total - pas_d_echauffement)
        return 0.5 * (1.0 + math.cos(math.pi * min(1.0, avancement)))

    return torch.optim.lr_scheduler.LambdaLR(optimiseur, facteur)


def evaluer_segmente(
    modele: InterpretePreentraine,
    chargeur: DataLoader[dict[str, Tensor]],
    perte_conjointe: PerteConjointeAlignee,
) -> Mesures:
    """Mesure les performances sur une partition segmentee en sous-unites.

    Les positions portant l'indice ignore sont ecartees: elles correspondent
    aux morceaux de mot autres que le premier, dont la prediction n'a jamais
    contribue a l'apprentissage.
    """
    modele.eval()
    noms = etiquettes_bio()
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
                intention_exacte = bool(
                    intentions[rang].item() == lot["intention"][rang].item()
                )
                intentions_exactes += int(intention_exacte)

                retenues = [
                    position
                    for position in range(lot["etiquettes"].size(1))
                    if int(lot["etiquettes"][rang][position].item()) != INDICE_IGNORE
                ]
                predites = extraire_entites(
                    [noms[int(etiquettes[rang][position])] for position in retenues]
                )
                attendues = extraire_entites(
                    [
                        noms[int(lot["etiquettes"][rang][position])]
                        for position in retenues
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


def specialiser(
    corpus: Corpus,
    tokeniseur: TokeniseurAligne,
    configuration_du_modele: ConfigurationPreentrainee,
    configuration: ConfigurationDeSpecialisation | None = None,
    destination: Path | None = None,
) -> tuple[InterpretePreentraine, Historique]:
    """Specialise l'encodeur preentraine et restitue le meilleur modele.

    Les meilleurs parametres sont conserves sur disque et non en memoire. Une
    copie occupe plus de quatre cents megaoctets que le systeme ne restitue
    pas lorsqu'elle est liberee: leur accumulation au fil des epoques epuise
    la memoire disponible.

    Le modele est en outre consigne des qu'il progresse: une interruption
    laisse ainsi un modele exploitable plutot que de perdre le calcul accompli.
    """
    reglages = configuration or ConfigurationDeSpecialisation()
    torch.manual_seed(reglages.graine)

    modele = creer_modele_preentraine(configuration_du_modele)
    perte_conjointe = PerteConjointeAlignee(
        reglages.coefficient_d_etiquetage, reglages.lissage_des_etiquettes
    )

    chargeur_entrainement = DataLoader(
        JeuSegmente(corpus.entrainement, tokeniseur),
        batch_size=reglages.taille_de_lot,
        shuffle=True,
    )
    chargeur_validation = DataLoader(
        JeuSegmente(corpus.validation, tokeniseur),
        batch_size=reglages.taille_de_lot,
    )

    optimiseur = _optimiseur_par_groupes(modele, reglages)
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
    epoques_sans_progres = 0
    debut = time.perf_counter()

    abri = tempfile.TemporaryDirectory(prefix="specialisation-")
    chemin_des_meilleurs = Path(abri.name) / "meilleurs.pt"
    torch.save(modele.state_dict(), chemin_des_meilleurs)

    for epoque in range(1, reglages.epoques + 1):
        modele.train()
        perte_cumulee = 0.0

        for rang, lot in enumerate(chargeur_entrainement, start=1):
            if rang % 40 == 0:
                logger.debug(
                    "epoque %d: %d/%d lots traites",
                    epoque,
                    rang,
                    len(chargeur_entrainement),
                )
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

        mesures = evaluer_segmente(modele, chargeur_validation, perte_conjointe)
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
        logger.info(
            "epoque %d/%d  %s  (%.0f s ecoulees)",
            epoque,
            reglages.epoques,
            mesures.resumer(),
            time.perf_counter() - debut,
        )

        if mesures.justesse_complete > meilleure:
            meilleure = mesures.justesse_complete
            meilleures_mesures = mesures
            meilleure_epoque = epoque
            torch.save(modele.state_dict(), chemin_des_meilleurs)
            if destination is not None:
                enregistrer_specialise(
                    modele,
                    tokeniseur,
                    configuration_du_modele,
                    Historique(
                        epoques=suivi,
                        meilleure_epoque=epoque,
                        meilleures_mesures=mesures,
                        duree_secondes=time.perf_counter() - debut,
                    ),
                    destination,
                )

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

    modele.load_state_dict(torch.load(chemin_des_meilleurs, map_location="cpu"))
    abri.cleanup()

    historique = Historique(
        epoques=suivi,
        meilleure_epoque=meilleure_epoque,
        meilleures_mesures=meilleures_mesures,
        duree_secondes=time.perf_counter() - debut,
    )

    if destination is not None:
        enregistrer_specialise(
            modele, tokeniseur, configuration_du_modele, historique, destination
        )

    return modele, historique


def enregistrer_specialise(
    modele: InterpretePreentraine,
    tokeniseur: TokeniseurAligne,
    configuration: ConfigurationPreentrainee,
    historique: Historique,
    destination: Path,
) -> None:
    """Consigne le modele specialise, son segmenteur et son historique."""
    destination.mkdir(parents=True, exist_ok=True)
    torch.save(modele.state_dict(), destination / "parametres.pt")
    tokeniseur.enregistrer(destination / "segmenteur")
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
    logger.info("modele specialise consigne dans %s", destination)


def charger_specialise(
    destination: Path,
) -> tuple[InterpretePreentraine, TokeniseurAligne]:
    """Restitue un modele specialise et son segmenteur."""
    configuration = ConfigurationPreentrainee(
        **json.loads((destination / "configuration.json").read_text(encoding="utf-8"))
    )
    modele = creer_modele_preentraine(configuration)
    modele.load_state_dict(torch.load(destination / "parametres.pt", map_location="cpu"))
    modele.eval()
    return modele, TokeniseurAligne(
        configuration.encodeur, configuration.longueur_maximale
    )
