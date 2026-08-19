"""Tests du service housekeeping, de la traduction a la justification.

Les tests verifient la chaine complete: etablissement des paires admissibles
par le moteur logique, ordonnancement par le solveur de contraintes, puis
formulation. La propriete centrale verifiee est que le solveur ne retient
jamais une paire que le moteur logique a ecartee.
"""

from datetime import time
from pathlib import Path

import pytest
from src.domaine import (
    AgentEtage,
    DisponibiliteAgent,
    IdentifiantAgent,
    NumeroChambre,
    PlageDeService,
    PrioriteTache,
    Secteur,
    StatutTache,
    TacheNettoyage,
    TypePrestation,
)
from src.orchestration import (
    ConnaissancesHousekeeping,
    ConnaissancesIndisponiblesError,
    DemandeInvalideError,
    PlanifierNettoyage,
    creer_cas_usage_housekeeping,
    demande_de_service,
)
from src.symbolique.regles import (
    charger_regles,
    diagnostiquer_paires,
    identifiant_agent,
    identifiant_tache,
    traduire_service,
    vers_agents_disponibles,
    vers_taches_a_ordonnancer,
)

RACINE = Path(__file__).resolve().parents[2] / "connaissances"
PLAGE_MATIN = PlageDeService(debut=time(8, 0), fin=time(16, 0))


@pytest.fixture(scope="module")
def cas_usage() -> PlanifierNettoyage:
    """Construit une seule fois le cas d'usage et ses connaissances."""
    return creer_cas_usage_housekeeping(RACINE)


@pytest.fixture(scope="module")
def regles_diagnostic() -> str:
    """Charge une seule fois les regles d'admissibilite du service."""
    return charger_regles(RACINE / "regles" / "diagnostic_housekeeping.lp")


def agent(
    identifiant: str = "A-001",
    secteur: str = "etage_4",
    disponibilite: DisponibiliteAgent = DisponibiliteAgent.PRESENT,
    charge: int = 0,
    plage: PlageDeService = PLAGE_MATIN,
) -> AgentEtage:
    """Construit un agent d'etage dont seuls les attributs utiles varient."""
    return AgentEtage(
        identifiant=IdentifiantAgent(identifiant),
        secteur=Secteur(secteur),
        plage=plage,
        disponibilite=disponibilite,
        minutes_deja_affectees=charge,
    )


def tache(
    identifiant: str = "T-001",
    chambre: str = "407",
    prestation: TypePrestation = TypePrestation.DEPART,
    secteur: str = "etage_4",
    echeance: time | None = None,
    priorite: PrioriteTache = PrioriteTache.NORMALE,
    statut: StatutTache = StatutTache.A_PLANIFIER,
) -> TacheNettoyage:
    """Construit une tache de nettoyage dont seuls les attributs utiles varient."""
    return TacheNettoyage(
        identifiant=identifiant,
        chambre=NumeroChambre(chambre),
        prestation=prestation,
        secteur=Secteur(secteur),
        echeance=echeance,
        priorite=priorite,
        statut=statut,
    )


class TestTraduction:
    def test_un_agent_est_traduit_avec_ses_etats(self) -> None:
        faits = traduire_service(demande_de_service([tache()], [agent()]).service)
        assert "agent(aa_001)." in faits
        assert "disponibilite(aa_001, present)." in faits
        assert "minutes_restantes(aa_001, 480)." in faits

    def test_une_tache_est_traduite_avec_sa_duree_effective(self) -> None:
        faits = traduire_service(
            demande_de_service(
                [tache(prestation=TypePrestation.REMISE_EN_ETAT)], [agent()]
            ).service
        )
        assert "duree(tt_001, 75)." in faits

    def test_une_echeance_est_traduite_en_minutes(self) -> None:
        faits = traduire_service(
            demande_de_service([tache(echeance=time(13, 0))], [agent()]).service
        )
        assert "echeance(tt_001, 780)." in faits

    def test_une_tache_sans_echeance_n_en_declare_aucune(self) -> None:
        faits = traduire_service(demande_de_service([tache()], [agent()]).service)
        assert "echeance(" not in faits

    def test_les_taches_achevees_ne_sont_pas_traduites(self) -> None:
        service = demande_de_service(
            [tache("T-001"), tache("T-002", statut=StatutTache.ACHEVEE)], [agent()]
        ).service
        faits = traduire_service(service)
        assert "tache(tt_001)." in faits
        assert "tache(tt_002)." not in faits

    def test_les_competences_sont_traduites(self) -> None:
        faits = traduire_service(
            demande_de_service([tache()], [agent()]).service,
            competences_par_agent={"A-001": ("suite",)},
        )
        assert "competence(aa_001, suite)." in faits

    def test_les_secteurs_reserves_sont_traduits(self) -> None:
        faits = traduire_service(
            demande_de_service([tache()], [agent()]).service,
            secteurs_reserves=("presidentielle",),
        )
        assert "secteur_reserve(presidentielle)." in faits

    def test_la_fenetre_du_solveur_deduit_la_charge_deja_affectee(self) -> None:
        service = demande_de_service([tache()], [agent(charge=120)]).service
        ressources = vers_agents_disponibles(service)
        assert ressources[0].debut_minutes == 8 * 60 + 120
        assert ressources[0].fin_minutes == 16 * 60

    def test_un_agent_sature_n_est_pas_transmis_au_solveur(self) -> None:
        service = demande_de_service([tache()], [agent(charge=480)]).service
        assert vers_agents_disponibles(service) == []

    def test_un_agent_absent_n_est_pas_transmis_au_solveur(self) -> None:
        service = demande_de_service(
            [tache()], [agent(disponibilite=DisponibiliteAgent.ABSENT)]
        ).service
        assert vers_agents_disponibles(service) == []


