"""Verification de l'arbitrage des conflits d'affectation.

Un conflit n'admet pas un traitement unique: sa nature determine la conduite.
Le module doit etablir cette nature avant d'en tirer une consequence, faute de
quoi il relogerait un client sans motif ou laisserait une anomalie inapercue.
"""

from datetime import date, time, timedelta
from pathlib import Path

import pytest
from src.domaine import (
    Categorie,
    Chambre,
    Client,
    Equipement,
    EtatOccupation,
    EtatProprete,
    EtatTechnique,
    HeureArrivee,
    IdentifiantReservation,
    NumeroChambre,
    Periode,
    Reservation,
    StatutFidelite,
)
from src.orchestration import creer_cas_usage
from src.orchestration.arbitrage import (
    ArbitrerUnConflit,
    NatureDuConflit,
    _nuitees_communes,
    _sejours_qui_se_chevauchent,
)

RACINE = Path(__file__).resolve().parents[2] / "connaissances"
JOUR = date(2026, 8, 12)


def _chambre(numero: str) -> Chambre:
    """Constitue une chambre libre, prete et operationnelle."""
    return Chambre(
        numero=NumeroChambre(numero),
        etage=int(numero[0]),
        capacite=2,
        categorie=Categorie.STANDARD,
        equipements=frozenset({Equipement.LIT_DOUBLE, Equipement.CLIMATISATION}),
        etat_proprete=EtatProprete.PRETE,
        etat_technique=EtatTechnique.OPERATIONNELLE,
        etat_occupation=EtatOccupation.LIBRE,
        chambres_communicantes=frozenset(),
    )


def _sejour(
    reference: str, arrivee: date, nuitees: int, chambre: str | None = None
) -> Reservation:
    """Constitue un sejour sur une periode donnee."""
    return Reservation(
        identifiant=IdentifiantReservation(reference),
        client=Client(
            identifiant=f"C-{reference[-4:]}",
            statut_fidelite=StatutFidelite.AUCUN,
            besoins_permanents=frozenset(),
        ),
        periode=Periode(arrivee, arrivee + timedelta(days=nuitees)),
        nombre_personnes=2,
        categorie_contractee=Categorie.STANDARD,
        heure_arrivee=HeureArrivee(prevue=time(14, 0), contractuelle=time(15, 0)),
        exigences=frozenset(),
        chambre_affectee=NumeroChambre(chambre) if chambre else None,
    )


@pytest.fixture(scope="module")
def arbitre() -> ArbitrerUnConflit:
    """Constitue l'arbitre une fois pour le module."""
    return ArbitrerUnConflit(creer_cas_usage(RACINE))


class TestChevauchement:
    """Verifie la detection d'un conflit reel."""

    def test_des_sejours_qui_se_succedent_ne_constituent_pas_un_conflit(
        self,
    ) -> None:
        """Une rotation normale de chambre n'appelle aucun arbitrage."""
        premier = _sejour("R-00001", date(2026, 8, 10), 3, "309")
        second = _sejour("R-00002", date(2026, 8, 13), 2, "309")
        assert _sejours_qui_se_chevauchent([premier, second]) == ()

    def test_des_sejours_simultanes_constituent_un_conflit(self) -> None:
        premier = _sejour("R-00001", date(2026, 8, 10), 5, "309")
        second = _sejour("R-00002", date(2026, 8, 12), 3, "309")
        retenus = _sejours_qui_se_chevauchent([premier, second])
        assert len(retenus) == 2

    def test_les_nuitees_communes_sont_denombrees(self) -> None:
        premier = _sejour("R-00001", date(2026, 8, 10), 5)
        second = _sejour("R-00002", date(2026, 8, 12), 3)
        assert _nuitees_communes(premier, second) == 3

    def test_des_periodes_disjointes_n_ont_aucune_nuitee_commune(self) -> None:
        premier = _sejour("R-00001", date(2026, 8, 10), 2)
        second = _sejour("R-00002", date(2026, 8, 15), 2)
        assert _nuitees_communes(premier, second) == 0


class TestQualificationDuConflit:
    """Verifie que la nature du conflit est correctement etablie."""

    def test_aucun_sejour_commence_est_qualifie(
        self, arbitre: ArbitrerUnConflit
    ) -> None:
        """Deux sejours a venir sur la meme periode entiere."""
        premier = _sejour("R-00001", date(2026, 8, 20), 3)
        second = _sejour("R-00002", date(2026, 8, 20), 3)
        nature = arbitre._qualifier(premier, second, JOUR)
        assert nature is NatureDuConflit.AUCUN_INSTALLE

    def test_un_chevauchement_partiel_est_distingue(
        self, arbitre: ArbitrerUnConflit
    ) -> None:
        """Reloger pour deux nuits sur trois differe d'un relogement complet."""
        premier = _sejour("R-00001", date(2026, 8, 20), 3)
        second = _sejour("R-00002", date(2026, 8, 21), 3)
        nature = arbitre._qualifier(premier, second, JOUR)
        assert nature is NatureDuConflit.CHEVAUCHEMENT_PARTIEL

    def test_un_sejour_commence_est_qualifie(
        self, arbitre: ArbitrerUnConflit
    ) -> None:
        installe = _sejour("R-00001", date(2026, 8, 10), 5)
        attendu = _sejour("R-00002", date(2026, 8, 20), 3)
        nature = arbitre._qualifier(installe, attendu, JOUR)
        assert nature is NatureDuConflit.UN_INSTALLE

    def test_deux_sejours_commences_constituent_une_anomalie(
        self, arbitre: ArbitrerUnConflit
    ) -> None:
        """Deux clients dans une meme chambre revelent une erreur anterieure."""
        premier = _sejour("R-00001", date(2026, 8, 10), 5)
        second = _sejour("R-00002", date(2026, 8, 11), 4)
        nature = arbitre._qualifier(premier, second, JOUR)
        assert nature is NatureDuConflit.DEUX_INSTALLES


class TestPrioriteDeMaintien:
    """Verifie les criteres departageant les sejours concurrents."""

    def test_un_sejour_commence_est_maintenu(
        self, arbitre: ArbitrerUnConflit
    ) -> None:
        """Deloger un client installe engage un demenagement et une compensation."""
        attendu = _sejour("R-00002", date(2026, 8, 20), 3)
        installe = _sejour("R-00001", date(2026, 8, 10), 5)
        maintenu, reloge = arbitre._ordonner([attendu, installe], JOUR)
        assert maintenu.identifiant == installe.identifiant
        assert reloge.identifiant == attendu.identifiant

    def test_a_defaut_l_anteriorite_departage(
        self, arbitre: ArbitrerUnConflit
    ) -> None:
        tardif = _sejour("R-00002", date(2026, 8, 25), 3)
        precoce = _sejour("R-00001", date(2026, 8, 20), 3)
        maintenu, reloge = arbitre._ordonner([tardif, precoce], JOUR)
        assert maintenu.identifiant == precoce.identifiant
        assert reloge.identifiant == tardif.identifiant
