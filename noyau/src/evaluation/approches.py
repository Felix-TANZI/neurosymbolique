"""Definition des trois approches confrontees.

La comparaison oppose trois conduites face a une meme situation. La premiere
s'en remet a la seule interpretation neuronale: elle comprend l'enonce mais ne
verifie rien. La deuxieme s'en tient au seul raisonnement symbolique: elle
garantit les contraintes mais n'accepte qu'une situation deja formalisee. La
troisieme les compose.

L'objet n'est pas d'etablir qu'une approche l'emporte partout, mais de
determiner dans quelles situations leur composition apporte ce qu'aucune ne
procure seule.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum, unique

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@unique
class Approche(StrEnum):
    """Conduite tenue face a une situation."""

    NEURONALE = "neuronale"
    SYMBOLIQUE = "symbolique"
    COMPOSEE = "composee"


@dataclass(frozen=True, slots=True)
class Conduite:
    """Ce qu'une approche a etabli face a un scenario.

    La conduite restitue ce que l'approche a fait, non ce qu'elle aurait du
    faire: la confrontation a l'attendu releve de la mesure, non de
    l'execution.
    """

    approche: str
    scenario: str
    conduite: str
    intention: str = ""
    entites: dict[str, str] = field(default_factory=dict)
    chambres_proposees: tuple[str, ...] = ()
    confiance: float = 0.0
    duree_millisecondes: float = 0.0
    defaillance: str = ""

    @property
    def a_defailli(self) -> bool:
        return bool(self.defaillance)


TraitementDUnScenario = Callable[[Session, str, date], Conduite]
