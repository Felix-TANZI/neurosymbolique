"""Tests du moteur de regles du service de gestion des chambres.

Les tests de la classe TestGarantieDeConformite realisent la verification de
l'exigence centrale du systeme: aucune affectation restituee ne viole une
contrainte dure, quelle que soit la situation engendree.
"""

from datetime import date, time
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
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
    StatutFidelite,
)
from src.symbolique.regles import (
    POIDS_PAR_DEFAUT,
    MoteurIndisponibleError,
    Rejet,
    Resultat,
    charger_regles,
    diagnostiquer,
    identifiant_chambre,
    resoudre,
    traduire_situation,
)

CHEMIN_REGLES = Path(__file__).resolve().parents[2] / "connaissances" / "regles"
ACCES_STANDARD = HeureArrivee(prevue=time(16, 0), contractuelle=time(15, 0))
SEJOUR = Periode(date(2026, 8, 12), date(2026, 8, 15))


@pytest.fixture(scope="module")
def regles() -> tuple[str, str]:
    """Charge une seule fois les regles de decision et de diagnostic."""
    return (
        charger_regles(CHEMIN_REGLES / "decision_chambres.lp"),
        charger_regles(CHEMIN_REGLES / "diagnostic_chambres.lp"),
    )


def chambre(
    numero: str,
    proprete: EtatProprete = EtatProprete.PRETE,
    technique: EtatTechnique = EtatTechnique.OPERATIONNELLE,
    occupation: EtatOccupation = EtatOccupation.LIBRE,
    capacite: int = 2,
    categorie: Categorie = Categorie.STANDARD,
    etage: int = 3,
    equipements: frozenset[Equipement] = frozenset(),
) -> Chambre:
    """Construit une chambre du domaine dont seuls les attributs utiles varient."""
    return Chambre(
        numero=NumeroChambre(numero),
        etage=etage,
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
    categorie: Categorie = Categorie.STANDARD,
    exigences: frozenset[Exigence] = frozenset(),
    periode: Periode = SEJOUR,
    fidelite: StatutFidelite = StatutFidelite.AUCUN,
    chambre_affectee: NumeroChambre | None = None,
) -> Reservation:
    """Construit une reservation du domaine avec des valeurs par defaut valides."""
    return Reservation(
        identifiant=IdentifiantReservation(identifiant),
        client=Client("C-001", statut_fidelite=fidelite),
        periode=periode,
        nombre_personnes=nombre_personnes,
        categorie_contractee=categorie,
        heure_arrivee=ACCES_STANDARD,
        exigences=exigences,
        chambre_affectee=chambre_affectee,
    )


def resoudre_situation(
    regles: tuple[str, str],
    parc: list[Chambre],
    demande: Reservation,
    occupations: list[Reservation] | None = None,
    poids: dict[str, int] | None = None,
) -> Resultat:
    """Traduit une situation du domaine puis execute le moteur de regles."""
    decision, diagnostic = regles
    situation = traduire_situation(parc, demande, occupations or [], poids)
    return resoudre(decision, diagnostic, situation)


class TestChargementDesRegles:
    def test_les_regles_du_service_sont_chargeables(
        self, regles: tuple[str, str]
    ) -> None:
        decision, diagnostic = regles
        assert "affectation" in decision
        assert "rejet" in diagnostic

    def test_un_fichier_absent_est_signale(self) -> None:
        from src.symbolique.regles import ReglesIntrouvablesError

        with pytest.raises(ReglesIntrouvablesError):
            charger_regles(CHEMIN_REGLES / "inexistant.lp")


