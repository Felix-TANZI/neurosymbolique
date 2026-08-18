"""Tests de l'orchestration du cycle de decision.

Les tests verifient l'enchainement des composants et le traitement de leurs
defaillances. La logique metier, verifiee par les tests du moteur de regles et
de la gouvernance, n'est pas reprise ici: seule est controlee l'absence de
decision propre a l'orchestration.
"""

from datetime import date, time
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
    Exigence,
    HeureArrivee,
    IdentifiantReservation,
    NumeroChambre,
    Periode,
    Reservation,
)
from src.gouvernance import GabaritIntrouvableError
from src.orchestration import (
    AffecterChambre,
    Connaissances,
    ConnaissancesIndisponiblesError,
    Demande,
    DemandeInvalideError,
    creer_cas_usage,
    demande_depuis,
)
from src.symbolique.regles import MoteurIndisponibleError

RACINE_CONNAISSANCES = Path(__file__).resolve().parents[2] / "connaissances"
ACCES_STANDARD = HeureArrivee(prevue=time(16, 0), contractuelle=time(15, 0))
SEJOUR = Periode(date(2026, 8, 12), date(2026, 8, 15))


@pytest.fixture(scope="module")
def cas_usage() -> AffecterChambre:
    """Construit une seule fois le cas d'usage et sa base de connaissances."""
    return creer_cas_usage(RACINE_CONNAISSANCES)


def chambre(
    numero: str,
    proprete: EtatProprete = EtatProprete.PRETE,
    technique: EtatTechnique = EtatTechnique.OPERATIONNELLE,
    occupation: EtatOccupation = EtatOccupation.LIBRE,
    capacite: int = 2,
    categorie: Categorie = Categorie.STANDARD,
    equipements: frozenset[Equipement] = frozenset(),
) -> Chambre:
    """Construit une chambre du domaine dont seuls les attributs utiles varient."""
    return Chambre(
        numero=NumeroChambre(numero),
        etage=3,
        capacite=capacite,
        categorie=categorie,
        equipements=equipements,
        etat_proprete=proprete,
        etat_technique=technique,
        etat_occupation=occupation,
    )


def reservation(
    identifiant: str = "R-4471",
    nombre_personnes: int = 2,
    exigences: frozenset[Exigence] = frozenset(),
    periode: Periode = SEJOUR,
    chambre_affectee: NumeroChambre | None = None,
) -> Reservation:
    """Construit une reservation du domaine avec des valeurs par defaut valides."""
    return Reservation(
        identifiant=IdentifiantReservation(identifiant),
        client=Client("C-001"),
        periode=periode,
        nombre_personnes=nombre_personnes,
        categorie_contractee=Categorie.STANDARD,
        heure_arrivee=ACCES_STANDARD,
        exigences=exigences,
        chambre_affectee=chambre_affectee,
    )


class TestChargementDesConnaissances:
    def test_la_base_du_projet_est_chargeable(self) -> None:
        connaissances = Connaissances.charger(RACINE_CONNAISSANCES)
        assert connaissances.decision
        assert connaissances.diagnostic

    def test_une_base_absente_est_signalee(self, tmp_path: Path) -> None:
        with pytest.raises(ConnaissancesIndisponiblesError):
            Connaissances.charger(tmp_path)

    def test_une_base_privee_de_ses_gabarits_est_signalee(self, tmp_path: Path) -> None:
        regles = tmp_path / "regles"
        regles.mkdir()
        for fichier in ("decision_chambres.lp", "diagnostic_chambres.lp"):
            source = RACINE_CONNAISSANCES / "regles" / fichier
            (regles / fichier).write_text(
                source.read_text(encoding="utf-8"), encoding="utf-8"
            )
        with pytest.raises(ConnaissancesIndisponiblesError):
            Connaissances.charger(tmp_path)


class TestValidationStructurelle:
    """Verifie que la validation porte sur la forme et non sur les regles."""

    def test_un_parc_vide_est_refuse(self) -> None:
        with pytest.raises(DemandeInvalideError):
            Demande(parc=(), reservation=reservation())

    def test_un_parc_comportant_des_doublons_est_refuse(self) -> None:
        with pytest.raises(DemandeInvalideError):
            Demande(parc=(chambre("401"), chambre("401")), reservation=reservation())

    def test_une_reservation_a_la_fois_demandee_et_occupante_est_refusee(self) -> None:
        demandee = reservation("R-4471")
        with pytest.raises(DemandeInvalideError):
            Demande(
                parc=(chambre("401"),),
                reservation=demandee,
                occupations=(demandee,),
            )

    def test_un_parc_entierement_indisponible_demeure_une_demande_valide(
        self, cas_usage: AffecterChambre
    ) -> None:
        demande = demande_depuis(
            [chambre("401", technique=EtatTechnique.BLOQUEE)], reservation()
        )
        recommandation = cas_usage.executer(demande)
        assert not recommandation.a_conclu
        assert recommandation.options_ecartees


