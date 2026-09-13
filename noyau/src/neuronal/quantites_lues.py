"""Qualification des quantites extraites d'un enonce.

Le modele reconnait les nombres d'un enonce sans etablir ce qu'ils designent:
« douze chambres et trois agents » restitue deux quantites, dont l'ordre seul
ne dit rien. Le mot qui suit chaque nombre porte cette information, et c'est de
l'enonce lui-meme qu'elle se lit.

Aucune convention d'ordre n'est retenue. Supposer que la premiere quantite
designe la charge ferait echouer « trois agents pour douze chambres » sans
qu'aucun signal ne le revele. Lorsque le terme qualifiant manque, le module
s'abstient plutot que de deviner: une repartition fondee sur une lecture
erronee des quantites produirait une conduite inexploitable.
"""

import logging
from dataclasses import dataclass
from enum import StrEnum, unique

from .inference import Interpretation
from .taxonomie import TypeDEntite
from .tokeniseur import segmenter

logger = logging.getLogger(__name__)

PORTEE_DU_QUALIFIANT = 3

NOMBRES_EN_LETTRES: dict[str, int] = {
    "un": 1,
    "une": 1,
    "deux": 2,
    "trois": 3,
    "quatre": 4,
    "cinq": 5,
    "six": 6,
    "sept": 7,
    "huit": 8,
    "neuf": 9,
    "dix": 10,
    "onze": 11,
    "douze": 12,
    "quinze": 15,
    "vingt": 20,
}

TERMES_DE_CHARGE: frozenset[str] = frozenset(
    {
        "chambre",
        "chambres",
        "nettoyage",
        "nettoyages",
        "prestation",
        "prestations",
        "tache",
        "taches",
        "recouche",
        "recouches",
        "unite",
        "unites",
    }
)

TERMES_D_EFFECTIF: frozenset[str] = frozenset(
    {
        "agent",
        "agents",
        "personne",
        "personnes",
        "employe",
        "employes",
        "equipe",
        "equipes",
        "intervenant",
        "intervenants",
        "femme",
        "femmes",
        "collaborateur",
        "collaborateurs",
    }
)


@unique
class RoleDeLaQuantite(StrEnum):
    """Ce qu'une quantite designe dans l'enonce."""

    CHARGE = "charge"
    EFFECTIF = "effectif"
    INDETERMINE = "indetermine"


@dataclass(frozen=True, slots=True)
class QuantiteQualifiee:
    """Nombre releve dans l'enonce, avec ce qu'il designe."""

    valeur: int
    role: str
    qualifiant: str = ""

    @property
    def est_qualifiee(self) -> bool:
        return self.role != RoleDeLaQuantite.INDETERMINE.value


@dataclass(frozen=True, slots=True)
class ChargeALire:
    """Charge et effectif releves dans un enonce, lorsqu'ils sont etablis."""

    charge: int | None = None
    effectif: int | None = None
    indeterminees: tuple[int, ...] = ()

    @property
    def est_exploitable(self) -> bool:
        """Indique que la repartition peut etre conduite."""
        return self.charge is not None and self.effectif is not None

    @property
    def manque(self) -> str:
        """Designe ce qui fait defaut pour conduire la repartition."""
        if self.charge is None and self.effectif is None:
            return "le nombre de chambres et l'effectif"
        if self.charge is None:
            return "le nombre de chambres"
        if self.effectif is None:
            return "l'effectif"
        return ""


def relever_les_quantites(interpretation: Interpretation) -> ChargeALire:
    """Etablit ce que designent les quantites d'un enonce.

    Chaque quantite est qualifiee par les mots qui la suivent immediatement.
    Une quantite dont le terme qualifiant est absent demeure indeterminee: le
    module ne lui attribue aucun role, et la repartition ne sera pas conduite.
    """
    mots = segmenter(interpretation.enonce)
    relevees: list[QuantiteQualifiee] = []

    for entite in interpretation.entites:
        if entite.type_d_entite != TypeDEntite.QUANTITE.value:
            continue

        valeur = _convertir(entite.valeur)
        if valeur is None:
            continue

        relevees.append(_qualifier(valeur, entite.fin, mots))

    charge = next(
        (
            quantite.valeur
            for quantite in relevees
            if quantite.role == RoleDeLaQuantite.CHARGE.value
        ),
        None,
    )
    effectif = next(
        (
            quantite.valeur
            for quantite in relevees
            if quantite.role == RoleDeLaQuantite.EFFECTIF.value
        ),
        None,
    )
    indeterminees = tuple(
        quantite.valeur for quantite in relevees if not quantite.est_qualifiee
    )

    if indeterminees:
        logger.info(
            "%d quantites demeurent indeterminees dans: %s",
            len(indeterminees),
            interpretation.enonce,
        )

    return ChargeALire(
        charge=charge, effectif=effectif, indeterminees=indeterminees
    )


def _qualifier(
    valeur: int, fin: int, mots: list[str]
) -> QuantiteQualifiee:
    """Etablit ce qu'une quantite designe, d'apres les mots qui la suivent.

    La recherche porte sur les mots immediatement posterieurs: « douze
    chambres » qualifie, « douze, pour trois agents » ne qualifie que la
    seconde. Etendre la portee ferait attribuer a une quantite le terme qui
    qualifie la suivante.
    """
    for rang in range(fin, min(fin + PORTEE_DU_QUALIFIANT, len(mots))):
        mot = mots[rang]

        if mot in TERMES_DE_CHARGE:
            return QuantiteQualifiee(
                valeur=valeur,
                role=RoleDeLaQuantite.CHARGE.value,
                qualifiant=mot,
            )

        if mot in TERMES_D_EFFECTIF:
            return QuantiteQualifiee(
                valeur=valeur,
                role=RoleDeLaQuantite.EFFECTIF.value,
                qualifiant=mot,
            )

        if mot.isdigit() or mot in NOMBRES_EN_LETTRES:
            break

    return QuantiteQualifiee(
        valeur=valeur, role=RoleDeLaQuantite.INDETERMINE.value
    )


def _convertir(valeur: str) -> int | None:
    """Restitue la valeur numerique d'une quantite exprimee."""
    nettoyee = valeur.strip().lower().replace(" ", "")

    if nettoyee.isdigit():
        return int(nettoyee)

    return NOMBRES_EN_LETTRES.get(nettoyee)