class TestAdmissibiliteParLesRegles:
    def test_un_agent_present_et_disponible_est_admissible(
        self, regles_diagnostic: str
    ) -> None:
        service = demande_de_service([tache()], [agent()]).service
        constat = diagnostiquer_paires(regles_diagnostic, traduire_service(service))
        assert ("tt_001", "aa_001") in constat.admissibles

    def test_un_agent_absent_est_ecarte(self, regles_diagnostic: str) -> None:
        service = demande_de_service(
            [tache()], [agent(disponibilite=DisponibiliteAgent.ABSENT)]
        ).service
        constat = diagnostiquer_paires(regles_diagnostic, traduire_service(service))
        assert not constat.admissibles
        assert any(
            rejet.motif == "agent_absent" for rejet in constat.rejets_de("tt_001")
        )

    def test_un_agent_en_retard_est_ecarte(self, regles_diagnostic: str) -> None:
        service = demande_de_service(
            [tache()], [agent(disponibilite=DisponibiliteAgent.RETARD)]
        ).service
        constat = diagnostiquer_paires(regles_diagnostic, traduire_service(service))
        assert any(
            rejet.motif == "agent_en_retard" for rejet in constat.rejets_de("tt_001")
        )

    def test_un_temps_restant_insuffisant_ecarte_l_agent(
        self, regles_diagnostic: str
    ) -> None:
        service = demande_de_service(
            [tache(prestation=TypePrestation.REMISE_EN_ETAT)], [agent(charge=440)]
        ).service
        constat = diagnostiquer_paires(regles_diagnostic, traduire_service(service))
        assert any(
            rejet.motif == "temps_insuffisant" for rejet in constat.rejets_de("tt_001")
        )

    def test_une_competence_absente_ecarte_l_agent(self, regles_diagnostic: str) -> None:
        service = demande_de_service([tache()], [agent()]).service
        constat = diagnostiquer_paires(
            regles_diagnostic,
            traduire_service(service, exigences_par_tache={"T-001": ("suite",)}),
        )
        rejets = constat.rejets_de("tt_001")
        assert any(rejet.motif == "competence_absente" for rejet in rejets)
        assert any(rejet.detail == "suite" for rejet in rejets)

    def test_une_competence_presente_conserve_l_agent(
        self, regles_diagnostic: str
    ) -> None:
        service = demande_de_service([tache()], [agent()]).service
        constat = diagnostiquer_paires(
            regles_diagnostic,
            traduire_service(
                service,
                competences_par_agent={"A-001": ("suite",)},
                exigences_par_tache={"T-001": ("suite",)},
            ),
        )
        assert ("tt_001", "aa_001") in constat.admissibles

    def test_un_secteur_reserve_ecarte_l_agent_non_habilite(
        self, regles_diagnostic: str
    ) -> None:
        service = demande_de_service(
            [tache(secteur="presidentielle")], [agent(secteur="etage_4")]
        ).service
        constat = diagnostiquer_paires(
            regles_diagnostic,
            traduire_service(service, secteurs_reserves=("presidentielle",)),
        )
        assert any(
            rejet.motif == "secteur_reserve" for rejet in constat.rejets_de("tt_001")
        )

    def test_une_tache_sans_agent_admissible_est_signalee(
        self, regles_diagnostic: str
    ) -> None:
        service = demande_de_service(
            [tache()], [agent(disponibilite=DisponibiliteAgent.ABSENT)]
        ).service
        constat = diagnostiquer_paires(regles_diagnostic, traduire_service(service))
        assert "tt_001" in constat.demandes_sans_ressource