class TestCycleDeDecision:
    def test_une_recommandation_est_produite(self, cas_usage: AffecterChambre) -> None:
        recommandation = cas_usage.executer(
            demande_depuis([chambre("407")], reservation())
        )
        assert recommandation.a_conclu
        assert recommandation.chambre_proposee == "c407"

    def test_la_justification_accompagne_la_recommandation(
        self, cas_usage: AffecterChambre
    ) -> None:
        recommandation = cas_usage.executer(
            demande_depuis([chambre("407")], reservation())
        )
        assert "c407" in recommandation.justification.decision.texte

    def test_les_options_ecartees_sont_regroupees_par_chambre(
        self, cas_usage: AffecterChambre
    ) -> None:
        parc = [
            chambre("201", capacite=1, technique=EtatTechnique.BLOQUEE),
            chambre("405", proprete=EtatProprete.A_CONTROLER),
            chambre("407"),
        ]
        recommandation = cas_usage.executer(demande_depuis(parc, reservation()))
        par_chambre = {
            option.chambre: option for option in recommandation.options_ecartees
        }
        assert set(par_chambre) == {"c201", "c405"}
        assert len(par_chambre["c201"].motifs) >= 2
        assert len(par_chambre["c405"].motifs) == 1

    def test_chaque_motif_ecarte_porte_sa_formulation(
        self, cas_usage: AffecterChambre
    ) -> None:
        parc = [chambre("405", proprete=EtatProprete.A_CONTROLER), chambre("407")]
        recommandation = cas_usage.executer(demande_depuis(parc, reservation()))
        ecartee = recommandation.options_ecartees[0]
        assert len(ecartee.formulations) == len(ecartee.motifs)
        assert all(formulation for formulation in ecartee.formulations)

    def test_le_denombrement_des_options_est_expose(
        self, cas_usage: AffecterChambre
    ) -> None:
        parc = [
            chambre("401"),
            chambre("402", technique=EtatTechnique.BLOQUEE),
            chambre("403", proprete=EtatProprete.SALE),
        ]
        recommandation = cas_usage.executer(demande_depuis(parc, reservation()))
        assert recommandation.nombre_examinees == 3

    def test_une_recommandation_conforme_n_est_pas_sous_reserve(
        self, cas_usage: AffecterChambre
    ) -> None:
        recommandation = cas_usage.executer(
            demande_depuis([chambre("407")], reservation())
        )
        assert not recommandation.sous_reserve

    def test_les_occupations_existantes_sont_prises_en_compte(
        self, cas_usage: AffecterChambre
    ) -> None:
        occupante = reservation(
            "R-1000",
            periode=Periode(date(2026, 8, 13), date(2026, 8, 16)),
            chambre_affectee=NumeroChambre("401"),
        )
        demande = demande_depuis(
            [chambre("401"), chambre("407")], reservation(), [occupante]
        )
        recommandation = cas_usage.executer(demande)
        assert recommandation.chambre_proposee == "c407"

    def test_la_ponderation_transmise_influe_sur_le_choix(
        self, cas_usage: AffecterChambre
    ) -> None:
        parc = [
            chambre("401"),
            chambre(
                "501",
                categorie=Categorie.SUITE,
                equipements=frozenset({Equipement.BALCON}),
            ),
        ]
        demande = reservation(
            exigences=frozenset({Exigence(Equipement.BALCON, obligatoire=False)})
        )
        base = {"souhait_non_satisfait": 3, "hors_secteur": 2, "etage_non_souhaite": 1}
        couteux = cas_usage.executer(
            demande_depuis(parc, demande, poids=base | {"surclassement": 100})
        )
        gratuit = cas_usage.executer(
            demande_depuis(parc, demande, poids=base | {"surclassement": 0})
        )
        assert couteux.chambre_proposee == "c401"
        assert gratuit.chambre_proposee == "c501"

    def test_le_temps_maximal_transmis_est_respecte(
        self, cas_usage: AffecterChambre
    ) -> None:
        recommandation = cas_usage.executer(
            demande_depuis([chambre("407")], reservation()), temps_maximal=5.0
        )
        assert recommandation.a_conclu


class TestPropagationDesDefaillances:
    """Verifie que les defaillances sont journalisees puis propagees.

    Absorber une defaillance produirait une recommandation silencieusement
    fausse, ce qui est inacceptable sur une decision critique.
    """

    def test_des_regles_invalides_interrompent_le_cycle(self) -> None:
        connaissances = Connaissances.charger(RACINE_CONNAISSANCES)
        connaissances.decision = "regle manifestement invalide((("
        cas = AffecterChambre(connaissances)
        with pytest.raises(MoteurIndisponibleError):
            cas.executer(demande_depuis([chambre("407")], reservation()))

    def test_un_gabarit_absent_interrompt_le_cycle(self) -> None:
        from src.gouvernance import GenerateurParGabarits

        connaissances = Connaissances.charger(RACINE_CONNAISSANCES)
        connaissances.generateur = GenerateurParGabarits(
            {"decision": {}, "rejet": {}, "penalite": {}, "regroupement": {}}
        )
        cas = AffecterChambre(connaissances)
        with pytest.raises(GabaritIntrouvableError):
            cas.executer(demande_depuis([chambre("407")], reservation()))


class TestConstructionDeDemande:
    def test_une_demande_accepte_des_sequences_quelconques(self) -> None:
        demande = demande_depuis([chambre("401")], reservation(), [])
        assert isinstance(demande.parc, tuple)
        assert isinstance(demande.occupations, tuple)

    def test_une_demande_sans_ponderation_est_valide(self) -> None:
        assert demande_depuis([chambre("401")], reservation()).poids is None
