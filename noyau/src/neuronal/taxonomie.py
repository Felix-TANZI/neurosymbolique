"""Taxonomie des situations operationnelles et schema d'annotation.

La taxonomie enumere les intentions que la couche d'interpretation doit
reconnaitre et les types d'entites qu'elle doit extraire. Elle constitue la
verite terrain du corpus: les annotations en derivent, et le modele n'apprend
rien qui n'y figure.

Le schema d'annotation suit la convention BIO, employee par les jeux de
reference du domaine: chaque jeton porte l'etiquette B-type s'il ouvre une
entite, I-type s'il la poursuit, O s'il n'appartient a aucune.
"""

from enum import StrEnum, unique


@unique
class Intention(StrEnum):
    """Situation operationnelle exprimee par un enonce.

    Les intentions couvrent les trois services traites par le systeme. Une
    intention absente de cette enumeration ne peut etre reconnue: l'enonce est
    alors signale comme hors perimetre plutot qu'interprete par defaut.
    """

    DEGAT_DES_EAUX = "degat_des_eaux"
    PANNE_ELECTRIQUE = "panne_electrique"
    PANNE_CLIMATISATION = "panne_climatisation"
    PANNE_PLOMBERIE = "panne_plomberie"
    DEFAUT_SERRURE = "defaut_serrure"
    MOBILIER_ENDOMMAGE = "mobilier_endommage"
    NUISANCE_SONORE = "nuisance_sonore"
    RISQUE_SECURITE = "risque_securite"

    DEMANDE_AFFECTATION = "demande_affectation"
    DEMANDE_CHANGEMENT = "demande_changement"
    SIGNALEMENT_INDISPONIBILITE = "signalement_indisponibilite"

    ARRIVEE_ANTICIPEE = "arrivee_anticipee"
    CHAMBRE_URGENTE = "chambre_urgente"
    AGENT_INDISPONIBLE = "agent_indisponible"
    DEMANDE_PLANIFICATION = "demande_planification"


@unique
class TypeDEntite(StrEnum):
    """Element concret mentionne dans un enonce et extrait de celui-ci."""

    CHAMBRE = "chambre"
    RESERVATION = "reservation"
    AGENT = "agent"
    SECTEUR = "secteur"
    HEURE = "heure"
    EQUIPEMENT = "equipement"
    LOCALISATION = "localisation"


ETIQUETTE_HORS_ENTITE = "O"


def etiquettes_bio() -> list[str]:
    """Restitue l'ensemble ordonne des etiquettes du schema d'annotation.

    L'ordre est stable: il determine l'indice de chaque etiquette dans les
    sorties du modele, et une permutation invaliderait un modele deja entraine.
    """
    etiquettes = [ETIQUETTE_HORS_ENTITE]
    for entite in TypeDEntite:
        etiquettes.append(f"B-{entite.value}")
        etiquettes.append(f"I-{entite.value}")
    return etiquettes


def indices_des_etiquettes() -> dict[str, int]:
    """Associe chaque etiquette a son indice dans les sorties du modele."""
    return {etiquette: rang for rang, etiquette in enumerate(etiquettes_bio())}


def indices_des_intentions() -> dict[str, int]:
    """Associe chaque intention a son indice dans les sorties du modele."""
    return {intention.value: rang for rang, intention in enumerate(Intention)}


INTENTIONS_PAR_SERVICE: dict[str, tuple[Intention, ...]] = {
    "maintenance": (
        Intention.DEGAT_DES_EAUX,
        Intention.PANNE_ELECTRIQUE,
        Intention.PANNE_CLIMATISATION,
        Intention.PANNE_PLOMBERIE,
        Intention.DEFAUT_SERRURE,
        Intention.MOBILIER_ENDOMMAGE,
        Intention.NUISANCE_SONORE,
        Intention.RISQUE_SECURITE,
    ),
    "chambres": (
        Intention.DEMANDE_AFFECTATION,
        Intention.DEMANDE_CHANGEMENT,
        Intention.SIGNALEMENT_INDISPONIBILITE,
        Intention.ARRIVEE_ANTICIPEE,
    ),
    "housekeeping": (
        Intention.CHAMBRE_URGENTE,
        Intention.AGENT_INDISPONIBLE,
        Intention.DEMANDE_PLANIFICATION,
    ),
}


ENTITES_ATTENDUES: dict[Intention, frozenset[TypeDEntite]] = {
    Intention.DEGAT_DES_EAUX: frozenset(
        {TypeDEntite.CHAMBRE, TypeDEntite.LOCALISATION}
    ),
    Intention.PANNE_ELECTRIQUE: frozenset({TypeDEntite.CHAMBRE}),
    Intention.PANNE_CLIMATISATION: frozenset({TypeDEntite.CHAMBRE}),
    Intention.PANNE_PLOMBERIE: frozenset(
        {TypeDEntite.CHAMBRE, TypeDEntite.LOCALISATION}
    ),
    Intention.DEFAUT_SERRURE: frozenset({TypeDEntite.CHAMBRE}),
    Intention.MOBILIER_ENDOMMAGE: frozenset(
        {TypeDEntite.CHAMBRE, TypeDEntite.LOCALISATION}
    ),
    Intention.NUISANCE_SONORE: frozenset({TypeDEntite.CHAMBRE}),
    Intention.RISQUE_SECURITE: frozenset(
        {TypeDEntite.CHAMBRE, TypeDEntite.LOCALISATION}
    ),
    Intention.DEMANDE_AFFECTATION: frozenset(
        {TypeDEntite.RESERVATION, TypeDEntite.EQUIPEMENT}
    ),
    Intention.DEMANDE_CHANGEMENT: frozenset(
        {TypeDEntite.RESERVATION, TypeDEntite.CHAMBRE, TypeDEntite.EQUIPEMENT}
    ),
    Intention.SIGNALEMENT_INDISPONIBILITE: frozenset({TypeDEntite.CHAMBRE}),
    Intention.ARRIVEE_ANTICIPEE: frozenset(
        {TypeDEntite.RESERVATION, TypeDEntite.HEURE}
    ),
    Intention.CHAMBRE_URGENTE: frozenset(
        {TypeDEntite.CHAMBRE, TypeDEntite.HEURE}
    ),
    Intention.AGENT_INDISPONIBLE: frozenset(
        {TypeDEntite.AGENT, TypeDEntite.SECTEUR}
    ),
    Intention.DEMANDE_PLANIFICATION: frozenset({TypeDEntite.SECTEUR}),
}