class TestContraintesDures:
    def test_une_chambre_prete_et_libre_est_retenue(
        self, regles: tuple[str, str]
    ) -> None:
        resultat = resoudre_situation(regles, [chambre("407")], reservation())
        assert resultat.chambre_retenue == "c407"

    def test_une_chambre_bloquee_est_ecartee(self, regles: tuple[str, str]) -> None:
        resultat = resoudre_situation(
            regles,
            [chambre("312", technique=EtatTechnique.BLOQUEE), chambre("407")],
            reservation(),
        )
        assert resultat.chambre_retenue == "c407"
        assert any(rejet.motif == "bloquee" for rejet in resultat.rejets_de("c312"))

    def test_une_chambre_a_controler_est_ecartee(self, regles: tuple[str, str]) -> None:
        resultat = resoudre_situation(
            regles,
            [chambre("405", proprete=EtatProprete.A_CONTROLER), chambre("407")],
            reservation(),
        )
        assert resultat.chambre_retenue == "c407"
        assert any(rejet.motif == "non_prete" for rejet in resultat.rejets_de("c405"))

    def test_une_chambre_occupee_est_ecartee(self, regles: tuple[str, str]) -> None:
        resultat = resoudre_situation(
            regles,
            [chambre("401", occupation=EtatOccupation.OCCUPEE), chambre("407")],
            reservation(),
        )
        assert resultat.chambre_retenue == "c407"
        assert any(rejet.motif == "non_libre" for rejet in resultat.rejets_de("c401"))

    def test_une_capacite_insuffisante_ecarte_la_chambre(
        self, regles: tuple[str, str]
    ) -> None:
        resultat = resoudre_situation(
            regles,
            [chambre("201", capacite=1), chambre("407", capacite=2)],
            reservation(nombre_personnes=2),
        )
        assert resultat.chambre_retenue == "c407"
        assert any(
            rejet.motif == "capacite_insuffisante"
            for rejet in resultat.rejets_de("c201")
        )

    def test_une_exigence_obligatoire_non_satisfaite_ecarte_la_chambre(
        self, regles: tuple[str, str]
    ) -> None:
        resultat = resoudre_situation(
            regles,
            [
                chambre("401"),
                chambre("402", equipements=frozenset({Equipement.ACCES_PMR})),
            ],
            reservation(
                exigences=frozenset({Exigence(Equipement.ACCES_PMR, obligatoire=True)})
            ),
        )
        assert resultat.chambre_retenue == "c402"
        rejets = resultat.rejets_de("c401")
        assert any(rejet.motif == "equipement_absent" for rejet in rejets)
        assert any(rejet.detail == "acces_pmr" for rejet in rejets)

    def test_une_categorie_inferieure_ecarte_la_chambre(
        self, regles: tuple[str, str]
    ) -> None:
        resultat = resoudre_situation(
            regles,
            [
                chambre("401", categorie=Categorie.STANDARD),
                chambre("501", categorie=Categorie.SUITE),
            ],
            reservation(categorie=Categorie.SUITE),
        )
        assert resultat.chambre_retenue == "c501"
        assert any(
            rejet.motif == "categorie_inferieure"
            for rejet in resultat.rejets_de("c401")
        )

    def test_un_sejour_en_conflit_ecarte_la_chambre(
        self, regles: tuple[str, str]
    ) -> None:
        occupante = reservation(
            "R-1000",
            periode=Periode(date(2026, 8, 13), date(2026, 8, 16)),
            chambre_affectee=NumeroChambre("401"),
        )
        resultat = resoudre_situation(
            regles, [chambre("401"), chambre("407")], reservation(), [occupante]
        )
        assert resultat.chambre_retenue == "c407"
        assert any(
            rejet.motif == "sejour_en_conflit" for rejet in resultat.rejets_de("c401")
        )

    def test_un_sejour_consecutif_n_ecarte_pas_la_chambre(
        self, regles: tuple[str, str]
    ) -> None:
        precedente = reservation(
            "R-1000",
            periode=Periode(date(2026, 8, 9), date(2026, 8, 12)),
            chambre_affectee=NumeroChambre("401"),
        )
        resultat = resoudre_situation(
            regles, [chambre("401")], reservation(), [precedente]
        )
        assert resultat.chambre_retenue == "c401"


class TestAbsenceDeSolution:
    def test_un_parc_entierement_indisponible_ne_conclut_pas(
        self, regles: tuple[str, str]
    ) -> None:
        resultat = resoudre_situation(
            regles,
            [
                chambre("401", technique=EtatTechnique.BLOQUEE),
                chambre("402", proprete=EtatProprete.SALE),
            ],
            reservation(),
        )
        assert not resultat.a_conclu

    def test_les_motifs_demeurent_disponibles_sans_solution(
        self, regles: tuple[str, str]
    ) -> None:
        resultat = resoudre_situation(
            regles,
            [
                chambre("401", technique=EtatTechnique.BLOQUEE),
                chambre("402", proprete=EtatProprete.SALE),
            ],
            reservation(),
        )
        assert not resultat.a_conclu
        assert resultat.rejets_de("c401")
        assert resultat.rejets_de("c402")
        assert resultat.nombre_examinees == 2

    def test_un_parc_vide_ne_conclut_pas(self, regles: tuple[str, str]) -> None:
        assert not resoudre_situation(regles, [], reservation()).a_conclu


