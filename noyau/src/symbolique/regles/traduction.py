"""Traduction du domaine metier vers les faits du moteur de regles.

La traduction produit un programme logique decrivant une situation
operationnelle. Elle n'exprime aucune regle: les regles resident dans les
fichiers de connaissances, editables sans modification du code.
"""

from collections.abc import Iterable, Sequence

from src.domaine import Chambre, Reservation

PREFIXE_CHAMBRE = "c"
PREFIXE_RESERVATION = "r"

POIDS_PAR_DEFAUT: dict[str, int] = {
    "souhait_non_satisfait": 3,
    "surclassement": 10,
    "hors_secteur": 2,
    "etage_non_souhaite": 1,
}


class TraductionImpossibleError(ValueError):
    """Signale une valeur du domaine sans representation logique."""


def _normaliser(valeur: str) -> str:
    """Convertit une valeur du domaine en constante logique valide."""
    normalisee = valeur.strip().lower().replace("-", "_").replace(" ", "_")
    if not normalisee:
        raise TraductionImpossibleError("valeur vide, aucune constante productible")
    return normalisee


def identifiant_chambre(chambre: Chambre) -> str:
    """Produit l'identifiant logique d'une chambre."""
    return f"{PREFIXE_CHAMBRE}{_normaliser(str(chambre.numero))}"


def identifiant_reservation(reservation: Reservation) -> str:
    """Produit l'identifiant logique d'une reservation."""
    return f"{PREFIXE_RESERVATION}{_normaliser(str(reservation.identifiant))}"


def traduire_chambre(chambre: Chambre) -> list[str]:
    """Produit les faits decrivant une chambre."""
    reference = identifiant_chambre(chambre)
    faits = [
        f"chambre({reference}).",
        f"etat_proprete({reference}, {chambre.etat_proprete.value}).",
        f"etat_technique({reference}, {chambre.etat_technique.value}).",
        f"etat_occupation({reference}, {chambre.etat_occupation.value}).",
        f"capacite({reference}, {chambre.capacite}).",
        f"categorie({reference}, {chambre.categorie.value}).",
        f"etage({reference}, {chambre.etage}).",
    ]
    faits.extend(
        f"dispose_de({reference}, {equipement.value})."
        for equipement in sorted(chambre.equipements)
    )
    faits.extend(
        f"communique_avec({reference}, "
        f"{PREFIXE_CHAMBRE}{_normaliser(str(voisine))})."
        for voisine in sorted(chambre.chambres_communicantes, key=str)
    )
    return faits


def traduire_reservation(
    reservation: Reservation, a_affecter: bool = True
) -> list[str]:
    """Produit les faits decrivant une reservation et ses exigences.

    L'indicateur a_affecter distingue la reservation dont l'affectation est
    recherchee de celles qui occupent deja le parc.
    """
    reference = identifiant_reservation(reservation)
    faits = [
        f"reservation({reference}).",
        f"nombre_personnes({reference}, {reservation.nombre_personnes}).",
        f"categorie_contractee({reference}, {reservation.categorie_contractee.value}).",
        f"arrivee({reference}, {reservation.periode.arrivee.toordinal()}).",
        f"depart({reference}, {reservation.periode.depart.toordinal()}).",
        f"fidelite({reference}, {reservation.client.statut_fidelite.value}).",
    ]
    if a_affecter:
        faits.append(f"a_affecter({reference}).")
    faits.extend(
        f"exigence_obligatoire({reference}, {equipement.value})."
        for equipement in sorted(reservation.exigences_obligatoires)
    )
    faits.extend(
        f"exigence_souhaitee({reference}, {equipement.value})."
        for equipement in sorted(reservation.exigences_souhaitees)
    )
    if reservation.chambre_affectee is not None:
        occupee = f"{PREFIXE_CHAMBRE}{_normaliser(str(reservation.chambre_affectee))}"
        faits.append(f"occupation_existante({occupee}, {reference}).")
    return faits


def traduire_chevauchements(reservations: Sequence[Reservation]) -> list[str]:
    """Produit les faits de chevauchement entre sejours.

    Le calcul est effectue par le domaine, dont les regles de convention
    hoteliere font autorite, plutot que reimplemente en logique.
    """
    faits: list[str] = []
    for rang, premiere in enumerate(reservations):
        for seconde in reservations[rang + 1 :]:
            if premiere.periode.chevauche(seconde.periode):
                gauche = identifiant_reservation(premiere)
                droite = identifiant_reservation(seconde)
                faits.append(f"chevauchent({gauche}, {droite}).")
                faits.append(f"chevauchent({droite}, {gauche}).")
    return faits


def traduire_poids(poids: dict[str, int]) -> list[str]:
    """Produit les faits de ponderation des preferences souples."""
    return [
        f"poids({_normaliser(motif)}, {valeur})." for motif, valeur in poids.items()
    ]


def traduire_situation(
    chambres: Iterable[Chambre],
    reservation_a_affecter: Reservation,
    occupations: Iterable[Reservation] = (),
    poids: dict[str, int] | None = None,
) -> str:
    """Assemble le programme logique decrivant une situation complete."""
    lignes: list[str] = []

    for chambre in chambres:
        lignes.extend(traduire_chambre(chambre))

    lignes.extend(traduire_reservation(reservation_a_affecter, a_affecter=True))

    presentes = list(occupations)
    for occupation in presentes:
        lignes.extend(traduire_reservation(occupation, a_affecter=False))

    lignes.extend(traduire_chevauchements([reservation_a_affecter, *presentes]))
    lignes.extend(traduire_poids(poids or POIDS_PAR_DEFAUT))

    return "\n".join(lignes)
