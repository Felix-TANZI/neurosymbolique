"""Tests de la projection du domaine vers l'ontologie.

La validation croisee compare les deductions du raisonneur aux conclusions de
la methode est_attribuable du domaine: deux chemins independants doivent
aboutir au meme resultat.
"""

from datetime import date, datetime, time
from itertools import product
from typing import Any

import pytest
from owlready2 import Ontology, sync_reasoner
from src.domaine import (
    Categorie,
    Chambre,
    Client,
    Equipement,
    EtatOccupation,
    EtatProprete,
    EtatTechnique,
    Exigence,
    Gravite,
    HeureArrivee,
    IdentifiantReservation,
    Incident,
    NumeroChambre,
    Periode,
    Reservation,
    TypeIncident,
)
from src.symbolique.ontologie.projection import (
    ValeurNonProjetableError,
    creer_ontologie,
    projeter_chambre,
    projeter_incident,
    projeter_reservation,
    projeter_situation,
)

ACCES_STANDARD = HeureArrivee(prevue=time(16, 0), contractuelle=time(15, 0))


def chambre(
    numero: str = "312",
    proprete: EtatProprete = EtatProprete.PRETE,
    technique: EtatTechnique = EtatTechnique.OPERATIONNELLE,
    occupation: EtatOccupation = EtatOccupation.LIBRE,
    equipements: frozenset[Equipement] = frozenset(),
    communicantes: frozenset[NumeroChambre] = frozenset(),
) -> Chambre:
    """Construit une chambre du domaine dont seuls les etats utiles sont precises."""
    return Chambre(
        numero=NumeroChambre(numero),
        etage=3,
        capacite=2,
        categorie=Categorie.STANDARD,
        equipements=equipements,
        etat_proprete=proprete,
        etat_technique=technique,
        etat_occupation=occupation,
        chambres_communicantes=communicantes,
    )


def reservation(
    identifiant: str = "R-4471",
    exigences: frozenset[Exigence] = frozenset(),
    chambre_affectee: NumeroChambre | None = None,
) -> Reservation:
    """Construit une reservation du domaine avec des valeurs par defaut valides."""
    return Reservation(
        identifiant=IdentifiantReservation(identifiant),
        client=Client("C-001"),
        periode=Periode(date(2026, 8, 12), date(2026, 8, 15)),
        nombre_personnes=2,
        categorie_contractee=Categorie.STANDARD,
        heure_arrivee=ACCES_STANDARD,
        exigences=exigences,
        chambre_affectee=chambre_affectee,
    )


def incident(identifiant: str = "I-001", numero: str = "312") -> Incident:
    """Construit un incident du domaine rattache a une chambre donnee."""
    return Incident(
        identifiant=identifiant,
        chambre=NumeroChambre(numero),
        type_incident=TypeIncident.DEGAT_DES_EAUX,
        gravite=Gravite.MAJEURE,
        signale_le=datetime(2026, 8, 12, 9, 30),
    )


class TestProjectionChambre:
    def test_les_attributs_sont_reportes(self) -> None:
        onto = creer_ontologie()
        individu = projeter_chambre(onto, chambre("312"))
        assert individu.aNumero == "312"
        assert individu.aEtage == 3
        assert individu.aCapacite == 2

    def test_les_trois_etats_sont_rattaches(self) -> None:
        onto = creer_ontologie()
        individu = projeter_chambre(
            onto,
            chambre(proprete=EtatProprete.A_CONTROLER, technique=EtatTechnique.DEGRADEE),
        )
        assert isinstance(individu.aEtatProprete, onto.AControler)
        assert isinstance(individu.aEtatTechnique, onto.Degradee)
        assert isinstance(individu.aEtatOccupation, onto.Libre)

    def test_les_equipements_sont_projetes(self) -> None:
        onto = creer_ontologie()
        individu = projeter_chambre(
            onto,
            chambre(equipements=frozenset({Equipement.ACCES_PMR, Equipement.BALCON})),
        )
        assert len(individu.disposeDe) == 2

    def test_un_equipement_est_partage_entre_les_chambres(self) -> None:
        onto = creer_ontologie()
        premiere = projeter_chambre(
            onto, chambre("401", equipements=frozenset({Equipement.ACCES_PMR}))
        )
        seconde = projeter_chambre(
            onto, chambre("402", equipements=frozenset({Equipement.ACCES_PMR}))
        )
        assert premiere.disposeDe[0] is seconde.disposeDe[0]

    def test_chaque_chambre_possede_ses_propres_individus_d_etat(self) -> None:
        onto = creer_ontologie()
        premiere = projeter_chambre(onto, chambre("401"))
        seconde = projeter_chambre(onto, chambre("402"))
        assert premiere.aEtatProprete is not seconde.aEtatProprete


