"""Constitution des preferences du domaine a partir d'une interpretation.

Le module realise la conversion entre ce que le modele reconnait et ce que le
moteur symbolique manipule. Une entite de proximite extraite d'un enonce
devient ici une preference du domaine, que la traduction transformera en poids
dans le programme logique.

Cette conversion constitue la charniere du systeme: elle est le point ou une
formulation en langue naturelle acquiert une portee sur le raisonnement, sans
qu'aucune regle n'ait a etre reecrite.

Les preferences ne sont relevees que sur les intentions qui en portent. Les
rechercher partout ferait prendre pour une reference de proximite le numero
d'une chambre simplement mentionnee.
"""

import logging

from src.domaine import NatureDeLaPreference, Preference, Preferences

from .inference import Interpretation
from .taxonomie import Intention, TypeDEntite, exprime_une_preference

logger = logging.getLogger(__name__)

INTENSITE_PAR_DEFAUT = 1


def relever_les_preferences(interpretation: Interpretation) -> Preferences:
    """Constitue les preferences exprimees dans un enonce interprete.

    Une preference dont l'entite ne correspond a aucune reference reelle est
    ecartee: la verification symbolique l'a signalee comme inexistante, et
    fonder un critere d'optimisation sur une reference inventee produirait un
    classement sans fondement.
    """
    if not interpretation.intention:
        return Preferences()

    intention = Intention(interpretation.intention)
    if not exprime_une_preference(intention):
        return Preferences()

    relevees = Preferences()

    for entite in interpretation.entites:
        if entite.existe is False:
            logger.info(
                "preference ecartee, reference inexistante: %s=%s",
                entite.type_d_entite,
                entite.valeur,
            )
            continue

        nature = _NATURE_PAR_ENTITE.get(entite.type_d_entite)
        if nature is None:
            continue

        relevees = relevees.avec(
            Preference(
                nature=nature,
                reference=entite.valeur,
                intensite=INTENSITE_PAR_DEFAUT,
            )
        )

    if relevees:
        logger.info(
            "%d preferences relevees: %s",
            len(relevees),
            [str(preference) for preference in relevees],
        )
    return relevees


_NATURE_PAR_ENTITE: dict[str, str] = {
    TypeDEntite.PROXIMITE.value: NatureDeLaPreference.PROXIMITE.value,
    TypeDEntite.ELOIGNEMENT.value: NatureDeLaPreference.ELOIGNEMENT.value,
    TypeDEntite.ETAGE.value: NatureDeLaPreference.ETAGE_DESIGNE.value,
}


def chambre_concernee(interpretation: Interpretation) -> str | None:
    """Restitue la chambre sur laquelle porte la situation.

    L'entite de chambre designe le lieu de l'incident ou du sejour a deplacer,
    quand les entites de proximite designent des reperes. Les confondre
    ferait traiter un repere comme le siege du probleme.
    """
    return interpretation.valeur_de(TypeDEntite.CHAMBRE.value)
