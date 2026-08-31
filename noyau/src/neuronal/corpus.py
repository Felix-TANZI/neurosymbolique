"""Constitution du corpus d'apprentissage de la couche d'interpretation.

Le corpus est engendre par instanciation de patrons de formulation avec les
entites de l'etablissement. L'annotation en decoule mecaniquement: la position
d'une entite dans le patron determine son etiquetage, ce qui exclut toute
erreur d'annotation.

Trois precautions repondent au risque, documente dans la litterature, qu'un
modele entraine sur des patrons apprenne les patrons plutot que la langue.
Les formulations d'evaluation sont disjointes de celles d'entrainement, de
sorte qu'une justesse elevee mesure une generalisation et non une
memorisation. Des perturbations lexicales reproduisent les ecarts observes
dans une saisie reelle. La partition est figee par une graine consignee, ce
qui rend l'experience reproductible par un tiers.
"""

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from random import Random

from .patrons import PATRONS_ENTRAINEMENT, PATRONS_EVALUATION
from .taxonomie import ETIQUETTE_HORS_ENTITE, Intention, TypeDEntite
from .tokeniseur import segmenter

logger = logging.getLogger(__name__)

MARQUEUR = re.compile(r"\{([a-z_]+)\}")

LOCALISATIONS: tuple[str, ...] = (
    "sous le lavabo",
    "dans la salle de bain",
    "au plafond",
    "sous la fenetre",
    "derriere le lit",
    "dans le couloir",
    "sous la douche",
    "pres du radiateur",
)

EQUIPEMENTS_EXPRIMES: tuple[str, ...] = (
    "lit double",
    "lit king",
    "acces pmr",
    "baignoire",
    "balcon",
    "climatisation",
    "coffre fort",
)

HEURES_EXPRIMEES: tuple[str, ...] = (
    "13h",
    "13h30",
    "14h",
    "midi",
    "11h",
    "15h",
    "16h30",
    "en debut d'apres midi",
)


class CorpusInvalideError(ValueError):
    """Signale un corpus dont les annotations ne sont pas exploitables."""


@dataclass(frozen=True, slots=True)
class EnonceAnnote:
    """Enonce accompagne de son intention et de l'etiquetage de ses jetons.

    L'invariant central est l'alignement: chaque jeton porte exactement une
    etiquette. Un desalignement produirait un apprentissage sur des
    correspondances fausses.
    """

    texte: str
    intention: str
    jetons: tuple[str, ...]
    etiquettes: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.jetons) != len(self.etiquettes):
            raise CorpusInvalideError(
                f"desalignement sur l'enonce {self.texte!r}: "
                f"{len(self.jetons)} jetons, {len(self.etiquettes)} etiquettes"
            )
        if not self.jetons:
            raise CorpusInvalideError("un enonce ne peut etre vide")

    @property
    def entites(self) -> tuple[tuple[str, str], ...]:
        """Restitue les entites extraites sous forme de couples type et valeur."""
        extraites: list[tuple[str, str]] = []
        courante: list[str] = []
        type_courant = ""

        for jeton, etiquette in zip(self.jetons, self.etiquettes, strict=True):
            if etiquette.startswith("B-"):
                if courante:
                    extraites.append((type_courant, " ".join(courante)))
                type_courant = etiquette[2:]
                courante = [jeton]
            elif etiquette.startswith("I-") and courante:
                courante.append(jeton)
            else:
                if courante:
                    extraites.append((type_courant, " ".join(courante)))
                    courante = []
                    type_courant = ""

        if courante:
            extraites.append((type_courant, " ".join(courante)))
        return tuple(extraites)


