"""Tests de la generation des justifications.

Les tests de la classe TestFideliteExplicative verifient l'exigence centrale de
la couche de gouvernance: une justification ne mentionne aucun element absent
de la trace et n'omet aucune contrainte determinante.
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
from src.gouvernance import (
    CatalogueInvalideError,
    GabaritIntrouvableError,
    GenerateurParGabarits,
    charger_catalogue,
    creer_generateur,
)
from src.symbolique.regles import (
    Penalite,
    Rejet,
    Resultat,
    charger_regles,
    resoudre,
    traduire_situation,
)

RACINE = Path(__file__).resolve().parents[2]
CHEMIN_REGLES = RACINE / "connaissances" / "regles"
CHEMIN_GABARITS = RACINE / "connaissances" / "explications" / "gabarits_chambres.toml"

ACCES_STANDARD = HeureArrivee(prevue=time(16, 0), contractuelle=time(15, 0))
SEJOUR = Periode(date(2026, 8, 12), date(2026, 8, 15))


@pytest.fixture(scope="module")
def generateur() -> GenerateurParGabarits:
    """Charge une seule fois le catalogue de gabarits du service."""
    return creer_generateur(CHEMIN_GABARITS)


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
    nombre_personnes: int = 2,
    categorie: Categorie = Categorie.STANDARD,
    exigences: frozenset[Exigence] = frozenset(),
) -> Reservation:
    """Construit une reservation du domaine avec des valeurs par defaut valides."""
    return Reservation(
        identifiant=IdentifiantReservation("R-4471"),
        client=Client("C-001"),
        periode=SEJOUR,
        nombre_personnes=nombre_personnes,
        categorie_contractee=categorie,
        heure_arrivee=ACCES_STANDARD,
        exigences=exigences,
    )


def resultat_reel(
    regles: tuple[str, str],
    parc: list[Chambre],
    demande: Reservation | None = None,
) -> Resultat:
    """Produit un resultat issu d'un raisonnement effectif sur une situation."""
    decision, diagnostic = regles
    situation = traduire_situation(parc, demande or reservation())
    return resoudre(decision, diagnostic, situation)


class TestChargementDuCatalogue:
    def test_le_catalogue_du_service_est_chargeable(self) -> None:
        catalogue = charger_catalogue(CHEMIN_GABARITS)
        assert {"decision", "rejet", "penalite", "regroupement"} <= set(catalogue)

    def test_un_catalogue_absent_est_signale(self) -> None:
        with pytest.raises(CatalogueInvalideError):
            charger_catalogue(CHEMIN_GABARITS.with_name("inexistant.toml"))

    def test_un_catalogue_incomplet_est_signale(self, tmp_path: Path) -> None:
        partiel = tmp_path / "partiel.toml"
        partiel.write_text('[decision]\nretenue = "texte"\n', encoding="utf-8")
        with pytest.raises(CatalogueInvalideError):
            charger_catalogue(partiel)


class TestCouvertureDesMotifs:
    """Verifie qu'aucun motif produit par les regles ne demeure sans formulation."""

    def test_tout_motif_de_rejet_dispose_d_une_formulation(self) -> None:
        contenu = (CHEMIN_REGLES / "diagnostic_chambres.lp").read_text(encoding="utf-8")
        motifs_declares = {
            ligne.split("rejet(R, C, ")[1].split(")")[0].split("(")[0]
            for ligne in contenu.splitlines()
            if ligne.startswith("rejet(R, C, ")
        }
        formules = set(charger_catalogue(CHEMIN_GABARITS)["rejet"])
        assert motifs_declares <= formules

    def test_tout_motif_de_penalite_dispose_d_une_formulation(self) -> None:
        contenu = (CHEMIN_REGLES / "decision_chambres.lp").read_text(encoding="utf-8")
        motifs_declares = {
            ligne.split("penalite(R, ")[1].split(",")[0]
            for ligne in contenu.splitlines()
            if ligne.startswith("penalite(R, ")
        }
        formules = set(charger_catalogue(CHEMIN_GABARITS)["penalite"])
        assert motifs_declares <= formules