class TestSeparationDesRoles:
    """Verifie que le solveur n'opere que sur les paires declarees admissibles.

    Cette propriete realise la division du travail retenue a la conception: le
    moteur logique etablit ce qui est permis, le solveur choisit parmi le permis.
    """

    def test_les_agents_transmis_sont_ceux_declares_admissibles(
        self, regles_diagnostic: str
    ) -> None:
        service = demande_de_service(
            [tache()],
            [agent("A-001"), agent("A-002", disponibilite=DisponibiliteAgent.ABSENT)],
        ).service
        constat = diagnostiquer_paires(regles_diagnostic, traduire_service(service))
        soumises = vers_taches_a_ordonnancer(service, constat)
        assert soumises[0].agents_admissibles == {"aa_001"}

    def test_une_tache_ecartee_ne_recoit_aucun_agent(
        self, regles_diagnostic: str
    ) -> None:
        service = demande_de_service(
            [tache()], [agent(disponibilite=DisponibiliteAgent.ABSENT)]
        ).service
        constat = diagnostiquer_paires(regles_diagnostic, traduire_service(service))
        soumises = vers_taches_a_ordonnancer(service, constat)
        assert soumises[0].agents_admissibles == frozenset()

    def test_aucune_affectation_ne_contredit_le_constat(
        self, cas_usage: PlanifierNettoyage
    ) -> None:
        demande = demande_de_service(
            [tache(f"T-{rang:03d}", secteur="etage_4") for rang in range(1, 6)],
            [
                agent("A-001", secteur="etage_4"),
                agent(
                    "A-002",
                    secteur="etage_5",
                    disponibilite=DisponibiliteAgent.ABSENT,
                ),
                agent("A-003", secteur="etage_5", charge=470),
            ],
        )
        proposition = cas_usage.executer(demande)
        for planifiee in proposition.ordonnancement.planifiees:
            assert (
                planifiee.tache,
                planifiee.agent,
            ) in proposition.constat.admissibles


class TestValidationDeLaDemande:
    def test_un_service_sans_agent_est_refuse(self) -> None:
        with pytest.raises(DemandeInvalideError):
            demande_de_service([tache()], [])

    def test_un_service_sans_tache_est_refuse(self) -> None:
        with pytest.raises(DemandeInvalideError):
            demande_de_service([], [agent()])

    def test_un_service_dont_les_taches_sont_achevees_est_refuse(self) -> None:
        with pytest.raises(DemandeInvalideError):
            demande_de_service([tache(statut=StatutTache.ACHEVEE)], [agent()])


class TestCycleDePlanification:
    def test_un_planning_est_produit(self, cas_usage: PlanifierNettoyage) -> None:
        proposition = cas_usage.executer(demande_de_service([tache()], [agent()]))
        assert proposition.est_complete
        assert len(proposition.ordonnancement.planifiees) == 1

    def test_les_horaires_sont_calcules(self, cas_usage: PlanifierNettoyage) -> None:
        proposition = cas_usage.executer(demande_de_service([tache()], [agent()]))
        planifiee = proposition.ordonnancement.planifiees[0]
        assert planifiee.debut_minutes >= 8 * 60
        assert planifiee.fin_minutes == planifiee.debut_minutes + 40

    def test_une_echeance_est_respectee(self, cas_usage: PlanifierNettoyage) -> None:
        demande = demande_de_service(
            [tache(echeance=time(10, 0)), tache("T-002")], [agent()]
        )
        proposition = cas_usage.executer(demande)
        sous_echeance = next(
            p for p in proposition.ordonnancement.planifiees if p.tache == "tt_001"
        )
        assert sous_echeance.fin_minutes <= 600

    def test_la_charge_est_denombree_par_agent(
        self, cas_usage: PlanifierNettoyage
    ) -> None:
        demande = demande_de_service(
            [tache("T-001"), tache("T-002", prestation=TypePrestation.RECOUCHE)],
            [agent()],
        )
        proposition = cas_usage.executer(demande)
        assert proposition.charge_par_agent == {"aa_001": 60}

    def test_le_planning_d_un_agent_est_restitue(
        self, cas_usage: PlanifierNettoyage
    ) -> None:
        proposition = cas_usage.executer(demande_de_service([tache()], [agent()]))
        assert len(proposition.planning_de("aa_001")) == 1

    def test_un_planning_conforme_n_est_pas_sous_reserve(
        self, cas_usage: PlanifierNettoyage
    ) -> None:
        proposition = cas_usage.executer(demande_de_service([tache()], [agent()]))
        assert not proposition.sous_reserve


