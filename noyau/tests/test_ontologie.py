"""Tests de l'ontologie du service de gestion des chambres.

Les tests verifient que l'appartenance a une classe definie est deduite par le
raisonneur a partir des etats de la chambre, et non declaree explicitement.
"""

from typing import Any

import pytest
from owlready2 import Ontology, get_ontology, sync_reasoner
from src.domaine import Categorie, EtatOccupation, EtatProprete, EtatTechnique
from src.symbolique.ontologie.schema import construire_schema

COMPTEUR = iter(range(1, 10_000))


def ontologie_neuve() -> Ontology:
    """Cree une ontologie isolee, chaque test disposant de son propre espace.

    La fabrique d'ontologie d'Owlready2 n'etant pas typee, son resultat est
    declare explicitement.
    """
    fabrique: Any = get_ontology
    onto: Ontology = fabrique(f"http://exemple.org/hotel/test{next(COMPTEUR)}.owl")
    construire_schema(onto)
    return onto


def _raisonner(onto: Ontology) -> None:
    """Execute le raisonneur sur l'ontologie fournie.

    L'appel est isole car le raisonneur d'Owlready2 n'expose pas de signature
    typee.
    """
    moteur: Any = sync_reasoner
    with onto:
        moteur(onto, debug=0)


def declarer_chambre(
    onto: Ontology,
    numero: str,
    proprete: EtatProprete = EtatProprete.PRETE,
    technique: EtatTechnique = EtatTechnique.OPERATIONNELLE,
    occupation: EtatOccupation = EtatOccupation.LIBRE,
) -> Any:
    """Cree une chambre dans l'ontologie et lui rattache ses trois etats."""
    classes: dict[str, Any] = {
        "proprete": getattr(onto, _en_capwords(proprete.name)),
        "technique": getattr(onto, _en_capwords(technique.name)),
        "occupation": getattr(onto, _en_capwords(occupation.name)),
    }
    with onto:
        chambre = onto.Chambre(f"chambre_{numero}")
        chambre.aNumero = numero
        chambre.aEtatProprete = classes["proprete"](f"proprete_{numero}")
        chambre.aEtatTechnique = classes["technique"](f"technique_{numero}")
        chambre.aEtatOccupation = classes["occupation"](f"occupation_{numero}")
    return chambre


def _en_capwords(nom: str) -> str:
    return "".join(mot.capitalize() for mot in nom.split("_"))


class TestSchema:
    def test_les_classes_du_domaine_sont_declarees(self) -> None:
        onto = ontologie_neuve()
        for nom in ("Chambre", "Reservation", "Client", "Incident", "Exigence"):
            assert getattr(onto, nom) is not None

    def test_une_classe_est_engendree_par_etat_de_proprete(self) -> None:
        onto = ontologie_neuve()
        for etat in EtatProprete:
            assert getattr(onto, _en_capwords(etat.name)) is not None

    def test_une_classe_est_engendree_par_categorie(self) -> None:
        onto = ontologie_neuve()
        for categorie in Categorie:
            assert getattr(onto, _en_capwords(categorie.name)) is not None

    def test_la_relation_d_affectation_expose_son_inverse(self) -> None:
        onto = ontologie_neuve()
        assert onto.recoitReservation.inverse_property is onto.estAffecteeA

    def test_la_communication_entre_chambres_est_symetrique(self) -> None:
        onto = ontologie_neuve()
        assert onto.communiqueAvec.symmetric is True


class TestDeduction:
    @pytest.fixture(scope="class")
    def onto_raisonnee(self) -> Ontology:
        """Construit un parc de chambres puis execute le raisonneur une seule fois."""
        onto = ontologie_neuve()
        declarer_chambre(onto, "401", proprete=EtatProprete.PRETE)
        declarer_chambre(onto, "402", proprete=EtatProprete.SALE)
        declarer_chambre(onto, "403", proprete=EtatProprete.EN_NETTOYAGE)
        declarer_chambre(onto, "404", proprete=EtatProprete.A_CONTROLER)
        declarer_chambre(onto, "405", technique=EtatTechnique.BLOQUEE)
        declarer_chambre(onto, "406", technique=EtatTechnique.DEGRADEE)
        _raisonner(onto)
        return onto

    def test_une_chambre_prete_et_operationnelle_n_est_pas_indisponible(
        self, onto_raisonnee: Ontology
    ) -> None:
        assert onto_raisonnee.ChambreIndisponible not in onto_raisonnee.chambre_401.is_a

    def test_une_chambre_sale_est_deduite_indisponible(
        self, onto_raisonnee: Ontology
    ) -> None:
        assert onto_raisonnee.ChambreIndisponible in onto_raisonnee.chambre_402.is_a

    def test_une_chambre_en_nettoyage_est_deduite_indisponible(
        self, onto_raisonnee: Ontology
    ) -> None:
        assert onto_raisonnee.ChambreIndisponible in onto_raisonnee.chambre_403.is_a

    def test_une_chambre_a_controler_est_deduite_indisponible(
        self, onto_raisonnee: Ontology
    ) -> None:
        assert onto_raisonnee.ChambreIndisponible in onto_raisonnee.chambre_404.is_a

    def test_une_chambre_bloquee_est_deduite_indisponible(
        self, onto_raisonnee: Ontology
    ) -> None:
        assert onto_raisonnee.ChambreIndisponible in onto_raisonnee.chambre_405.is_a

    def test_une_chambre_degradee_demeure_disponible(
        self, onto_raisonnee: Ontology
    ) -> None:
        assert onto_raisonnee.ChambreIndisponible not in onto_raisonnee.chambre_406.is_a
