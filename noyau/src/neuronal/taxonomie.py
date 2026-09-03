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

    CONSULTER_PARC = "consulter_parc"
    CONSULTER_DISPONIBILITE = "consulter_disponibilite"
    CONSULTER_INDISPONIBLES = "consulter_indisponibles"
    CONSULTER_ARRIVEES = "consulter_arrivees"
    CONSULTER_AGENTS = "consulter_agents"
    CONSULTER_TACHES = "consulter_taches"
    CONSULTER_CHAMBRE = "consulter_chambre"
    CONSULTER_SEJOUR = "consulter_sejour"

    CONFLIT_AFFECTATION = "conflit_affectation"
    SUR_OCCUPATION = "sur_occupation"
    DEMANDE_CONSEIL = "demande_conseil"


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
    ETAGE = "etage"
    ETAT = "etat"


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
    Intention.CONSULTER_PARC: frozenset(),
    Intention.CONSULTER_DISPONIBILITE: frozenset({TypeDEntite.ETAGE}),
    Intention.CONSULTER_INDISPONIBLES: frozenset({TypeDEntite.ETAGE}),
    Intention.CONSULTER_ARRIVEES: frozenset({TypeDEntite.HEURE}),
    Intention.CONSULTER_AGENTS: frozenset({TypeDEntite.SECTEUR}),
    Intention.CONSULTER_TACHES: frozenset({TypeDEntite.SECTEUR}),
    Intention.CONSULTER_CHAMBRE: frozenset({TypeDEntite.CHAMBRE}),
    Intention.CONSULTER_SEJOUR: frozenset({TypeDEntite.RESERVATION}),
    Intention.CONFLIT_AFFECTATION: frozenset(
        {TypeDEntite.CHAMBRE, TypeDEntite.RESERVATION}
    ),
    Intention.SUR_OCCUPATION: frozenset({TypeDEntite.HEURE}),
    Intention.DEMANDE_CONSEIL: frozenset(),
}


INTENTIONS_DE_CONSULTATION: frozenset[Intention] = frozenset(
    {
        Intention.CONSULTER_PARC,
        Intention.CONSULTER_DISPONIBILITE,
        Intention.CONSULTER_INDISPONIBLES,
        Intention.CONSULTER_ARRIVEES,
        Intention.CONSULTER_AGENTS,
        Intention.CONSULTER_TACHES,
        Intention.CONSULTER_CHAMBRE,
        Intention.CONSULTER_SEJOUR,
    }
)

INTENTIONS_D_ARBITRAGE: frozenset[Intention] = frozenset(
    {
        Intention.CONFLIT_AFFECTATION,
        Intention.SUR_OCCUPATION,
        Intention.DEMANDE_CONSEIL,
        Intention.DEMANDE_AFFECTATION,
        Intention.DEMANDE_CHANGEMENT,
    }
)


def appelle_un_raisonnement(intention: Intention) -> bool:
    """Etablit si une intention engage le moteur de raisonnement.

    Une consultation restitue un etat: elle interroge la base et repond. Un
    arbitrage etablit une decision: il mobilise les regles, produit des options
    admissibles et une justification. La distinction determine le traitement
    applique et ce qui est presente au responsable.
    """
    return intention not in INTENTIONS_DE_CONSULTATION
