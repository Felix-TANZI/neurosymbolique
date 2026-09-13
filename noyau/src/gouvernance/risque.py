"""Evaluation du risque et decision de s'abstenir.

Un systeme d'aide a la decision critique doit graduer sa conduite selon ce
qu'il sait. Une lecture assuree portant sur une situation ordinaire n'appelle
pas la meme prudence qu'une lecture incertaine portant sur une immobilisation
de chambre.

L'abstention n'est pas un echec mais une conduite. Un systeme qui repond
toujours transfere sur le responsable la charge de deceler ses erreurs; un
systeme qui declare ne pas pouvoir repondre de facon fiable lui restitue une
information exploitable.
"""

import logging
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum, unique

from src.neuronal.inference import Interpretation, MotifDeReserve
from src.neuronal.taxonomie import ENTITES_ATTENDUES, Intention

logger = logging.getLogger(__name__)

CONFIANCE_ASSUREE = 0.85
CONFIANCE_ACCEPTABLE = 0.70


@unique
class NiveauDeRisque(IntEnum):
    """Prudence que la situation commande.

    Les niveaux sont ordonnes: leur comparaison permet d'etablir la conduite
    la plus conservatrice entre plusieurs appreciations.
    """

    MESURE = 1
    MODERE = 2
    ELEVE = 3
    INDETERMINE = 4


@unique
class MotifDAbstention(StrEnum):
    """Raison pour laquelle le systeme ne peut se prononcer."""

    HORS_DOMAINE = "hors_domaine"
    INFORMATION_MANQUANTE = "information_manquante"
    CONFIANCE_INSUFFISANTE = "confiance_insuffisante"
    REFERENCE_INEXISTANTE = "reference_inexistante"
    AUCUNE_SOLUTION = "aucune_solution"


CONDUITES: dict[int, str] = {
    NiveauDeRisque.MESURE: (
        "La lecture est assuree et la situation ordinaire. La proposition "
        "peut etre examinee directement."
    ),
    NiveauDeRisque.MODERE: (
        "La lecture demeure assuree mais la situation engage l'exploitation. "
        "Verifiez la proposition avant de l'appliquer."
    ),
    NiveauDeRisque.ELEVE: (
        "La lecture comporte une incertitude sur une situation engageante. "
        "Une verification de la situation est requise."
    ),
    NiveauDeRisque.INDETERMINE: (
        "Le systeme ne dispose pas des elements permettant une proposition "
        "fiable."
    ),
}

MOTIFS_LISIBLES: dict[str, str] = {
    MotifDAbstention.HORS_DOMAINE.value: (
        "Cet enonce ne releve d'aucune situation traitee par le systeme."
    ),
    MotifDAbstention.INFORMATION_MANQUANTE.value: (
        "Un element indispensable n'a pas ete reconnu dans l'enonce."
    ),
    MotifDAbstention.CONFIANCE_INSUFFISANTE.value: (
        "Le systeme n'est pas assure d'avoir compris la situation."
    ),
    MotifDAbstention.REFERENCE_INEXISTANTE.value: (
        "Un element mentionne ne correspond a rien dans l'etablissement."
    ),
    MotifDAbstention.AUCUNE_SOLUTION.value: (
        "Aucune solution conforme aux contraintes n'existe."
    ),
}

INTENTIONS_ENGAGEANTES: frozenset[str] = frozenset(
    {
        Intention.DEGAT_DES_EAUX.value,
        Intention.RISQUE_SECURITE.value,
        Intention.PANNE_ELECTRIQUE.value,
        Intention.SIGNALEMENT_INDISPONIBILITE.value,
        Intention.CONFLIT_AFFECTATION.value,
        Intention.INCIDENT_AVEC_PREFERENCE.value,
        Intention.SUR_OCCUPATION.value,
    }
)


@dataclass(frozen=True, slots=True)
class Appreciation:
    """Niveau de risque etabli et conduite qu'il commande."""

    niveau: int
    conduite: str
    abstention: str = ""
    precision_attendue: str = ""
    motifs: tuple[str, ...] = field(default_factory=tuple)

    @property
    def appelle_une_abstention(self) -> bool:
        return bool(self.abstention)

    @property
    def appelle_une_verification(self) -> bool:
        return self.niveau >= NiveauDeRisque.ELEVE

    @property
    def libelle(self) -> str:
        return NiveauDeRisque(self.niveau).name.lower()


