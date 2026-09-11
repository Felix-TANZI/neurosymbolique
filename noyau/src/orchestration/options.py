"""Production de plusieurs options d'affectation et de ce qui les distingue.

Une decision critique ne se reduit pas a une proposition unique. Le responsable
arbitre entre des considerations que le systeme ne connait pas: un engagement
commercial, une reclamation en cours, une consigne du jour. Lui soumettre
plusieurs options assorties de leurs contreparties lui restitue cet arbitrage,
la ou une proposition unique le lui retirerait.

Les options sont obtenues en interrogeant le moteur successivement, chaque
option retenue etant ecartee du parc soumis a la suivante. Ce procede garantit
que chaque option est optimale au regard de ce qui demeurait disponible, et non
choisie arbitrairement parmi les admissibles.

Ce qui distingue deux options est etabli par comparaison de leurs penalites:
une option qui n'encourt pas une penalite que l'autre subit s'en trouve
avantagee sur ce point precis. La distinction est ainsi derivee de la trace du
raisonnement, et non formulee apres coup.
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from src.domaine import Chambre, NumeroChambre

from .affectation import AffecterChambre, Demande, Recommandation

logger = logging.getLogger(__name__)

OPTIONS_PAR_DEFAUT = 3

AVANTAGES: Mapping[str, str] = {
    "proximite": "elle est plus proche de la chambre demandee",
    "hors_de_portee": "elle se situe a l'etage demande",
    "eloignement": "elle s'ecarte davantage de la chambre a eviter",
    "etage_non_souhaite": "elle se trouve a l'etage souhaite",
    "souhait_non_satisfait": "elle satisfait une preference supplementaire",
    "surclassement": "elle correspond mieux a la categorie contractee",
    "hors_secteur": "elle demeure dans le secteur de nettoyage courant",
}

CONTREPARTIES: Mapping[str, str] = {
    "proximite": "elle s'eloigne de la chambre demandee",
    "hors_de_portee": "elle se situe a un autre etage",
    "eloignement": "elle demeure proche de la chambre a eviter",
    "etage_non_souhaite": "elle n'est pas a l'etage souhaite",
    "souhait_non_satisfait": "une preference demeure insatisfaite",
    "surclassement": "elle surclasse le client, au prix d'un manque a gagner",
    "hors_secteur": "elle sort du secteur de nettoyage courant",
}


@dataclass(frozen=True, slots=True)
class Option:
    """Affectation possible, avec son cout et ce qui la distingue.

    Le rang traduit l'ordre etabli par le moteur: l'option de rang un est celle
    qu'il retient lorsque rien ne l'en empeche. Les rangs suivants demeurent
    conformes mais moins bien notes.
    """

    rang: int
    chambre: str
    cout: int
    justification: str
    contreparties: tuple[str, ...] = ()
    avantages: tuple[str, ...] = ()
    penalites: Mapping[str, int] = field(default_factory=dict)

    @property
    def est_preferee(self) -> bool:
        return self.rang == 1

    def __str__(self) -> str:
        return f"{self.chambre} (rang {self.rang}, cout {self.cout})"


@dataclass(frozen=True, slots=True)
class Eventail:
    """Ensemble des options soumises au responsable."""

    options: tuple[Option, ...] = ()
    examinees: int = 0
    admissibles: int = 0
    interrompu: bool = False
    motifs_de_rejet: Mapping[str, int] = field(default_factory=dict)

    @property
    def est_vide(self) -> bool:
        return not self.options

    @property
    def preferee(self) -> Option | None:
        return self.options[0] if self.options else None

    @property
    def offre_un_choix(self) -> bool:
        """Indique qu'un arbitrage demeure ouvert au responsable."""
        return len(self.options) > 1

    @property
    def sont_equivalentes(self) -> bool:
        """Indique qu'aucun critere ne departage les options.

        Un classement presente sans qu'aucun critere ne le fonde laisserait
        croire a une preference du systeme la ou il n'en a aucune. Le
        responsable doit savoir que son choix est libre.
        """
        if len(self.options) < 2:
            return False
        couts = {option.cout for option in self.options}
        return len(couts) == 1

    @property
    def motifs_dominants(self) -> tuple[str, ...]:
        """Restitue les motifs ayant ecarte le plus de chambres.

        Le diagnostic n'a d'utilite que lorsque l'eventail demeure vide: il
        designe alors ce qui s'oppose a toute solution, la ou le seul constat
        d'absence laisserait le responsable sans prise.
        """
        return tuple(
            f"{motif}: {compte} chambres"
            for motif, compte in sorted(
                self.motifs_de_rejet.items(), key=lambda paire: -paire[1]
            )[:3]
        )

    def resumer(self) -> str:
        """Formule l'etendue du choix restitue."""
        if not self.options:
            return f"Aucune chambre ne convient parmi les {self.examinees} examinees."
        if len(self.options) == 1:
            return (
                f"Une seule chambre convient sur les {self.examinees} examinees: "
                f"{self.options[0].chambre}."
            )
        if self.sont_equivalentes:
            return (
                f"{len(self.options)} chambres conviennent egalement, "
                f"sur {self.admissibles} admissibles et {self.examinees} examinees. "
                f"Aucun critere ne les departage."
            )
        return (
            f"{len(self.options)} chambres conviennent, sur {self.admissibles} "
            f"admissibles et {self.examinees} examinees."
        )


