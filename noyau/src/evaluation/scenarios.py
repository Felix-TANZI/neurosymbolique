"""Jeu de scenarios destines a l'evaluation comparative des approches.

Les scenarios decrivent des situations operationnelles dont la conduite
attendue est etablie a l'avance. Ils permettent de confronter trois approches
sur une meme base: la couche neuronale seule, le moteur symbolique seul, et
leur composition.

L'attendu porte sur ce qui est verifiable, non sur une preference: une chambre
occupee ne peut etre attribuee, une reference inexistante ne peut fonder une
decision, un enonce hors perimetre ne peut recevoir de reponse. Un attendu qui
reposerait sur un jugement discutable ne mesurerait que l'accord avec ce
jugement.

Les scenarios sont classes par ce qu'ils eprouvent. Cette classification
permet d'etablir non seulement si une approche reussit, mais dans quelles
situations elle echoue, ce qui constitue l'objet meme de la comparaison.
"""

from dataclasses import dataclass, field
from enum import StrEnum, unique


@unique
class Epreuve(StrEnum):
    """Ce que le scenario met a l'epreuve."""

    COMPREHENSION = "comprehension"
    REFERENCE = "reference"
    CONTRAINTE = "contrainte"
    PREFERENCE = "preference"
    ABSTENTION = "abstention"
    ARBITRAGE = "arbitrage"


@unique
class ConduiteAttendue(StrEnum):
    """Conduite que le systeme devrait tenir."""

    REPONDRE = "repondre"
    PROPOSER = "proposer"
    SIGNALER_INEXISTANT = "signaler_inexistant"
    REFUSER_HORS_PERIMETRE = "refuser_hors_perimetre"
    DEMANDER_CONFIRMATION = "demander_confirmation"
    CONSTATER_ABSENCE_DE_CONFLIT = "constater_absence_de_conflit"


@dataclass(frozen=True, slots=True)
class Scenario:
    """Situation soumise au systeme, avec la conduite attendue."""

    identifiant: str
    enonce: str
    epreuve: str
    conduite: str
    intention_attendue: str = ""
    entites_attendues: dict[str, str] = field(default_factory=dict)
    commentaire: str = ""

    def __post_init__(self) -> None:
        if not self.enonce.strip():
            raise ValueError(f"scenario {self.identifiant} sans enonce")


