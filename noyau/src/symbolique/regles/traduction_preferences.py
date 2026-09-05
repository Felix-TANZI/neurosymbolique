"""Traduction des preferences exprimees en faits et poids logiques.

Une preference exprimee en langue naturelle devient ici un fait du programme
logique, assorti d'un poids. Le moteur la prend alors en compte dans son
optimisation sans qu'aucune regle n'ait a etre reecrite: c'est la demande du
responsable qui oriente le choix, et non un reglage fixe.

Les faits de proximite ne sont engendres que pour les chambres qu'une
preference designe. Les produire pour l'ensemble du parc multiplierait
inutilement la taille du programme, la proximite ne concernant qu'une chambre
de reference a la fois.
"""

import logging
from collections.abc import Mapping, Sequence

from src.domaine import (
    Chambre,
    NatureDeLaPreference,
    Preference,
    Preferences,
    Reservation,
    distance_entre,
    etage_de,
)

from .traduction import identifiant_chambre, identifiant_reservation

logger = logging.getLogger(__name__)

DISTANCE_MAXIMALE_RETENUE = 12

POIDS_DES_PREFERENCES: Mapping[str, int] = {
    NatureDeLaPreference.PROXIMITE.value: 2,
    NatureDeLaPreference.ELOIGNEMENT.value: 2,
    NatureDeLaPreference.MEME_ETAGE.value: 4,
    NatureDeLaPreference.ETAGE_DESIGNE.value: 4,
    NatureDeLaPreference.SURCLASSEMENT.value: 10,
}


def poids_ajustes(
    poids: Mapping[str, int], preferences: Preferences
) -> dict[str, int]:
    """Restitue le bareme modifie par les preferences exprimees.

    Un poids exprime remplace le poids par defaut plutot que de s'y ajouter:
    deux ponderations concurrentes sur un meme motif declencheraient la regle
    de penalite deux fois, et fausseraient l'optimisation sans qu'aucune
    mesure ne le revele.
    """
    ajuste = dict(poids)
    if not preferences:
        return ajuste

    for preference in preferences:
        motif = _MOTIF_PAR_NATURE.get(preference.nature)
        if motif is not None:
            ajuste[motif] = (
                POIDS_DES_PREFERENCES.get(preference.nature, 2)
                * preference.intensite
            )

    return ajuste


def traduire_preferences(
    parc: Sequence[Chambre],
    reservation: Reservation,
    preferences: Preferences,
) -> list[str]:
    """Assemble les faits decrivant les preferences exprimees.

    Seuls les faits sont produits ici; les ponderations relevent du bareme,
    etabli par poids_ajustes et emis une seule fois par traduire_poids.
    """
    if not preferences:
        return []

    lignes: list[str] = []
    for preference in preferences:
        lignes.extend(_faits_de(parc, reservation, preference))

    logger.debug(
        "%d preferences traduites en %d faits", len(preferences), len(lignes)
    )
    return lignes


_MOTIF_PAR_NATURE: Mapping[str, str] = {
    NatureDeLaPreference.PROXIMITE.value: "proximite",
    NatureDeLaPreference.ELOIGNEMENT.value: "eloignement",
    NatureDeLaPreference.MEME_ETAGE.value: "etage_non_souhaite",
    NatureDeLaPreference.ETAGE_DESIGNE.value: "etage_non_souhaite",
    NatureDeLaPreference.SURCLASSEMENT.value: "surclassement",
}


def _faits_de(
    parc: Sequence[Chambre],
    reservation: Reservation,
    preference: Preference,
) -> list[str]:
    """Assemble les faits d'une preference donnee."""
    if preference.nature == NatureDeLaPreference.PROXIMITE.value:
        return _proximite(parc, preference.reference)

    if preference.nature == NatureDeLaPreference.ELOIGNEMENT.value:
        return _proximite(parc, preference.reference)

    if preference.nature == NatureDeLaPreference.MEME_ETAGE.value:
        return _meme_etage(parc, reservation, preference.reference)

    if preference.nature == NatureDeLaPreference.ETAGE_DESIGNE.value:
        return _etage_designe(reservation, preference.reference)

    if preference.nature == NatureDeLaPreference.SURCLASSEMENT.value:
        return []

    logger.info("preference sans traduction connue: %s", preference.nature)
    return []


def _proximite(parc: Sequence[Chambre], reference: str) -> list[str]:
    """Assemble les distances separant chaque chambre d'une reference.

    Les distances superieures au seuil retenu ne sont pas produites: au-dela,
    la proximite ne distingue plus utilement deux chambres, et les faits
    correspondants alourdiraient le programme sans profit.
    """
    designee = next(
        (chambre for chambre in parc if str(chambre.numero) == reference), None
    )
    if designee is None:
        logger.info("preference de proximite sur une chambre absente: %s", reference)
        return []

    lignes: list[str] = []

    for chambre in parc:
        if chambre.numero == designee.numero:
            continue
        distance = distance_entre(chambre.numero, designee.numero)
        if distance is not None and distance <= DISTANCE_MAXIMALE_RETENUE:
            lignes.append(
                f"distance({identifiant_chambre(chambre)}, {distance})."
            )

    return lignes


def _meme_etage(
    parc: Sequence[Chambre], reservation: Reservation, reference: str
) -> list[str]:
    """Assemble les faits designant les chambres d'un meme etage."""
    designee = next(
        (chambre for chambre in parc if str(chambre.numero) == reference), None
    )
    if designee is None:
        logger.info("preference d'etage sur une chambre absente: %s", reference)
        return []

    etage = etage_de(designee.numero)
    if etage is None:
        return []

    return [
        f"etage_souhaite({identifiant_reservation(reservation)}, {etage})."
    ]


def _etage_designe(reservation: Reservation, reference: str) -> list[str]:
    """Assemble les faits designant un etage explicitement demande."""
    if not reference.isdigit():
        return []
    return [
        f"etage_souhaite({identifiant_reservation(reservation)}, {int(reference)})."
    ]
