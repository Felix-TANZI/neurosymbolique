"""Schema de l'ontologie du service de gestion des chambres.

Le schema est derive du domaine metier: les classes d'etats sont engendrees a
partir des enumerations de src.domaine. Le domaine demeure ainsi la source
unique de verite, et l'ajout d'un etat s'y propage sans double saisie.
"""

import types
from typing import Any

from owlready2 import DataProperty, FunctionalProperty, ObjectProperty, Ontology, Thing

from src.domaine import (
    Categorie,
    EtatOccupation,
    EtatProprete,
    EtatTechnique,
)


def _nom_de_classe(valeur: Any) -> str:
    """Convertit un membre d'enumeration en nom de classe OWL."""
    return "".join(mot.capitalize() for mot in valeur.name.split("_"))


def _engendrer_sous_classes(
    onto: Ontology, base: type[Thing], enumeration: type[Any]
) -> dict[Any, type[Thing]]:
    """Cree une sous-classe OWL par membre de l'enumeration fournie."""
    produites: dict[Any, type[Thing]] = {}
    for membre in enumeration:
        classe = types.new_class(
            _nom_de_classe(membre),
            (base,),
            exec_body=lambda espace: espace.update({"namespace": onto}),
        )
        produites[membre] = classe
    return produites


def definir_chambre_indisponible(
    onto: Ontology,
    chambre: type[Thing],
    proprietes: dict[str, Any],
    classes: dict[str, dict[Any, type[Thing]]],
) -> None:
    """Declare la classe des chambres inaptes a recevoir une reservation.

    L'appartenance n'est jamais declaree: elle est deduite par le raisonneur a
    partir des etats de la chambre. Les restrictions OWL relevant du mecanisme
    dynamique d'Owlready2, leur construction est isolee dans cette fonction.
    """
    proprete = classes["proprete"]
    technique = classes["technique"]
    occupation = classes["occupation"]
    condition = chambre & (
        proprietes["technique"].some(technique[EtatTechnique.BLOQUEE])
        | proprietes["proprete"].some(proprete[EtatProprete.SALE])
        | proprietes["proprete"].some(proprete[EtatProprete.EN_NETTOYAGE])
        | proprietes["proprete"].some(proprete[EtatProprete.A_CONTROLER])
        | proprietes["occupation"].some(occupation[EtatOccupation.ATTRIBUEE])
        | proprietes["occupation"].some(occupation[EtatOccupation.OCCUPEE])
    )
    with onto:
        indisponible: Any = types.new_class(
            "ChambreIndisponible",
            (chambre,),
            exec_body=lambda espace: espace.update({"namespace": onto}),
        )
    indisponible.equivalent_to = [condition]


def construire_schema(onto: Ontology) -> None:
    """Declare l'integralite du schema dans l'ontologie fournie."""

    with onto:

        class Chambre(Thing):
            pass

        class Reservation(Thing):
            pass

        class Client(Thing):
            pass

        class Incident(Thing):
            pass

        class CategorieChambre(Thing):
            pass

        class Equipement(Thing):
            pass

        class Exigence(Thing):
            pass

        class EtatDeProprete(Thing):
            pass

        class EtatDeTechnique(Thing):
            pass

        class EtatDOccupation(Thing):
            pass

    classes = {
        "proprete": _engendrer_sous_classes(onto, EtatDeProprete, EtatProprete),
        "technique": _engendrer_sous_classes(onto, EtatDeTechnique, EtatTechnique),
        "occupation": _engendrer_sous_classes(onto, EtatDOccupation, EtatOccupation),
    }
    _engendrer_sous_classes(onto, CategorieChambre, Categorie)

    with onto:

        class aEtatProprete(ObjectProperty, FunctionalProperty):
            domain = [Chambre]
            range = [EtatDeProprete]

        class aEtatTechnique(ObjectProperty, FunctionalProperty):
            domain = [Chambre]
            range = [EtatDeTechnique]

        class aEtatOccupation(ObjectProperty, FunctionalProperty):
            domain = [Chambre]
            range = [EtatDOccupation]

        class aCategorie(ObjectProperty, FunctionalProperty):
            domain = [Chambre]
            range = [CategorieChambre]

        class disposeDe(ObjectProperty):
            domain = [Chambre]
            range = [Equipement]

        class communiqueAvec(ObjectProperty):
            domain = [Chambre]
            range = [Chambre]
            symmetric = True

        class estAffecteeA(ObjectProperty, FunctionalProperty):
            domain = [Reservation]
            range = [Chambre]

        class recoitReservation(ObjectProperty):
            domain = [Chambre]
            range = [Reservation]
            inverse_property = estAffecteeA

        class estTitulaire(ObjectProperty, FunctionalProperty):
            domain = [Reservation]
            range = [Client]

        class comporteExigence(ObjectProperty):
            domain = [Reservation]
            range = [Exigence]

        class exigeCategorie(ObjectProperty, FunctionalProperty):
            domain = [Reservation]
            range = [CategorieChambre]

        class satisfaitePar(ObjectProperty, FunctionalProperty):
            domain = [Exigence]
            range = [Equipement]

        class affecteChambre(ObjectProperty, FunctionalProperty):
            domain = [Incident]
            range = [Chambre]

        class aNumero(DataProperty, FunctionalProperty):
            domain = [Chambre]
            range = [str]

        class aEtage(DataProperty, FunctionalProperty):
            domain = [Chambre]
            range = [int]

        class aCapacite(DataProperty, FunctionalProperty):
            domain = [Chambre]
            range = [int]

        class aRang(DataProperty, FunctionalProperty):
            domain = [CategorieChambre]
            range = [int]

        class aIdentifiant(DataProperty, FunctionalProperty):
            domain = [Thing]
            range = [str]

        class aNombrePersonnes(DataProperty, FunctionalProperty):
            domain = [Reservation]
            range = [int]

        class estObligatoire(DataProperty, FunctionalProperty):
            domain = [Exigence]
            range = [bool]

    definir_chambre_indisponible(
        onto,
        Chambre,
        {
            "proprete": aEtatProprete,
            "technique": aEtatTechnique,
            "occupation": aEtatOccupation,
        },
        classes,
    )
