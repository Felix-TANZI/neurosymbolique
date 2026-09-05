"""Preferences exprimees par un responsable sur une affectation.

Une preference oriente le choix sans le contraindre: elle n'ecarte aucune
chambre, elle ordonne celles qui demeurent admissibles. La distinction avec une
exigence est fonctionnelle: une exigence non satisfaite interdit l'affectation,
une preference non satisfaite la rend seulement moins bonne.

Les preferences constituent la charniere entre la couche neuronale et la couche
symbolique. Une formulation telle que « une chambre a cote de la 405 » est
reconnue par le modele, convertie ici en objet du domaine, puis traduite en
poids dans le programme logique. La demande du responsable devient ainsi un
critere d'optimisation, sans qu'aucune regle n'ait a etre reecrite.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum, unique

from .valeurs import NumeroChambre


@unique
class NatureDeLaPreference(StrEnum):
    """Forme que prend une preference exprimee sur une affectation."""

    PROXIMITE = "proximite"
    ELOIGNEMENT = "eloignement"
    MEME_ETAGE = "meme_etage"
    ETAGE_DESIGNE = "etage_designe"
    SURCLASSEMENT = "surclassement"


@dataclass(frozen=True, slots=True)
class Preference:
    """Souhait exprime sur l'affectation, assorti de son intensite.

    L'intensite pondere la preference dans l'arbitrage: elle permet de
    distinguer un souhait appuye d'une simple indication, et de departager
    plusieurs preferences concurrentes.
    """

    nature: str
    reference: str = ""
    intensite: int = 1

    def __post_init__(self) -> None:
        if self.intensite < 1:
            raise ValueError(
                f"l'intensite d'une preference doit etre positive: {self.intensite}"
            )
        if self.nature in _NATURES_AVEC_REFERENCE and not self.reference:
            raise ValueError(
                f"la preference {self.nature} exige une reference"
            )

    def __str__(self) -> str:
        return (
            f"{self.nature}({self.reference})" if self.reference else self.nature
        )


_NATURES_AVEC_REFERENCE: frozenset[str] = frozenset(
    {
        NatureDeLaPreference.PROXIMITE.value,
        NatureDeLaPreference.ELOIGNEMENT.value,
        NatureDeLaPreference.MEME_ETAGE.value,
        NatureDeLaPreference.ETAGE_DESIGNE.value,
    }
)


@dataclass(frozen=True, slots=True)
class Preferences:
    """Ensemble des preferences portant sur une meme affectation."""

    exprimees: tuple[Preference, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.exprimees)

    def __iter__(self) -> Iterator[Preference]:
        return iter(self.exprimees)

    def __len__(self) -> int:
        return len(self.exprimees)

    def de_nature(self, nature: str) -> tuple[Preference, ...]:
        """Restitue les preferences d'une nature donnee."""
        return tuple(
            preference
            for preference in self.exprimees
            if preference.nature == nature
        )

    def avec(self, preference: Preference) -> "Preferences":
        """Restitue l'ensemble augmente d'une preference."""
        return Preferences(exprimees=(*self.exprimees, preference))


def distance_entre(premiere: NumeroChambre, seconde: NumeroChambre) -> int | None:
    """Etablit le nombre de portes separant deux chambres d'un meme etage.

    La distance se deduit de la numerotation: deux chambres consecutives sont
    voisines. Elle demeure indefinie entre etages differents, ou aucune notion
    de proximite ne s'applique sans plan de l'etablissement.
    """
    premier = _decomposer(str(premiere))
    second = _decomposer(str(seconde))

    if premier is None or second is None:
        return None
    if premier[0] != second[0]:
        return None

    return abs(premier[1] - second[1])


def sont_voisines(premiere: NumeroChambre, seconde: NumeroChambre) -> bool:
    """Etablit si deux chambres se jouxtent."""
    distance = distance_entre(premiere, seconde)
    return distance is not None and distance == 1


def etage_de(chambre: NumeroChambre) -> int | None:
    """Restitue l'etage deduit de la numerotation."""
    decompose = _decomposer(str(chambre))
    return decompose[0] if decompose else None


def _decomposer(numero: str) -> tuple[int, int] | None:
    """Separe l'etage du rang dans un numero de chambre.

    La convention retenue place l'etage en tete et le rang sur les deux
    derniers chiffres: 405 designe la cinquieme chambre du quatrieme etage. Un
    numero qui ne s'y conforme pas ne permet aucun calcul de proximite.
    """
    chiffres = "".join(caractere for caractere in numero if caractere.isdigit())
    if len(chiffres) < 3:
        return None
    return int(chiffres[:-2]), int(chiffres[-2:])
