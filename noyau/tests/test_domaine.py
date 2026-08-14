"""Tests du domaine metier.

Les tests portent sur les invariants, dont le respect conditionne l'impossibilite
de construire un objet incoherent, et sur les comportements metier tels que le
chevauchement de periodes ou l'identite des entites.
"""

from datetime import date, datetime, time

import pytest
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
    StatutFidelite,
    TypeIncident,
    ValeurInvalideError,
)

ACCES_STANDARD = HeureArrivee(prevue=time(16, 0), contractuelle=time(15, 0))


def chambre(
    numero: str = "312",
    etage: int = 3,
    capacite: int = 2,
    categorie: Categorie = Categorie.STANDARD,
    equipements: frozenset[Equipement] = frozenset(),
    etat_proprete: EtatProprete = EtatProprete.SALE,
    etat_technique: EtatTechnique = EtatTechnique.OPERATIONNELLE,
    etat_occupation: EtatOccupation = EtatOccupation.LIBRE,
    chambres_communicantes: frozenset[NumeroChambre] = frozenset(),
) -> Chambre:
    """Construit une chambre valide dont seuls les attributs utiles sont precises."""
    return Chambre(
        numero=NumeroChambre(numero),
        etage=etage,
        capacite=capacite,
        categorie=categorie,
        equipements=equipements,
        etat_proprete=etat_proprete,
        etat_technique=etat_technique,
        etat_occupation=etat_occupation,
        chambres_communicantes=chambres_communicantes,
    )


def reservation(
    identifiant: str = "R-4471",
    client: Client | None = None,
    periode: Periode | None = None,
    nombre_personnes: int = 2,
    categorie_contractee: Categorie = Categorie.STANDARD,
    heure_arrivee: HeureArrivee = ACCES_STANDARD,
    exigences: frozenset[Exigence] = frozenset(),
) -> Reservation:
    """Construit une reservation valide dont seuls les attributs utiles sont precises."""
    return Reservation(
        identifiant=IdentifiantReservation(identifiant),
        client=client or Client("C-001"),
        periode=periode or Periode(date(2026, 8, 12), date(2026, 8, 15)),
        nombre_personnes=nombre_personnes,
        categorie_contractee=categorie_contractee,
        heure_arrivee=heure_arrivee,
        exigences=exigences,
    )


def incident(
    identifiant: str = "I-001",
    numero_chambre: str = "312",
    type_incident: TypeIncident = TypeIncident.DEGAT_DES_EAUX,
    gravite: Gravite = Gravite.MODEREE,
    resolu: bool = False,
) -> Incident:
    """Construit un incident valide dont seuls les attributs utiles sont precises."""
    return Incident(
        identifiant=identifiant,
        chambre=NumeroChambre(numero_chambre),
        type_incident=type_incident,
        gravite=gravite,
        signale_le=datetime(2026, 8, 12, 9, 30),
        resolu=resolu,
    )


class TestNumeroChambre:
    def test_un_numero_vide_est_refuse(self) -> None:
        with pytest.raises(ValeurInvalideError):
            NumeroChambre("   ")

    def test_le_numero_s_affiche_tel_quel(self) -> None:
        assert str(NumeroChambre("312")) == "312"

    def test_deux_numeros_identiques_sont_egaux(self) -> None:
        assert NumeroChambre("312") == NumeroChambre("312")


class TestIdentifiantReservation:
    def test_un_identifiant_vide_est_refuse(self) -> None:
        with pytest.raises(ValeurInvalideError):
            IdentifiantReservation("")

    def test_l_identifiant_s_affiche_tel_quel(self) -> None:
        assert str(IdentifiantReservation("R-4471")) == "R-4471"


class TestPeriode:
    def test_le_depart_doit_suivre_l_arrivee(self) -> None:
        with pytest.raises(ValeurInvalideError):
            Periode(date(2026, 8, 15), date(2026, 8, 12))

    def test_une_periode_d_une_journee_est_refusee(self) -> None:
        with pytest.raises(ValeurInvalideError):
            Periode(date(2026, 8, 12), date(2026, 8, 12))

    def test_le_nombre_de_nuitees_exclut_le_jour_de_depart(self) -> None:
        assert Periode(date(2026, 8, 12), date(2026, 8, 15)).nombre_nuitees == 3

    def test_deux_sejours_simultanes_se_chevauchent(self) -> None:
        premier = Periode(date(2026, 8, 12), date(2026, 8, 15))
        second = Periode(date(2026, 8, 14), date(2026, 8, 17))
        assert premier.chevauche(second)
        assert second.chevauche(premier)

    def test_un_sejour_inclus_dans_un_autre_se_chevauche(self) -> None:
        englobant = Periode(date(2026, 8, 10), date(2026, 8, 20))
        inclus = Periode(date(2026, 8, 12), date(2026, 8, 15))
        assert englobant.chevauche(inclus)
        assert inclus.chevauche(englobant)

    def test_un_depart_le_jour_d_une_arrivee_ne_chevauche_pas(self) -> None:
        depart = Periode(date(2026, 8, 12), date(2026, 8, 15))
        arrivee = Periode(date(2026, 8, 15), date(2026, 8, 18))
        assert not depart.chevauche(arrivee)
        assert not arrivee.chevauche(depart)

    def test_deux_sejours_disjoints_ne_chevauchent_pas(self) -> None:
        premier = Periode(date(2026, 8, 12), date(2026, 8, 15))
        second = Periode(date(2026, 8, 20), date(2026, 8, 22))
        assert not premier.chevauche(second)

    def test_le_jour_de_depart_n_appartient_pas_a_la_periode(self) -> None:
        periode = Periode(date(2026, 8, 12), date(2026, 8, 15))
        assert periode.contient(date(2026, 8, 12))
        assert periode.contient(date(2026, 8, 14))
        assert not periode.contient(date(2026, 8, 15))
        assert not periode.contient(date(2026, 8, 11))