class ProposerDesOptions:
    """Etablit plusieurs affectations possibles et ce qui les separe."""

    def __init__(self, affectation: AffecterChambre) -> None:
        self._affectation = affectation

    def executer(
        self,
        demande: Demande,
        nombre: int = OPTIONS_PAR_DEFAUT,
        temps_maximal: float | None = None,
    ) -> Eventail:
        """Produit les meilleures options, dans l'ordre etabli par le moteur.

        Chaque option retenue est ecartee du parc soumis a la recherche
        suivante. Le moteur restitue ainsi l'optimum de ce qui demeure, ce qui
        ordonne les options par cout croissant sans qu'aucun tri ulterieur ne
        soit necessaire.
        """
        retenues: list[Option] = []
        ecartees: set[NumeroChambre] = set()
        examinees = 0
        admissibles = 0
        interrompu = False
        motifs_de_rejet: dict[str, int] = {}

        for rang in range(1, nombre + 1):
            parc = tuple(
                chambre for chambre in demande.parc if chambre.numero not in ecartees
            )
            if not parc:
                break

            recommandation = self._affectation.executer(
                _restreindre(demande, parc), temps_maximal
            )

            if rang == 1:
                examinees = recommandation.nombre_examinees
                admissibles = len(recommandation.resultat.admissibles)
                motifs_de_rejet = _compter_les_rejets(recommandation)
            interrompu = interrompu or recommandation.resultat.interrompu

            if not recommandation.a_conclu or recommandation.chambre_proposee is None:
                break

            retenues.append(_constituer(rang, recommandation))
            ecartees.add(
                NumeroChambre(recommandation.chambre_proposee.removeprefix("c"))
            )

        eventail = Eventail(
            options=tuple(_distinguer(retenues)),
            examinees=examinees,
            admissibles=admissibles,
            interrompu=interrompu,
            motifs_de_rejet=motifs_de_rejet,
        )
        logger.info(
            "%d options etablies sur %d admissibles",
            len(eventail.options),
            admissibles,
        )
        return eventail


def _restreindre(demande: Demande, parc: tuple[Chambre, ...]) -> Demande:
    """Restitue la demande portant sur un parc reduit."""
    from dataclasses import replace

    return replace(demande, parc=parc)


def _compter_les_rejets(recommandation: Recommandation) -> dict[str, int]:
    """Denombre les chambres que chaque motif a ecartees.

    Le compte est etabli sur la premiere interrogation seule: elle porte sur le
    parc entier, quand les suivantes portent sur ce qu'il en reste. Les cumuler
    compterait plusieurs fois le meme rejet.
    """
    comptes: dict[str, int] = {}
    for option in recommandation.options_ecartees:
        for motif in option.motifs:
            comptes[motif.motif] = comptes.get(motif.motif, 0) + 1
    return comptes


def _constituer(rang: int, recommandation: Recommandation) -> Option:
    """Constitue une option a partir d'une recommandation."""
    penalites: dict[str, int] = {}
    for penalite in recommandation.resultat.penalites:
        penalites[penalite.motif] = penalites.get(penalite.motif, 0) + penalite.poids

    return Option(
        rang=rang,
        chambre=recommandation.chambre_proposee or "",
        cout=recommandation.resultat.cout,
        justification=recommandation.justification.decision.texte,
        contreparties=tuple(
            enonce.texte for enonce in recommandation.justification.contreparties
        ),
        penalites=penalites,
    )


def _distinguer(options: Sequence[Option]) -> list[Option]:
    """Etablit ce qui distingue chaque option des autres.

    La comparaison porte sur l'intensite des penalites et non sur leur seule
    presence: deux options peuvent subir le meme motif a des degres tres
    differents, et c'est cet ecart qui les separe utilement. Une option est
    avantagee sur un motif lorsqu'elle en subit sensiblement moins que la
    mediane des autres, et desavantagee dans le cas inverse.
    """
    if len(options) < 2:
        return list(options)

    motifs = {motif for option in options for motif in option.penalites}
    distinguees: list[Option] = []

    for option in options:
        avantages: list[str] = []
        contreparties: list[str] = []

        for motif in sorted(motifs):
            subie = option.penalites.get(motif, 0)
            ailleurs = [
                autre.penalites.get(motif, 0)
                for autre in options
                if autre is not option
            ]
            if not ailleurs:
                continue

            reference = sum(ailleurs) / len(ailleurs)

            if subie < reference * 0.7:
                formulation = AVANTAGES.get(motif)
                if formulation:
                    avantages.append(formulation)
            elif subie > reference * 1.3:
                formulation = CONTREPARTIES.get(motif)
                if formulation:
                    contreparties.append(formulation)

        distinguees.append(
            Option(
                rang=option.rang,
                chambre=option.chambre,
                cout=option.cout,
                justification=option.justification,
                contreparties=tuple(contreparties),
                avantages=tuple(avantages),
                penalites=option.penalites,
            )
        )

    return distinguees