class TestPreferencesSouples:
    def test_le_surclassement_est_penalise(self, regles: tuple[str, str]) -> None:
        resultat = resoudre_situation(
            regles,
            [
                chambre("401", categorie=Categorie.STANDARD),
                chambre("501", categorie=Categorie.SUITE),
            ],
            reservation(categorie=Categorie.STANDARD),
        )
        assert resultat.chambre_retenue == "c401"
        assert resultat.cout == 0

    def test_une_preference_ne_ressuscite_pas_une_option_interdite(
        self, regles: tuple[str, str]
    ) -> None:
        poids = dict(POIDS_PAR_DEFAUT) | {"surclassement": 0}
        resultat = resoudre_situation(
            regles,
            [
                chambre("401", technique=EtatTechnique.BLOQUEE),
                chambre("501", categorie=Categorie.SUITE),
            ],
            reservation(categorie=Categorie.STANDARD),
            poids=poids,
        )
        assert resultat.chambre_retenue == "c501"

    def test_la_ponderation_modifie_le_choix(self, regles: tuple[str, str]) -> None:
        parc = [
            chambre("401", categorie=Categorie.STANDARD),
            chambre(
                "501",
                categorie=Categorie.SUITE,
                equipements=frozenset({Equipement.BALCON}),
            ),
        ]
        demande = reservation(
            exigences=frozenset({Exigence(Equipement.BALCON, obligatoire=False)})
        )

        avec_surclassement_couteux = resoudre_situation(
            regles, parc, demande, poids=dict(POIDS_PAR_DEFAUT) | {"surclassement": 100}
        )
        avec_surclassement_gratuit = resoudre_situation(
            regles, parc, demande, poids=dict(POIDS_PAR_DEFAUT) | {"surclassement": 0}
        )

        assert avec_surclassement_couteux.chambre_retenue == "c401"
        assert avec_surclassement_gratuit.chambre_retenue == "c501"

    def test_un_souhait_non_satisfait_est_penalise(
        self, regles: tuple[str, str]
    ) -> None:
        resultat = resoudre_situation(
            regles,
            [chambre("401")],
            reservation(
                exigences=frozenset({Exigence(Equipement.BALCON, obligatoire=False)})
            ),
        )
        assert any(
            penalite.motif == "souhait_non_satisfait" for penalite in resultat.penalites
        )


class TestRestitution:
    def test_les_options_examinees_sont_denombrees(
        self, regles: tuple[str, str]
    ) -> None:
        resultat = resoudre_situation(
            regles,
            [
                chambre("401"),
                chambre("402", technique=EtatTechnique.BLOQUEE),
                chambre("403", proprete=EtatProprete.SALE),
            ],
            reservation(),
        )
        assert resultat.nombre_examinees == 3
        assert len(resultat.admissibles) == 1

    def test_une_chambre_peut_cumuler_plusieurs_motifs_de_rejet(
        self, regles: tuple[str, str]
    ) -> None:
        resultat = resoudre_situation(
            regles,
            [
                chambre("201", capacite=1, technique=EtatTechnique.BLOQUEE),
                chambre("407"),
            ],
            reservation(nombre_personnes=2),
        )
        motifs = {rejet.motif for rejet in resultat.rejets_de("c201")}
        assert {"bloquee", "capacite_insuffisante"} <= motifs

    def test_les_rejets_sont_independants_de_la_solution_retenue(
        self, regles: tuple[str, str]
    ) -> None:
        parc = [chambre("401", technique=EtatTechnique.BLOQUEE), chambre("407")]
        avec_poids_eleve = resoudre_situation(
            regles,
            parc,
            reservation(),
            poids=dict(POIDS_PAR_DEFAUT) | {"surclassement": 99},
        )
        avec_poids_nul = resoudre_situation(
            regles,
            parc,
            reservation(),
            poids=dict(POIDS_PAR_DEFAUT) | {"surclassement": 0},
        )
        assert avec_poids_eleve.rejets == avec_poids_nul.rejets

    def test_la_solution_est_signalee_optimale(self, regles: tuple[str, str]) -> None:
        resultat = resoudre_situation(regles, [chambre("407")], reservation())
        assert resultat.optimal
        assert not resultat.interrompu


class TestDeterminisme:
    def test_une_meme_situation_produit_une_meme_decision(
        self, regles: tuple[str, str]
    ) -> None:
        parc = [
            chambre("401", etage=4),
            chambre("402", etage=4),
            chambre("403", etage=5, categorie=Categorie.SUPERIEURE),
        ]
        decisions = {
            resoudre_situation(regles, parc, reservation()).chambre_retenue
            for _ in range(5)
        }
        assert len(decisions) == 1