class TestProjectionReservation:
    def test_les_attributs_sont_reportes(self) -> None:
        onto = creer_ontologie()
        individu = projeter_reservation(onto, reservation("R-4471"))
        assert individu.aIdentifiant == "R-4471"
        assert individu.aNombrePersonnes == 2

    def test_le_client_est_projete_et_relie(self) -> None:
        onto = creer_ontologie()
        individu = projeter_reservation(onto, reservation())
        assert individu.estTitulaire.aIdentifiant == "C-001"

    def test_les_exigences_conservent_leur_caractere(self) -> None:
        onto = creer_ontologie()
        individu = projeter_reservation(
            onto,
            reservation(
                exigences=frozenset(
                    {
                        Exigence(Equipement.ACCES_PMR, obligatoire=True),
                        Exigence(Equipement.BALCON, obligatoire=False),
                    }
                )
            ),
        )
        caracteres = {e.satisfaitePar.name: e.estObligatoire for e in individu.comporteExigence}
        assert caracteres["equipement_acces_pmr"] is True
        assert caracteres["equipement_balcon"] is False

    def test_l_affectation_est_projetee(self) -> None:
        onto = creer_ontologie()
        projeter_chambre(onto, chambre("407"))
        individu = projeter_reservation(
            onto, reservation(chambre_affectee=NumeroChambre("407"))
        )
        assert individu.estAffecteeA.aNumero == "407"

    def test_l_affectation_expose_la_relation_inverse(self) -> None:
        onto = creer_ontologie()
        chambre_projetee = projeter_chambre(onto, chambre("407"))
        individu = projeter_reservation(
            onto, reservation(chambre_affectee=NumeroChambre("407"))
        )
        assert individu in chambre_projetee.recoitReservation

    def test_une_affectation_vers_une_chambre_absente_est_refusee(self) -> None:
        onto = creer_ontologie()
        with pytest.raises(ValeurNonProjetableError):
            projeter_reservation(
                onto, reservation(chambre_affectee=NumeroChambre("999"))
            )


class TestProjectionIncident:
    def test_l_incident_est_relie_a_sa_chambre(self) -> None:
        onto = creer_ontologie()
        projeter_chambre(onto, chambre("312"))
        individu = projeter_incident(onto, incident())
        assert individu.affecteChambre.aNumero == "312"

    def test_un_incident_sur_une_chambre_absente_est_refuse(self) -> None:
        onto = creer_ontologie()
        with pytest.raises(ValeurNonProjetableError):
            projeter_incident(onto, incident(numero="999"))


class TestProjectionSituation:
    def test_une_situation_complete_est_projetee(self) -> None:
        onto = projeter_situation(
            chambres=[chambre("401"), chambre("402")],
            reservations=[reservation("R-1", chambre_affectee=NumeroChambre("401"))],
            incidents=[incident("I-1", numero="402")],
        )
        assert len(list(onto.Chambre.instances())) == 2
        assert len(list(onto.Reservation.instances())) == 1
        assert len(list(onto.Incident.instances())) == 1

    def test_les_chambres_communicantes_sont_reliees(self) -> None:
        onto = projeter_situation(
            chambres=[
                chambre("401", communicantes=frozenset({NumeroChambre("402")})),
                chambre("402", communicantes=frozenset({NumeroChambre("401")})),
            ]
        )
        assert onto.chambre_402 in onto.chambre_401.communiqueAvec

    def test_un_lien_vers_une_chambre_absente_est_ignore(self) -> None:
        onto = projeter_situation(
            chambres=[chambre("401", communicantes=frozenset({NumeroChambre("999")}))]
        )
        assert onto.chambre_401.communiqueAvec == []

    def test_deux_projections_sont_isolees(self) -> None:
        premiere = projeter_situation(chambres=[chambre("401")])
        seconde = projeter_situation(chambres=[chambre("402")])
        assert len(list(premiere.Chambre.instances())) == 1
        assert len(list(seconde.Chambre.instances())) == 1


def _raisonner(onto: Ontology) -> None:
    """Execute le raisonneur sur l'ontologie fournie.

    L'appel est isole car le raisonneur d'Owlready2 n'expose pas de signature
    typee.
    """
    moteur: Any = sync_reasoner
    with onto:
        moteur(onto, debug=0)


@pytest.fixture(scope="module")
def parc_raisonne() -> tuple[Ontology, dict[str, Chambre]]:
    """Projette toutes les combinaisons d'etats puis raisonne une seule fois."""
    combinaisons = product(EtatProprete, EtatTechnique, EtatOccupation)
    parc: dict[str, Chambre] = {}
    for rang, (proprete, technique, occupation) in enumerate(combinaisons, start=1):
        numero = f"{rang:03d}"
        parc[numero] = chambre(
            numero, proprete=proprete, technique=technique, occupation=occupation
        )
    onto = projeter_situation(chambres=list(parc.values()))
    _raisonner(onto)
    return onto, parc


class TestValidationCroisee:
    """Compare les deductions du raisonneur aux conclusions du domaine Python."""

    def test_le_parc_couvre_toutes_les_combinaisons_d_etats(
        self, parc_raisonne: tuple[Ontology, dict[str, Chambre]]
    ) -> None:
        _, parc = parc_raisonne
        assert len(parc) == 4 * 3 * 3

    def test_les_deductions_concordent_avec_le_domaine(
        self, parc_raisonne: tuple[Ontology, dict[str, Chambre]]
    ) -> None:
        onto, parc = parc_raisonne
        for numero, chambre_domaine in parc.items():
            individu = getattr(onto, f"chambre_{numero}")
            deduite_indisponible = onto.ChambreIndisponible in individu.is_a
            assert deduite_indisponible is not chambre_domaine.est_attribuable, (
                f"divergence sur la chambre {numero}: "
                f"domaine={chambre_domaine.est_attribuable}, "
                f"ontologie={not deduite_indisponible}"
            )

    def test_au_moins_une_chambre_demeure_attribuable(
        self, parc_raisonne: tuple[Ontology, dict[str, Chambre]]
    ) -> None:
        _, parc = parc_raisonne
        assert any(chambre.est_attribuable for chambre in parc.values())