class TestQualificationDesTachesEnAttente:
    """Verifie la distinction entre absence d'agent et manque de capacite.

    La distinction determine l'action du responsable et ne peut etre etablie
    par le seul solveur: elle resulte du croisement avec le constat logique.
    """

    def test_une_tache_sans_agent_admissible_est_qualifiee(
        self, cas_usage: PlanifierNettoyage
    ) -> None:
        demande = demande_de_service(
            [tache(secteur="presidentielle")],
            [agent(secteur="etage_4")],
            secteurs_reserves=("presidentielle",),
        )
        proposition = cas_usage.executer(demande)
        assert len(proposition.non_planifiees) == 1
        assert proposition.non_planifiees[0].cause == "aucun_agent_admissible"
        assert proposition.non_planifiees[0].motifs

    def test_une_tache_ecartee_faute_de_temps_est_qualifiee(
        self, cas_usage: PlanifierNettoyage
    ) -> None:
        demande = demande_de_service(
            [
                tache(f"T-{rang:03d}", prestation=TypePrestation.REMISE_EN_ETAT)
                for rang in range(1, 9)
            ],
            [agent()],
        )
        proposition = cas_usage.executer(demande)
        assert proposition.non_planifiees
        assert all(
            attente.cause == "capacite_insuffisante"
            for attente in proposition.non_planifiees
        )

    def test_une_tache_planifiee_ne_figure_pas_en_attente(
        self, cas_usage: PlanifierNettoyage
    ) -> None:
        proposition = cas_usage.executer(demande_de_service([tache()], [agent()]))
        assert proposition.non_planifiees == ()


class TestJustification:
    def test_un_planning_complet_est_annonce(
        self, cas_usage: PlanifierNettoyage
    ) -> None:
        proposition = cas_usage.executer(demande_de_service([tache()], [agent()]))
        assert "planifiees" in proposition.justification[0]

    def test_chaque_affectation_est_formulee(
        self, cas_usage: PlanifierNettoyage
    ) -> None:
        demande = demande_de_service(
            [tache("T-001"), tache("T-002")], [agent("A-001"), agent("A-002")]
        )
        proposition = cas_usage.executer(demande)
        affectations = [
            ligne for ligne in proposition.justification if "confiee a" in ligne
        ]
        assert len(affectations) == len(proposition.ordonnancement.planifiees)

    def test_les_horaires_figurent_dans_la_formulation(
        self, cas_usage: PlanifierNettoyage
    ) -> None:
        proposition = cas_usage.executer(demande_de_service([tache()], [agent()]))
        assert any("h" in ligne for ligne in proposition.justification)

    def test_une_tache_en_attente_est_formulee(
        self, cas_usage: PlanifierNettoyage
    ) -> None:
        demande = demande_de_service(
            [tache(secteur="presidentielle")],
            [agent(secteur="etage_4")],
            secteurs_reserves=("presidentielle",),
        )
        proposition = cas_usage.executer(demande)
        assert any("aucun agent" in ligne for ligne in proposition.justification)

    def test_un_planning_partiel_denombre_les_taches_en_attente(
        self, cas_usage: PlanifierNettoyage
    ) -> None:
        demande = demande_de_service(
            [
                tache(f"T-{rang:03d}", prestation=TypePrestation.REMISE_EN_ETAT)
                for rang in range(1, 9)
            ],
            [agent()],
        )
        proposition = cas_usage.executer(demande)
        assert "en attente" in proposition.justification[0]


class TestChargementDesConnaissances:
    def test_la_base_du_projet_est_chargeable(self) -> None:
        connaissances = ConnaissancesHousekeeping.charger(RACINE)
        assert connaissances.diagnostic

    def test_une_base_absente_est_signalee(self, tmp_path: Path) -> None:
        with pytest.raises(ConnaissancesIndisponiblesError):
            ConnaissancesHousekeeping.charger(tmp_path)


class TestIdentifiants:
    def test_l_identifiant_d_une_tache_est_normalise(self) -> None:
        assert identifiant_tache(tache("T-001")) == "tt_001"

    def test_l_identifiant_d_un_agent_est_normalise(self) -> None:
        assert identifiant_agent(agent("A-001")) == "aa_001"