class TestExigence:
    def test_une_exigence_obligatoire_est_bloquante(self) -> None:
        assert Exigence(Equipement.ACCES_PMR, obligatoire=True).est_bloquante

    def test_une_exigence_souhaitee_n_est_pas_bloquante(self) -> None:
        assert not Exigence(Equipement.BALCON, obligatoire=False).est_bloquante


class TestHeureArrivee:
    def test_une_arrivee_avant_l_acces_contractuel_est_anticipee(self) -> None:
        assert HeureArrivee(time(13, 0), time(15, 0)).est_anticipee()

    def test_une_arrivee_a_l_heure_n_est_pas_anticipee(self) -> None:
        assert not HeureArrivee(time(15, 0), time(15, 0)).est_anticipee()

    def test_une_arrivee_tardive_n_est_pas_anticipee(self) -> None:
        assert not HeureArrivee(time(18, 0), time(15, 0)).est_anticipee()


class TestCategorie:
    def test_les_categories_sont_ordonnees(self) -> None:
        assert Categorie.STANDARD < Categorie.SUPERIEURE
        assert Categorie.SUPERIEURE < Categorie.JUNIOR_SUITE
        assert Categorie.JUNIOR_SUITE < Categorie.SUITE

    def test_la_comparaison_large_accepte_l_egalite(self) -> None:
        assert Categorie.SUITE <= Categorie.SUITE
        assert Categorie.STANDARD <= Categorie.SUITE

    def test_une_suite_surclasse_une_standard(self) -> None:
        assert Categorie.SUITE.surclasse(Categorie.STANDARD)
        assert not Categorie.STANDARD.surclasse(Categorie.SUITE)

    def test_une_categorie_ne_se_surclasse_pas_elle_meme(self) -> None:
        assert not Categorie.SUITE.surclasse(Categorie.SUITE)


class TestGravite:
    def test_les_gravites_sont_ordonnees(self) -> None:
        assert Gravite.MINEURE < Gravite.MODEREE
        assert Gravite.MODEREE < Gravite.MAJEURE
        assert Gravite.MAJEURE < Gravite.CRITIQUE

    def test_la_comparaison_large_accepte_l_egalite(self) -> None:
        assert Gravite.MAJEURE <= Gravite.MAJEURE


class TestStatutFidelite:
    def test_les_statuts_sont_ordonnes(self) -> None:
        assert StatutFidelite.AUCUN < StatutFidelite.BRONZE
        assert StatutFidelite.OR < StatutFidelite.PLATINE

    def test_la_comparaison_large_accepte_l_egalite(self) -> None:
        assert StatutFidelite.OR <= StatutFidelite.OR


class TestChambreInvariants:
    def test_une_capacite_nulle_est_refusee(self) -> None:
        with pytest.raises(ValeurInvalideError):
            chambre(capacite=0)

    def test_une_capacite_negative_est_refusee(self) -> None:
        with pytest.raises(ValeurInvalideError):
            chambre(capacite=-2)

    def test_un_etage_negatif_est_refuse(self) -> None:
        with pytest.raises(ValeurInvalideError):
            chambre(etage=-1)

    def test_le_rez_de_chaussee_est_accepte(self) -> None:
        assert chambre(etage=0).etage == 0

    def test_une_chambre_ne_communique_pas_avec_elle_meme(self) -> None:
        with pytest.raises(ValeurInvalideError):
            chambre(chambres_communicantes=frozenset({NumeroChambre("312")}))

    def test_deux_chambres_peuvent_communiquer(self) -> None:
        voisine = chambre(chambres_communicantes=frozenset({NumeroChambre("314")}))
        assert NumeroChambre("314") in voisine.chambres_communicantes


