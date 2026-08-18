"""Projection du domaine metier vers l'ontologie.

La projection est unidirectionnelle: elle construit une ontologie a partir
d'objets du domaine, jamais l'inverse. L'ontologie sert au raisonnement puis
est abandonnee; le domaine demeure l'unique representation persistante.
"""

import logging
from collections.abc import Iterable
from itertools import count
from typing import Any

from owlready2 import Ontology, get_ontology

from src.domaine import Chambre, Incident, NumeroChambre, Reservation

from .schema import construire_schema

logger = logging.getLogger(__name__)

_SEQUENCE = count(1)


class ValeurNonProjetableError(ValueError):
    """Signale une valeur du domaine sans correspondance dans l'ontologie."""


def _en_capwords(nom: str) -> str:
    """Convertit un nom de membre d'enumeration en nom de classe OWL."""
    return "".join(mot.capitalize() for mot in nom.split("_"))


def _identite(valeur: str) -> str:
    """Produit un identifiant OWL valide a partir d'une valeur du domaine."""
    return valeur.replace(" ", "_").replace("-", "_")


def creer_ontologie(iri: str | None = None) -> Ontology:
    """Cree une ontologie vide dotee du schema du domaine.

    Chaque appel produit un espace isole, ce qui evite toute accumulation
    d'individus entre deux raisonnements successifs. La fabrique d'ontologie
    d'Owlready2 n'etant pas typee, son resultat est declare explicitement.
    """
    adresse = iri or f"http://exemple.org/hotel/situation{next(_SEQUENCE)}.owl"
    fabrique: Any = get_ontology
    onto: Ontology = fabrique(adresse)
    construire_schema(onto)
    return onto


def _instancier_etat(onto: Ontology, nom_membre: str, reference: str) -> Any:
    """Instancie la classe OWL correspondant a un membre d'enumeration du domaine."""
    classe = getattr(onto, _en_capwords(nom_membre), None)
    if classe is None:
        raise ValeurNonProjetableError(
            f"aucune classe ontologique pour la valeur {nom_membre}"
        )
    return classe(reference)


def _instancier_equipement(onto: Ontology, nom_membre: str) -> Any:
    """Instancie un equipement, partage entre toutes les chambres qui en disposent."""
    return onto.Equipement(f"equipement_{nom_membre.lower()}")


def _chambre_existante(onto: Ontology, numero: NumeroChambre) -> Any:
    """Retrouve l'individu d'une chambre deja projetee."""
    individu = getattr(onto, f"chambre_{_identite(str(numero))}", None)
    if individu is None:
        raise ValeurNonProjetableError(f"chambre non projetee: {numero}")
    return individu


def projeter_chambre(onto: Ontology, chambre: Chambre) -> Any:
    """Cree l'individu correspondant a une chambre et rattache ses etats."""
    reference = _identite(str(chambre.numero))
    with onto:
        individu = onto.Chambre(f"chambre_{reference}")
        individu.aNumero = str(chambre.numero)
        individu.aEtage = chambre.etage
        individu.aCapacite = chambre.capacite
        individu.aEtatProprete = _instancier_etat(
            onto, chambre.etat_proprete.name, f"proprete_{reference}"
        )
        individu.aEtatTechnique = _instancier_etat(
            onto, chambre.etat_technique.name, f"technique_{reference}"
        )
        individu.aEtatOccupation = _instancier_etat(
            onto, chambre.etat_occupation.name, f"occupation_{reference}"
        )
        individu.aCategorie = _instancier_etat(
            onto, chambre.categorie.name, f"categorie_{reference}"
        )
        individu.disposeDe = [
            _instancier_equipement(onto, equipement.name)
            for equipement in sorted(chambre.equipements)
        ]
    return individu


def _projeter_exigence(
    onto: Ontology, reference: str, equipement: str, obligatoire: bool
) -> Any:
    """Cree l'individu d'une exigence et le relie a l'equipement qui la satisfait."""
    individu = onto.Exigence(f"exigence_{reference}_{equipement.lower()}")
    individu.estObligatoire = obligatoire
    individu.satisfaitePar = _instancier_equipement(onto, equipement)
    return individu


def projeter_reservation(onto: Ontology, reservation: Reservation) -> Any:
    """Cree l'individu correspondant a une reservation et ses exigences."""
    reference = _identite(str(reservation.identifiant))
    with onto:
        individu = onto.Reservation(f"reservation_{reference}")
        individu.aIdentifiant = str(reservation.identifiant)
        individu.aNombrePersonnes = reservation.nombre_personnes
        individu.exigeCategorie = _instancier_etat(
            onto,
            reservation.categorie_contractee.name,
            f"categorie_contractee_{reference}",
        )

        client = onto.Client(f"client_{_identite(reservation.client.identifiant)}")
        client.aIdentifiant = reservation.client.identifiant
        individu.estTitulaire = client

        individu.comporteExigence = [
            _projeter_exigence(
                onto, reference, exigence.equipement.name, exigence.obligatoire
            )
            for exigence in sorted(
                reservation.exigences, key=lambda e: e.equipement.name
            )
        ]

        if reservation.chambre_affectee is not None:
            individu.estAffecteeA = _chambre_existante(
                onto, reservation.chambre_affectee
            )
    return individu


def projeter_incident(onto: Ontology, incident: Incident) -> Any:
    """Cree l'individu correspondant a un incident et le relie a sa chambre."""
    reference = _identite(incident.identifiant)
    with onto:
        individu = onto.Incident(f"incident_{reference}")
        individu.aIdentifiant = incident.identifiant
        individu.affecteChambre = _chambre_existante(onto, incident.chambre)
    return individu


def _projeter_communications(onto: Ontology, parc: list[Chambre]) -> None:
    """Etablit les liens de communication entre chambres effectivement projetees."""
    presentes = {chambre.numero for chambre in parc}
    with onto:
        for chambre in parc:
            voisines = chambre.chambres_communicantes & presentes
            if not voisines:
                continue
            individu = _chambre_existante(onto, chambre.numero)
            individu.communiqueAvec = [
                _chambre_existante(onto, voisine)
                for voisine in sorted(voisines, key=str)
            ]


def projeter_situation(
    chambres: Iterable[Chambre],
    reservations: Iterable[Reservation] = (),
    incidents: Iterable[Incident] = (),
    iri: str | None = None,
) -> Ontology:
    """Construit une ontologie complete decrivant une situation operationnelle.

    Les chambres sont projetees en premier, les reservations et incidents s'y
    rattachant ensuite par leur numero de chambre.
    """
    onto = creer_ontologie(iri)

    parc = list(chambres)
    for chambre in parc:
        projeter_chambre(onto, chambre)

    _projeter_communications(onto, parc)

    for reservation in reservations:
        projeter_reservation(onto, reservation)

    for incident in incidents:
        projeter_incident(onto, incident)

    logger.debug("situation projetee: %d chambres", len(parc))
    return onto