etats_proprete = st.sampled_from(list(EtatProprete))
etats_technique = st.sampled_from(list(EtatTechnique))
etats_occupation = st.sampled_from(list(EtatOccupation))
categories = st.sampled_from(list(Categorie))
equipements = st.frozensets(st.sampled_from(list(Equipement)), max_size=4)


@st.composite
def chambres_quelconques(tirage: st.DrawFn, numero: int) -> Chambre:
    """Engendre une chambre dont tous les attributs varient librement."""
    return chambre(
        numero=f"{numero:03d}",
        proprete=tirage(etats_proprete),
        technique=tirage(etats_technique),
        occupation=tirage(etats_occupation),
        capacite=tirage(st.integers(min_value=1, max_value=4)),
        categorie=tirage(categories),
        etage=tirage(st.integers(min_value=0, max_value=6)),
        equipements=tirage(equipements),
    )


@st.composite
def parcs_quelconques(tirage: st.DrawFn) -> list[Chambre]:
    """Engendre un parc de une a six chambres aux etats varies."""
    taille = tirage(st.integers(min_value=1, max_value=6))
    return [tirage(chambres_quelconques(rang)) for rang in range(1, taille + 1)]


@st.composite
def demandes_quelconques(tirage: st.DrawFn) -> Reservation:
    """Engendre une reservation aux exigences et contraintes variees."""
    obligatoires = tirage(st.frozensets(st.sampled_from(list(Equipement)), max_size=2))
    souhaitees = tirage(st.frozensets(st.sampled_from(list(Equipement)), max_size=2))
    exigences = frozenset(
        {Exigence(equipement, obligatoire=True) for equipement in obligatoires}
        | {
            Exigence(equipement, obligatoire=False)
            for equipement in souhaitees - obligatoires
        }
    )
    return reservation(
        nombre_personnes=tirage(st.integers(min_value=1, max_value=4)),
        categorie=tirage(categories),
        exigences=exigences,
    )