class TestChambreAttribuabilite:
    def test_une_chambre_prete_libre_et_operationnelle_est_attribuable(self) -> None:
        assert chambre(
            etat_proprete=EtatProprete.PRETE,
            etat_occupation=EtatOccupation.LIBRE,
        ).est_attribuable

    def test_une_chambre_sale_n_est_pas_attribuable(self) -> None:
        assert not chambre(
            etat_proprete=EtatProprete.SALE,
            etat_occupation=EtatOccupation.LIBRE,
        ).est_attribuable

    def test_une_chambre_en_nettoyage_n_est_pas_attribuable(self) -> None:
        assert not chambre(
            etat_proprete=EtatProprete.EN_NETTOYAGE,
            etat_occupation=EtatOccupation.LIBRE,
        ).est_attribuable

    def test_une_chambre_a_controler_n_est_pas_attribuable(self) -> None:
        assert not chambre(
            etat_proprete=EtatProprete.A_CONTROLER,
            etat_occupation=EtatOccupation.LIBRE,
        ).est_attribuable

    def test_une_chambre_bloquee_n_est_pas_attribuable(self) -> None:
        assert not chambre(
            etat_proprete=EtatProprete.PRETE,
            etat_technique=EtatTechnique.BLOQUEE,
            etat_occupation=EtatOccupation.LIBRE,
        ).est_attribuable

    def test_une_chambre_degradee_demeure_attribuable(self) -> None:
        assert chambre(
            etat_proprete=EtatProprete.PRETE,
            etat_technique=EtatTechnique.DEGRADEE,
            etat_occupation=EtatOccupation.LIBRE,
        ).est_attribuable

    def test_une_chambre_occupee_n_est_pas_attribuable(self) -> None:
        assert not chambre(
            etat_proprete=EtatProprete.PRETE,
            etat_occupation=EtatOccupation.OCCUPEE,
        ).est_attribuable

    def test_une_chambre_deja_attribuee_n_est_pas_attribuable(self) -> None:
        assert not chambre(
            etat_proprete=EtatProprete.PRETE,
            etat_occupation=EtatOccupation.ATTRIBUEE,
        ).est_attribuable


class TestChambreEquipements:
    def test_une_chambre_expose_ses_equipements(self) -> None:
        equipee = chambre(
            equipements=frozenset({Equipement.ACCES_PMR, Equipement.CLIMATISATION})
        )
        assert equipee.dispose_de(Equipement.ACCES_PMR)
        assert equipee.dispose_de(Equipement.CLIMATISATION)
        assert not equipee.dispose_de(Equipement.BALCON)

    def test_une_chambre_sans_equipement_ne_dispose_de_rien(self) -> None:
        assert not chambre().dispose_de(Equipement.BAIGNOIRE)


class TestChambreTransitions:
    def test_le_changement_de_proprete_produit_une_nouvelle_instance(self) -> None:
        initiale = chambre(etat_proprete=EtatProprete.SALE)
        modifiee = initiale.avec_etat_proprete(EtatProprete.PRETE)
        assert initiale.etat_proprete is EtatProprete.SALE
        assert modifiee.etat_proprete is EtatProprete.PRETE

    def test_le_changement_technique_produit_une_nouvelle_instance(self) -> None:
        initiale = chambre()
        bloquee = initiale.avec_etat_technique(EtatTechnique.BLOQUEE)
        assert initiale.etat_technique is EtatTechnique.OPERATIONNELLE
        assert bloquee.etat_technique is EtatTechnique.BLOQUEE

    def test_le_changement_d_occupation_produit_une_nouvelle_instance(self) -> None:
        initiale = chambre()
        occupee = initiale.avec_etat_occupation(EtatOccupation.OCCUPEE)
        assert initiale.etat_occupation is EtatOccupation.LIBRE
        assert occupee.etat_occupation is EtatOccupation.OCCUPEE

    def test_une_transition_preserve_les_autres_attributs(self) -> None:
        initiale = chambre(capacite=4, categorie=Categorie.SUITE)
        modifiee = initiale.avec_etat_proprete(EtatProprete.PRETE)
        assert modifiee.capacite == 4
        assert modifiee.categorie is Categorie.SUITE


class TestChambreIdentite:
    def test_l_identite_prime_sur_les_attributs(self) -> None:
        sale = chambre("312", etat_proprete=EtatProprete.SALE)
        prete = chambre("312", etat_proprete=EtatProprete.PRETE)
        autre = chambre("407")
        assert sale == prete
        assert sale != autre

    def test_une_chambre_n_est_pas_egale_a_un_autre_type(self) -> None:
        assert chambre("312") != "312"

    def test_une_chambre_est_utilisable_comme_cle(self) -> None:
        assert len({chambre("312"), chambre("312"), chambre("407")}) == 2