class TestJustificationDeDecision:
    def test_la_chambre_retenue_est_nommee(
        self, generateur: GenerateurParGabarits, regles: tuple[str, str]
    ) -> None:
        justification = generateur.justifier(resultat_reel(regles, [chambre("407")]))
        assert "c407" in justification.decision.texte

    def test_le_denombrement_des_options_est_restitue(
        self, generateur: GenerateurParGabarits, regles: tuple[str, str]
    ) -> None:
        parc = [
            chambre("401"),
            chambre("402", technique=EtatTechnique.BLOQUEE),
            chambre("403", proprete=EtatProprete.SALE),
        ]
        justification = generateur.justifier(resultat_reel(regles, parc))
        assert "3" in justification.decision.texte
        assert "1" in justification.decision.texte

    def test_l_absence_de_solution_est_explicitee(
        self, generateur: GenerateurParGabarits, regles: tuple[str, str]
    ) -> None:
        parc = [
            chambre("401", technique=EtatTechnique.BLOQUEE),
            chambre("402", proprete=EtatProprete.SALE),
        ]
        justification = generateur.justifier(resultat_reel(regles, parc))
        assert justification.decision.origine == "decision:sans_solution"
        assert len(justification.options_ecartees) == 2

    def test_une_optimalite_non_garantie_est_signalee(
        self, generateur: GenerateurParGabarits
    ) -> None:
        interrompu = Resultat(
            reservation="r4471",
            chambre_retenue="c407",
            admissibles=frozenset({"c407"}),
            interrompu=True,
        )
        justification = generateur.justifier(interrompu)
        assert justification.reserve is not None
        assert "optimalite" in justification.reserve.texte

    def test_une_solution_optimale_ne_porte_aucune_reserve(
        self, generateur: GenerateurParGabarits, regles: tuple[str, str]
    ) -> None:
        justification = generateur.justifier(resultat_reel(regles, [chambre("407")]))
        assert justification.reserve is None


class TestJustificationDesRejets:
    @pytest.mark.parametrize(
        ("ecartee", "extrait"),
        [
            (chambre("401", technique=EtatTechnique.BLOQUEE), "intervention technique"),
            (chambre("401", proprete=EtatProprete.A_CONTROLER), "nettoyage"),
            (chambre("401", occupation=EtatOccupation.OCCUPEE), "occupee"),
        ],
    )
    def test_chaque_etat_produit_sa_formulation(
        self,
        generateur: GenerateurParGabarits,
        regles: tuple[str, str],
        ecartee: Chambre,
        extrait: str,
    ) -> None:
        justification = generateur.justifier(
            resultat_reel(regles, [ecartee, chambre("407")])
        )
        assert any(extrait in enonce.texte for enonce in justification.options_ecartees)

    def test_l_equipement_manquant_est_nomme(
        self, generateur: GenerateurParGabarits, regles: tuple[str, str]
    ) -> None:
        parc = [
            chambre("401"),
            chambre("402", equipements=frozenset({Equipement.ACCES_PMR})),
        ]
        demande = reservation(
            exigences=frozenset({Exigence(Equipement.ACCES_PMR, obligatoire=True)})
        )
        justification = generateur.justifier(resultat_reel(regles, parc, demande))
        assert any(
            "acces_pmr" in enonce.texte for enonce in justification.options_ecartees
        )

    def test_une_chambre_cumulant_des_motifs_produit_plusieurs_enonces(
        self, generateur: GenerateurParGabarits, regles: tuple[str, str]
    ) -> None:
        parc = [
            chambre("201", capacite=1, technique=EtatTechnique.BLOQUEE),
            chambre("407"),
        ]
        justification = generateur.justifier(resultat_reel(regles, parc))
        enonces_201 = [
            enonce for enonce in justification.options_ecartees if "c201" in enonce.texte
        ]
        assert len(enonces_201) >= 2


class TestJustificationDesContreparties:
    def test_un_souhait_non_satisfait_est_expose(
        self, generateur: GenerateurParGabarits, regles: tuple[str, str]
    ) -> None:
        demande = reservation(
            exigences=frozenset({Exigence(Equipement.BALCON, obligatoire=False)})
        )
        justification = generateur.justifier(
            resultat_reel(regles, [chambre("401")], demande)
        )
        assert justification.contreparties
        assert "preference" in justification.contreparties[0].texte

    def test_une_decision_sans_contrepartie_n_en_expose_aucune(
        self, generateur: GenerateurParGabarits, regles: tuple[str, str]
    ) -> None:
        justification = generateur.justifier(resultat_reel(regles, [chambre("407")]))
        assert justification.contreparties == ()