def apprecier(interpretation: Interpretation) -> Appreciation:
    """Etablit le risque que comporte une lecture et la conduite a tenir.

    L'appreciation combine l'assurance de la lecture et la portee de la
    situation: une incertitude sur une consultation demeure sans consequence,
    la meme incertitude sur une immobilisation engage l'exploitation.
    """
    if not interpretation.intention:
        return _abstenir(
            MotifDAbstention.HORS_DOMAINE.value,
            "Decrivez une situation operationnelle.",
        )

    intention = Intention(interpretation.intention)

    if intention is Intention.DEMANDE_CONSEIL:
        return _abstenir(
            MotifDAbstention.HORS_DOMAINE.value,
            "Decrivez la situation sur laquelle porte votre question.",
        )

    motifs = {reserve.motif for reserve in interpretation.reserves}
    confiance = interpretation.confiance_d_intention

    verifiees = [
        entite for entite in interpretation.entites if entite.existe is True
    ]

    # Une entite verifiee rattache l'enonce a l'etablissement: le systeme peut
    # hesiter sur la nature de la situation sans que son objet soit douteux.
    # En l'absence de toute reference reconnue, une confiance faible revele au
    # contraire que l'intention a ete retenue faute de mieux.
    if confiance < CONFIANCE_ACCEPTABLE and not verifiees:
        return _abstenir(
            MotifDAbstention.HORS_DOMAINE.value,
            "Decrivez une situation operationnelle de l'etablissement.",
        )

    attendues = ENTITES_ATTENDUES.get(intention, frozenset())
    types_attendus = {entite.value for entite in attendues}

    # Une entite inexistante n'est redhibitoire que si l'intention l'attend.
    # Un nombre pris a tort pour une chambre dans « 12 et 3 » ne doit pas
    # faire echouer une repartition qui n'en demande aucune: le raisonnement
    # ne s'appuiera pas sur cette lecture erronee.
    inexistantes = [
        reserve
        for reserve in interpretation.reserves
        if reserve.motif == MotifDeReserve.ENTITE_INEXISTANTE.value
        and _type_de(reserve.detail) in types_attendus
    ]

    if inexistantes:
        return _abstenir(
            MotifDAbstention.REFERENCE_INEXISTANTE.value,
            f"Verifiez la reference mentionnee: {inexistantes[0].detail}.",
        )

    # La situation est reconnue, mais un element indispensable manque. Le
    # systeme peut alors designer precisement ce qu'il attend.
    if MotifDeReserve.ENTITE_MANQUANTE.value in motifs:
        manquante = next(
            (
                reserve.detail
                for reserve in interpretation.reserves
                if reserve.motif == MotifDeReserve.ENTITE_MANQUANTE.value
            ),
            "",
        )
        return _abstenir(
            MotifDAbstention.INFORMATION_MANQUANTE.value,
            _demander(manquante),
        )

    engageante = interpretation.intention in INTENTIONS_ENGAGEANTES

    if confiance >= CONFIANCE_ASSUREE:
        niveau = NiveauDeRisque.MODERE if engageante else NiveauDeRisque.MESURE
    else:
        niveau = NiveauDeRisque.ELEVE if engageante else NiveauDeRisque.MODERE

    logger.debug(
        "risque %s sur %s (confiance %.2f)",
        NiveauDeRisque(niveau).name.lower(),
        interpretation.intention,
        confiance,
    )

    return Appreciation(
        niveau=int(niveau),
        conduite=CONDUITES[niveau],
    )


def _type_de(detail: str) -> str:
    """Restitue le type d'entite designe par un detail de reserve.

    Le detail est forme du type et de la valeur separes par un signe egal.
    L'absence de separateur laisse le detail intact, ce qui ne correspondra a
    aucun type attendu et rendra la reserve sans effet.
    """
    return detail.split("=", 1)[0] if "=" in detail else detail


def _abstenir(motif: str, precision: str = "") -> Appreciation:
    """Constitue une abstention motivee."""
    return Appreciation(
        niveau=int(NiveauDeRisque.INDETERMINE),
        conduite=CONDUITES[NiveauDeRisque.INDETERMINE],
        abstention=motif,
        precision_attendue=precision,
        motifs=(MOTIFS_LISIBLES.get(motif, motif),),
    )


def _demander(entite_manquante: str) -> str:
    """Formule la precision attendue du responsable.

    Designer l'element manquant restitue au responsable une demande a laquelle
    il peut repondre, la ou une invitation a reformuler le laisserait devant
    la meme incertitude.
    """
    demandes = {
        "chambre": "Precisez la chambre concernee.",
        "reservation": "Precisez le sejour concerne.",
        "agent": "Precisez l'agent concerne.",
        "secteur": "Precisez le secteur concerne.",
    }
    return demandes.get(entite_manquante, "Precisez l'element manquant.")