@dataclass(frozen=True, slots=True)
class Corpus:
    """Partition figee du corpus d'apprentissage."""

    entrainement: tuple[EnonceAnnote, ...] = ()
    validation: tuple[EnonceAnnote, ...] = ()
    evaluation: tuple[EnonceAnnote, ...] = ()
    graine: int = 0
    vocabulaire_entites: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def resumer(self) -> dict[str, int]:
        """Restitue les grandeurs caracteristiques de la partition."""
        return {
            "entrainement": len(self.entrainement),
            "validation": len(self.validation),
            "evaluation": len(self.evaluation),
            "intentions": len({e.intention for e in self.entrainement}),
        }

    def repartition_des_intentions(self) -> dict[str, int]:
        """Denombre les enonces d'entrainement par intention."""
        comptes: dict[str, int] = {}
        for enonce in self.entrainement:
            comptes[enonce.intention] = comptes.get(enonce.intention, 0) + 1
        return dict(sorted(comptes.items()))


class GenerateurDeCorpus:
    """Engendre un corpus annote a partir de patrons et d'entites reelles."""

    def __init__(
        self,
        entites: Mapping[str, Sequence[str]],
        graine: int = 20260812,
        part_perturbees: float = 0.18,
    ) -> None:
        self._entites = entites
        self._sort = Random(graine)
        self._graine = graine
        self._part_perturbees = part_perturbees

    def engendrer(
        self, par_intention: int = 800, part_validation: float = 0.15
    ) -> Corpus:
        """Produit la partition complete du corpus.

        Le jeu d'evaluation est engendre a partir de formulations disjointes:
        il mesure la capacite du modele a traiter des enonces dont la
        structure lui est inconnue.
        """
        entrainement = self._engendrer_depuis(
            PATRONS_ENTRAINEMENT, par_intention, perturber=True
        )
        evaluation = self._engendrer_depuis(
            PATRONS_EVALUATION, max(par_intention // 6, 40), perturber=True
        )

        self._sort.shuffle(entrainement)
        rupture = int(len(entrainement) * (1 - part_validation))

        corpus = Corpus(
            entrainement=tuple(entrainement[:rupture]),
            validation=tuple(entrainement[rupture:]),
            evaluation=tuple(evaluation),
            graine=self._graine,
            vocabulaire_entites={
                nom: tuple(valeurs) for nom, valeurs in self._entites.items()
            },
        )
        logger.info("corpus engendre: %s", corpus.resumer())
        return corpus

    def _engendrer_depuis(
        self,
        patrons: Mapping[Intention, tuple[str, ...]],
        par_intention: int,
        perturber: bool,
    ) -> list[EnonceAnnote]:
        """Instancie chaque patron autant de fois que necessaire."""
        engendres: list[EnonceAnnote] = []

        for intention, formulations in patrons.items():
            if not formulations:
                continue
            for rang in range(par_intention):
                patron = formulations[rang % len(formulations)]
                enonce = self._instancier(patron, intention)
                if perturber and self._sort.random() < self._part_perturbees:
                    enonce = self._perturber(enonce)
                engendres.append(enonce)

        return engendres

    def _instancier(self, patron: str, intention: Intention) -> EnonceAnnote:
        """Remplit un patron et en derive l'annotation.

        L'annotation est construite au fil du remplissage: chaque valeur
        inseree est segmentee et etiquetee immediatement, ce qui garantit
        l'alignement sans recherche ulterieure dans le texte.
        """
        jetons: list[str] = []
        etiquettes: list[str] = []
        position = 0

        for marqueur in MARQUEUR.finditer(patron):
            avant = patron[position : marqueur.start()]
            for jeton in segmenter(avant):
                jetons.append(jeton)
                etiquettes.append(ETIQUETTE_HORS_ENTITE)

            type_entite = marqueur.group(1)
            valeur = self._tirer_valeur(type_entite)
            for rang, jeton in enumerate(segmenter(valeur)):
                jetons.append(jeton)
                etiquettes.append(
                    f"{'B' if rang == 0 else 'I'}-{type_entite}"
                )
            position = marqueur.end()

        for jeton in segmenter(patron[position:]):
            jetons.append(jeton)
            etiquettes.append(ETIQUETTE_HORS_ENTITE)

        return EnonceAnnote(
            texte=" ".join(jetons),
            intention=intention.value,
            jetons=tuple(jetons),
            etiquettes=tuple(etiquettes),
        )

    def _tirer_valeur(self, type_entite: str) -> str:
        """Tire une valeur pour un type d'entite donne."""
        if type_entite == TypeDEntite.LOCALISATION.value:
            return self._sort.choice(LOCALISATIONS)
        if type_entite == TypeDEntite.EQUIPEMENT.value:
            return self._sort.choice(EQUIPEMENTS_EXPRIMES)
        if type_entite == TypeDEntite.HEURE.value:
            return self._sort.choice(HEURES_EXPRIMEES)

        valeurs = self._entites.get(type_entite)
        if not valeurs:
            raise CorpusInvalideError(
                f"aucune valeur disponible pour le type d'entite {type_entite}"
            )
        return self._sort.choice(list(valeurs))

    def _perturber(self, enonce: EnonceAnnote) -> EnonceAnnote:
        """Applique une perturbation lexicale reproduisant une saisie reelle.

        Les perturbations ne portent jamais sur les jetons etiquetes: alterer
        une entite invaliderait son annotation, alors qu'alterer le contexte
        reproduit fidelement les ecarts de saisie observes.
        """
        modifiables = [
            rang
            for rang, etiquette in enumerate(enonce.etiquettes)
            if etiquette == ETIQUETTE_HORS_ENTITE and len(enonce.jetons[rang]) > 3
        ]
        if not modifiables:
            return enonce

        rang = self._sort.choice(modifiables)
        jetons = list(enonce.jetons)
        jetons[rang] = self._alterer(jetons[rang])

        return EnonceAnnote(
            texte=" ".join(jetons),
            intention=enonce.intention,
            jetons=tuple(jetons),
            etiquettes=enonce.etiquettes,
        )

    def _alterer(self, jeton: str) -> str:
        """Altere un jeton comme le ferait une saisie hative."""
        procede = self._sort.choice(("omission", "transposition", "doublement"))
        position = self._sort.randrange(1, len(jeton) - 1)

        if procede == "omission":
            return jeton[:position] + jeton[position + 1 :]
        if procede == "doublement":
            return jeton[:position] + jeton[position] + jeton[position:]
        return (
            jeton[: position - 1]
            + jeton[position]
            + jeton[position - 1]
            + jeton[position + 1 :]
        )


def verifier(corpus: Corpus) -> dict[str, int]:
    """Verifie les invariants du corpus et restitue ses grandeurs.

    La verification porte sur l'alignement, la disjonction des partitions et
    la coherence du schema BIO. Un corpus dont les invariants sont rompus
    produirait un modele appris sur des correspondances fausses.
    """
    for partition in (corpus.entrainement, corpus.validation, corpus.evaluation):
        for enonce in partition:
            _verifier_bio(enonce)

    textes_entrainement = {e.texte for e in corpus.entrainement}
    textes_validation = {e.texte for e in corpus.validation}
    textes_evaluation = {e.texte for e in corpus.evaluation}

    if textes_entrainement & textes_evaluation:
        raise CorpusInvalideError(
            "des enonces d'evaluation figurent dans l'entrainement: "
            "la mesure ne distinguerait plus generalisation et memorisation"
        )

    return {
        **corpus.resumer(),
        "enonces_distincts_entrainement": len(textes_entrainement),
        "enonces_distincts_validation": len(textes_validation),
        "enonces_distincts_evaluation": len(textes_evaluation),
    }


def _verifier_bio(enonce: EnonceAnnote) -> None:
    """Verifie qu'une etiquette de continuation suit bien son ouverture."""
    precedente = ETIQUETTE_HORS_ENTITE
    for etiquette in enonce.etiquettes:
        if etiquette.startswith("I-"):
            attendue = {f"B-{etiquette[2:]}", f"I-{etiquette[2:]}"}
            if precedente not in attendue:
                raise CorpusInvalideError(
                    f"etiquette de continuation isolee sur {enonce.texte!r}"
                )
        precedente = etiquette