class TestFideliteExplicative:
    """Verifie l'exigence de fidelite de la couche de gouvernance.

    Une justification ne peut mentionner un element absent de la trace, ni
    omettre une contrainte ayant determine la conclusion.
    """

    def test_chaque_enonce_se_rattache_a_un_element_de_trace(
        self, generateur: GenerateurParGabarits, regles: tuple[str, str]
    ) -> None:
        parc = [
            chambre("401", technique=EtatTechnique.BLOQUEE),
            chambre("402", proprete=EtatProprete.A_CONTROLER),
            chambre("403", capacite=1),
            chambre("407"),
        ]
        resultat = resultat_reel(regles, parc)
        justification = generateur.justifier(resultat)

        origines_valides = (
            {f"affectation:{resultat.chambre_retenue}", "decision:sans_solution"}
            | {f"rejet:{r.chambre}:{r.motif}" for r in resultat.rejets}
            | {f"penalite:{p.motif}" for p in resultat.penalites}
            | {"decision:optimalite_non_garantie"}
        )
        assert justification.origines <= origines_valides

    def test_aucune_contrainte_determinante_n_est_omise(
        self, generateur: GenerateurParGabarits, regles: tuple[str, str]
    ) -> None:
        parc = [
            chambre("401", technique=EtatTechnique.BLOQUEE),
            chambre("402", proprete=EtatProprete.SALE),
            chambre("403", capacite=1),
            chambre("404", categorie=Categorie.STANDARD),
            chambre("407"),
        ]
        demande = reservation(nombre_personnes=2, categorie=Categorie.SUPERIEURE)
        resultat = resultat_reel(regles, parc, demande)
        justification = generateur.justifier(resultat)

        attendues = {f"rejet:{r.chambre}:{r.motif}" for r in resultat.rejets}
        assert attendues <= justification.origines

    def test_aucune_chambre_absente_de_la_situation_n_est_mentionnee(
        self, generateur: GenerateurParGabarits, regles: tuple[str, str]
    ) -> None:
        parc = [chambre("401", technique=EtatTechnique.BLOQUEE), chambre("407")]
        justification = generateur.justifier(resultat_reel(regles, parc))
        presentes = {"c401", "c407"}
        for enonce in justification.enonces:
            mentionnees = {mot for mot in presentes if mot in enonce.texte}
            assert mentionnees <= presentes

    def test_un_motif_sans_formulation_interrompt_la_generation(
        self, generateur: GenerateurParGabarits
    ) -> None:
        inattendu = Resultat(
            reservation="r4471",
            chambre_retenue="c407",
            admissibles=frozenset({"c407"}),
            rejets=(Rejet(chambre="c401", motif="motif_non_prevu"),),
        )
        with pytest.raises(GabaritIntrouvableError):
            generateur.justifier(inattendu)

    def test_une_penalite_sans_formulation_interrompt_la_generation(
        self, generateur: GenerateurParGabarits
    ) -> None:
        inattendue = Resultat(
            reservation="r4471",
            chambre_retenue="c407",
            admissibles=frozenset({"c407"}),
            penalites=(Penalite(motif="motif_non_prevu", poids=5),),
        )
        with pytest.raises(GabaritIntrouvableError):
            generateur.justifier(inattendue)

    def test_une_variable_absente_de_la_trace_interrompt_la_generation(self) -> None:
        catalogue = {
            "decision": {"retenue": "{chambre} et {variable_inexistante}"},
            "rejet": {},
            "penalite": {},
            "regroupement": {},
        }
        generateur = GenerateurParGabarits(catalogue)
        with pytest.raises(GabaritIntrouvableError):
            generateur.justifier(Resultat(reservation="r1", chambre_retenue="c407"))


class TestRestitutionTextuelle:
    def test_la_justification_se_restitue_en_texte(
        self, generateur: GenerateurParGabarits, regles: tuple[str, str]
    ) -> None:
        parc = [chambre("401", technique=EtatTechnique.BLOQUEE), chambre("407")]
        texte = generateur.justifier(resultat_reel(regles, parc)).en_texte()
        assert "c407" in texte
        assert "c401" in texte
        assert texte.count("\n") >= 1

    def test_un_enonce_s_affiche_par_son_texte(
        self, generateur: GenerateurParGabarits, regles: tuple[str, str]
    ) -> None:
        justification = generateur.justifier(resultat_reel(regles, [chambre("407")]))
        assert str(justification.decision) == justification.decision.texte