SCENARIOS: tuple[Scenario, ...] = (
    # Comprehension d'enonces ordinaires.
    Scenario(
        identifiant="S-01",
        enonce="il y a une fuite dans la 319",
        epreuve=Epreuve.COMPREHENSION.value,
        conduite=ConduiteAttendue.PROPOSER.value,
        intention_attendue="degat_des_eaux",
        entites_attendues={"chambre": "319"},
    ),
    Scenario(
        identifiant="S-02",
        enonce="la clim de la 405 ne marche plus",
        epreuve=Epreuve.COMPREHENSION.value,
        conduite=ConduiteAttendue.PROPOSER.value,
        intention_attendue="panne_climatisation",
        entites_attendues={"chambre": "405"},
    ),
    Scenario(
        identifiant="S-03",
        enonce="combien de chambres avons-nous",
        epreuve=Epreuve.COMPREHENSION.value,
        conduite=ConduiteAttendue.REPONDRE.value,
        intention_attendue="consulter_parc",
    ),
    Scenario(
        identifiant="S-04",
        enonce="quelles chambres sont hors service a l'etage 4",
        epreuve=Epreuve.COMPREHENSION.value,
        conduite=ConduiteAttendue.REPONDRE.value,
        intention_attendue="consulter_indisponibles",
        entites_attendues={"etage": "4"},
    ),
    # Comprehension d'enonces alteres.
    Scenario(
        identifiant="S-05",
        enonce="il y a une fuiite dans la 319",
        epreuve=Epreuve.COMPREHENSION.value,
        conduite=ConduiteAttendue.PROPOSER.value,
        intention_attendue="degat_des_eaux",
        entites_attendues={"chambre": "319"},
        commentaire="Faute de frappe sur le terme porteur de l'intention.",
    ),
    Scenario(
        identifiant="S-06",
        enonce="la moquette de la 312 est trempee",
        epreuve=Epreuve.COMPREHENSION.value,
        conduite=ConduiteAttendue.PROPOSER.value,
        intention_attendue="degat_des_eaux",
        entites_attendues={"chambre": "312"},
        commentaire=(
            "Formulation employant un vocabulaire absent du corpus "
            "d'entrainement, mais du meme champ lexical."
        ),
    ),
    # Verification des references.
    Scenario(
        identifiant="S-07",
        enonce="il y a une fuite dans la 999",
        epreuve=Epreuve.REFERENCE.value,
        conduite=ConduiteAttendue.SIGNALER_INEXISTANT.value,
        intention_attendue="degat_des_eaux",
        entites_attendues={"chambre": "999"},
        commentaire="La chambre n'appartient pas a l'etablissement.",
    ),
    Scenario(
        identifiant="S-08",
        enonce="quel est le detail de R-99999",
        epreuve=Epreuve.REFERENCE.value,
        conduite=ConduiteAttendue.SIGNALER_INEXISTANT.value,
        intention_attendue="consulter_sejour",
        entites_attendues={"reservation": "R-99999"},
    ),
    # Respect des contraintes.
    Scenario(
        identifiant="S-09",
        enonce="il y a une fuite dans la 319",
        epreuve=Epreuve.CONTRAINTE.value,
        conduite=ConduiteAttendue.PROPOSER.value,
        intention_attendue="degat_des_eaux",
        entites_attendues={"chambre": "319"},
        commentaire=(
            "Aucune chambre proposee ne doit etre occupee sur la periode, ni "
            "d'une categorie inferieure a celle contractee."
        ),
    ),
    # Prise en compte des preferences.
    Scenario(
        identifiant="S-10",
        enonce="la 319 a un souci, il me faut une chambre a cote de la 318",
        epreuve=Epreuve.PREFERENCE.value,
        conduite=ConduiteAttendue.PROPOSER.value,
        intention_attendue="incident_avec_preference",
        entites_attendues={"chambre": "319", "proximite": "318"},
        commentaire="La chambre proposee doit etre la plus proche disponible.",
    ),
    Scenario(
        identifiant="S-11",
        enonce="probleme dans la 512, trouve une chambre pres de la 508",
        epreuve=Epreuve.PREFERENCE.value,
        conduite=ConduiteAttendue.PROPOSER.value,
        intention_attendue="incident_avec_preference",
        entites_attendues={"chambre": "512", "proximite": "508"},
    ),
    # Abstention.
    Scenario(
        identifiant="S-12",
        enonce="bonjour comment allez vous",
        epreuve=Epreuve.ABSTENTION.value,
        conduite=ConduiteAttendue.REFUSER_HORS_PERIMETRE.value,
        commentaire="Aucune situation operationnelle n'est decrite.",
    ),
    Scenario(
        identifiant="S-13",
        enonce="quel temps fera-t-il demain",
        epreuve=Epreuve.ABSTENTION.value,
        conduite=ConduiteAttendue.REFUSER_HORS_PERIMETRE.value,
    ),
    Scenario(
        identifiant="S-14",
        enonce="que dois je faire",
        epreuve=Epreuve.ABSTENTION.value,
        conduite=ConduiteAttendue.REFUSER_HORS_PERIMETRE.value,
        intention_attendue="demande_conseil",
        commentaire=(
            "La demande ne designe aucune situation: le systeme doit le dire "
            "plutot que de supposer laquelle."
        ),
    ),
    # Comprehension d'une consultation du service.
    Scenario(
        identifiant="S-15",
        enonce="quels agents travaillent aujourd'hui",
        epreuve=Epreuve.COMPREHENSION.value,
        conduite=ConduiteAttendue.REPONDRE.value,
        intention_attendue="consulter_agents",
    ),
    # Arbitrage.
    Scenario(
        identifiant="S-16",
        enonce="deux clients ont reserve la 309",
        epreuve=Epreuve.ARBITRAGE.value,
        conduite=ConduiteAttendue.PROPOSER.value,
        intention_attendue="conflit_affectation",
        entites_attendues={"chambre": "309"},
        commentaire=(
            "Deux sejours occupent simultanement cette chambre: le systeme "
            "doit arbitrer et proposer un relogement."
        ),
    ),
)


def scenarios_par_epreuve(epreuve: str) -> tuple[Scenario, ...]:
    """Restitue les scenarios eprouvant un aspect donne."""
    return tuple(
        scenario for scenario in SCENARIOS if scenario.epreuve == epreuve
    )


def denombrer_par_epreuve() -> dict[str, int]:
    """Denombre les scenarios de chaque epreuve."""
    comptes: dict[str, int] = {}
    for scenario in SCENARIOS:
        comptes[scenario.epreuve] = comptes.get(scenario.epreuve, 0) + 1
    return dict(sorted(comptes.items()))