class TestGarantieDeConformite:
    """Verifie l'exigence centrale du systeme sur des situations engendrees.

    La propriete verifiee n'est pas relative a un cas particulier: quelle que
    soit la situation, une affectation restituee satisfait l'integralite des
    contraintes dures. Une violation constituerait une non-conformite bloquante.
    """

    @settings(
        max_examples=120,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(parc=parcs_quelconques(), demande=demandes_quelconques())
    def test_aucune_affectation_ne_viole_une_contrainte_dure(
        self, regles: tuple[str, str], parc: list[Chambre], demande: Reservation
    ) -> None:
        resultat = resoudre_situation(regles, parc, demande)
        if not resultat.a_conclu:
            return

        retenue = next(
            candidate
            for candidate in parc
            if identifiant_chambre(candidate) == resultat.chambre_retenue
        )

        assert retenue.etat_proprete is EtatProprete.PRETE
        assert retenue.etat_technique is not EtatTechnique.BLOQUEE
        assert retenue.etat_occupation is EtatOccupation.LIBRE
        assert retenue.capacite >= demande.nombre_personnes
        assert retenue.categorie >= demande.categorie_contractee
        assert demande.exigences_obligatoires <= retenue.equipements

    @settings(
        max_examples=80,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(parc=parcs_quelconques(), demande=demandes_quelconques())
    def test_une_solution_existe_des_qu_une_chambre_convient(
        self, regles: tuple[str, str], parc: list[Chambre], demande: Reservation
    ) -> None:
        convenables = [
            candidate
            for candidate in parc
            if candidate.est_attribuable
            and candidate.capacite >= demande.nombre_personnes
            and candidate.categorie >= demande.categorie_contractee
            and demande.exigences_obligatoires <= candidate.equipements
        ]
        resultat = resoudre_situation(regles, parc, demande)
        assert resultat.a_conclu is bool(convenables)

    @settings(
        max_examples=60,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(parc=parcs_quelconques(), demande=demandes_quelconques())
    def test_toute_chambre_ecartee_porte_un_motif(
        self, regles: tuple[str, str], parc: list[Chambre], demande: Reservation
    ) -> None:
        resultat = resoudre_situation(regles, parc, demande)
        for candidate in parc:
            reference = identifiant_chambre(candidate)
            if reference not in resultat.admissibles:
                assert resultat.rejets_de(reference)


class TestDefaillances:
    """Verifie le traitement explicite des defaillances du moteur.

    Une defaillance non signalee sur le composant portant la garantie de
    conformite passerait inapercue: chaque chemin d'erreur est donc verifie.
    """

    def test_un_programme_logique_invalide_est_signale(
        self, regles: tuple[str, str]
    ) -> None:
        decision, diagnostic = regles
        with pytest.raises(MoteurIndisponibleError):
            resoudre(decision, diagnostic, "syntaxe manifestement invalide (((")

    def test_des_regles_invalides_sont_signalees(self) -> None:
        with pytest.raises(MoteurIndisponibleError):
            resoudre("regle sans point valide (((", "", "chambre(c1).")

    def test_un_diagnostic_invalide_est_signale(self, regles: tuple[str, str]) -> None:
        decision, _ = regles
        with pytest.raises(MoteurIndisponibleError):
            resoudre(decision, "diagnostic invalide (((", "chambre(c1).")

    def test_une_interruption_prive_la_solution_de_sa_garantie_d_optimalite(
        self,
    ) -> None:
        interrompu = Resultat(
            reservation="r4471",
            chambre_retenue="c407",
            admissibles=frozenset({"c407"}),
            interrompu=True,
        )
        assert interrompu.a_conclu
        assert not interrompu.optimal

    def test_le_diagnostic_demeure_disponible_sans_decision(
        self, regles: tuple[str, str]
    ) -> None:
        decision, diagnostic = regles
        situation = traduire_situation(
            [chambre("401", technique=EtatTechnique.BLOQUEE)], reservation()
        )
        constat = diagnostiquer(diagnostic, situation)
        resultat = resoudre(decision, diagnostic, situation)
        assert constat["rejets"]
        assert not resultat.a_conclu
        assert resultat.rejets


class TestRestitutionDesRejets:
    def test_un_rejet_simple_s_affiche_avec_son_motif(self) -> None:
        assert str(Rejet(chambre="c401", motif="bloquee")) == "c401: bloquee"

    def test_un_rejet_detaille_expose_son_argument(self) -> None:
        rejet = Rejet(chambre="c401", motif="equipement_absent", detail="acces_pmr")
        assert str(rejet) == "c401: equipement_absent(acces_pmr)"

    def test_les_rejets_d_une_autre_chambre_sont_ecartes(
        self, regles: tuple[str, str]
    ) -> None:
        resultat = resoudre_situation(
            regles,
            [chambre("401", technique=EtatTechnique.BLOQUEE), chambre("407")],
            reservation(),
        )
        assert resultat.rejets_de("c999") == ()


class _RechercheSimulee:
    """Recherche dont le temps imparti expire avant l'achevement du calcul."""

    def __init__(self, modeles: list[object]) -> None:
        self._modeles = modeles
        self.annulee = False

    def __enter__(self) -> "_RechercheSimulee":
        return self

    def __exit__(self, *exception: object) -> None:
        return None

    def wait(self, temps: float) -> bool:
        return False

    def cancel(self) -> None:
        self.annulee = True

    def get(self) -> object:
        return type("Statut", (), {"satisfiable": True})()


class _ControleSimule:
    """Controleur restituant une recherche dont le temps imparti expire."""

    def __init__(self, *arguments: object) -> None:
        self.recherche: _RechercheSimulee | None = None

    def add(self, *arguments: object) -> None:
        return None

    def ground(self, *arguments: object) -> None:
        return None

    def solve(self, on_model: object = None, async_: bool = False) -> object:
        if not async_:
            return type("Statut", (), {"satisfiable": True})()
        self.recherche = _RechercheSimulee([])
        return self.recherche


class TestDepassementDuTempsImparti:
    """Verifie le comportement lorsque le calcul excede le temps alloue.

    La condition de delai limite impose de restituer une solution exploitable
    plutot que d'attendre indefiniment. Le depassement etant difficile a
    provoquer sur une instance reelle, un controleur simule est substitue au
    moteur.
    """

    def test_le_depassement_annule_la_recherche_et_leve_l_optimalite(
        self, monkeypatch: pytest.MonkeyPatch, regles: tuple[str, str]
    ) -> None:
        controles: list[_ControleSimule] = []

        def fabriquer(*arguments: object) -> _ControleSimule:
            controle = _ControleSimule()
            controles.append(controle)
            return controle

        monkeypatch.setattr("src.symbolique.regles.execution.clingo.Control", fabriquer)
        decision, diagnostic = regles
        resultat = resoudre(decision, diagnostic, "chambre(c1).", temps_maximal=0.01)

        assert resultat.interrompu
        assert not resultat.optimal
        assert controles[-1].recherche is not None
        assert controles[-1].recherche.annulee