class TestReservationInvariants:
    def test_un_nombre_de_personnes_nul_est_refuse(self) -> None:
        with pytest.raises(ValeurInvalideError):
            reservation(nombre_personnes=0)

    def test_un_nombre_de_personnes_negatif_est_refuse(self) -> None:
        with pytest.raises(ValeurInvalideError):
            reservation(nombre_personnes=-1)


class TestReservationAffectation:
    def test_une_reservation_neuve_n_est_pas_affectee(self) -> None:
        assert not reservation().est_affectee

    def test_l_affectation_produit_une_nouvelle_instance(self) -> None:
        initiale = reservation()
        affectee = initiale.avec_chambre(NumeroChambre("407"))
        assert not initiale.est_affectee
        assert affectee.est_affectee
        assert affectee.chambre_affectee == NumeroChambre("407")

    def test_une_reservation_peut_etre_desaffectee(self) -> None:
        affectee = reservation().avec_chambre(NumeroChambre("407"))
        liberee = affectee.avec_chambre(None)
        assert affectee.est_affectee
        assert not liberee.est_affectee


class TestReservationExigences:
    def test_les_exigences_sont_separees_selon_leur_caractere(self) -> None:
        exigeante = reservation(
            exigences=frozenset(
                {
                    Exigence(Equipement.ACCES_PMR, obligatoire=True),
                    Exigence(Equipement.LIT_DOUBLE, obligatoire=True),
                    Exigence(Equipement.BALCON, obligatoire=False),
                }
            )
        )
        assert exigeante.exigences_obligatoires == {
            Equipement.ACCES_PMR,
            Equipement.LIT_DOUBLE,
        }
        assert exigeante.exigences_souhaitees == {Equipement.BALCON}

    def test_une_reservation_sans_exigence_expose_des_ensembles_vides(self) -> None:
        simple = reservation()
        assert simple.exigences_obligatoires == frozenset()
        assert simple.exigences_souhaitees == frozenset()


class TestReservationIdentite:
    def test_l_identite_prime_sur_les_attributs(self) -> None:
        initiale = reservation("R-4471")
        affectee = reservation("R-4471").avec_chambre(NumeroChambre("407"))
        assert initiale == affectee
        assert initiale != reservation("R-4472")

    def test_une_reservation_n_est_pas_egale_a_un_autre_type(self) -> None:
        assert reservation("R-4471") != "R-4471"

    def test_une_reservation_est_utilisable_comme_cle(self) -> None:
        assert len({reservation("R-1"), reservation("R-1"), reservation("R-2")}) == 2


class TestClient:
    def test_un_identifiant_vide_est_refuse(self) -> None:
        with pytest.raises(ValeurInvalideError):
            Client("   ")

    def test_un_client_porte_ses_besoins_permanents(self) -> None:
        pmr = Client("C-002", besoins_permanents=frozenset({Equipement.ACCES_PMR}))
        assert Equipement.ACCES_PMR in pmr.besoins_permanents

    def test_l_identite_prime_sur_les_attributs(self) -> None:
        simple = Client("C-001")
        fidele = Client("C-001", statut_fidelite=StatutFidelite.PLATINE)
        assert simple == fidele
        assert simple != Client("C-002")

    def test_un_client_n_est_pas_egal_a_un_autre_type(self) -> None:
        assert Client("C-001") != "C-001"

    def test_un_client_est_utilisable_comme_cle(self) -> None:
        assert len({Client("C-1"), Client("C-1"), Client("C-2")}) == 2


class TestIncident:
    def test_un_identifiant_vide_est_refuse(self) -> None:
        with pytest.raises(ValeurInvalideError):
            incident(identifiant="  ")

    def test_un_incident_neuf_est_ouvert(self) -> None:
        assert incident().est_ouvert

    def test_la_resolution_produit_une_nouvelle_instance(self) -> None:
        ouvert = incident()
        ferme = ouvert.resolu_maintenant()
        assert ouvert.est_ouvert
        assert not ferme.est_ouvert

    def test_le_changement_de_gravite_produit_une_nouvelle_instance(self) -> None:
        initial = incident(gravite=Gravite.MODEREE)
        aggrave = initial.avec_gravite(Gravite.CRITIQUE)
        assert initial.gravite is Gravite.MODEREE
        assert aggrave.gravite is Gravite.CRITIQUE

    def test_l_identite_prime_sur_les_attributs(self) -> None:
        ouvert = incident("I-001")
        ferme = incident("I-001", resolu=True)
        assert ouvert == ferme
        assert ouvert != incident("I-002")

    def test_un_incident_n_est_pas_egal_a_un_autre_type(self) -> None:
        assert incident("I-001") != "I-001"

    def test_un_incident_est_utilisable_comme_cle(self) -> None:
        assert len({incident("I-1"), incident("I-1"), incident("I-2")}) == 2
