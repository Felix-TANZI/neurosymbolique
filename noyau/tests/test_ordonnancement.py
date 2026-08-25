"""Tests de l'ordonnancement par programmation par contraintes.

Les tests de la classe TestGarantiesDOrdonnancement verifient les proprietes
structurelles du modele sur des situations engendrees: absence de recouvrement,
respect des echeances et des plages, et affectation limitee aux agents
admissibles.
"""

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from src.symbolique.ordonnancement import (
    POIDS_PAR_DEFAUT,
    AgentDisponible,
    Ordonnancement,
    TacheAOrdonnancer,
    ordonnancer,
)

MATIN_DEBUT = 8 * 60
MATIN_FIN = 16 * 60


def agent(
    identifiant: str = "A1",
    debut: int = MATIN_DEBUT,
    fin: int = MATIN_FIN,
    secteur: str = "",
) -> AgentDisponible:
    """Construit un agent disponible sur une plage de service."""
    return AgentDisponible(
        identifiant=identifiant, debut_minutes=debut, fin_minutes=fin, secteur=secteur
    )


def tache(
    identifiant: str = "T1",
    duree: int = 40,
    agents: frozenset[str] = frozenset({"A1"}),
    echeance: int | None = None,
    priorite: int = 1,
    secteur: str = "",
) -> TacheAOrdonnancer:
    """Construit une tache soumise a l'ordonnancement."""
    return TacheAOrdonnancer(
        identifiant=identifiant,
        duree_minutes=duree,
        agents_admissibles=agents,
        echeance_minutes=echeance,
        priorite=priorite,
        secteur=secteur,
    )


class TestInvariantsDesEntrees:
    def test_une_duree_nulle_est_refusee(self) -> None:
        with pytest.raises(ValueError):
            tache(duree=0)

    def test_une_duree_negative_est_refusee(self) -> None:
        with pytest.raises(ValueError):
            tache(duree=-10)

    def test_une_plage_inversee_est_refusee(self) -> None:
        with pytest.raises(ValueError):
            agent(debut=MATIN_FIN, fin=MATIN_DEBUT)

    def test_la_capacite_derive_de_la_plage(self) -> None:
        assert agent().capacite_minutes == 480


class TestOrdonnancementNominal:
    def test_une_tache_unique_est_planifiee(self) -> None:
        resultat = ordonnancer([tache()], [agent()])
        assert resultat.est_complet
        assert resultat.optimal
        assert resultat.planifiees[0].agent == "A1"

    def test_une_situation_vide_est_traitee(self) -> None:
        resultat = ordonnancer([], [agent()])
        assert resultat.est_complet
        assert resultat.optimal

    def test_les_taches_d_un_agent_ne_se_recouvrent_pas(self) -> None:
        taches = [tache(f"T{rang}", duree=60) for rang in range(1, 5)]
        resultat = ordonnancer(taches, [agent()])
        planifiees = resultat.taches_de("A1")
        for precedente, suivante in zip(planifiees, planifiees[1:], strict=False):
            assert precedente.fin_minutes <= suivante.debut_minutes

    def test_la_duree_planifiee_correspond_a_la_duree_demandee(self) -> None:
        resultat = ordonnancer([tache(duree=75)], [agent()])
        assert resultat.planifiees[0].duree_minutes == 75

    def test_les_taches_sont_reparties_entre_les_agents(self) -> None:
        taches = [
            tache(f"T{rang}", duree=120, agents=frozenset({"A1", "A2"}))
            for rang in range(1, 7)
        ]
        resultat = ordonnancer(taches, [agent("A1"), agent("A2")])
        assert resultat.est_complet
        assert set(resultat.charge_par_agent) == {"A1", "A2"}

    def test_la_charge_par_agent_est_denombree(self) -> None:
        taches = [tache("T1", duree=40), tache("T2", duree=20)]
        resultat = ordonnancer(taches, [agent()])
        assert resultat.charge_par_agent == {"A1": 60}

    def test_les_taches_d_un_agent_sont_restituees_dans_l_ordre(self) -> None:
        taches = [tache(f"T{rang}", duree=30) for rang in range(1, 4)]
        resultat = ordonnancer(taches, [agent()])
        debuts = [planifiee.debut_minutes for planifiee in resultat.taches_de("A1")]
        assert debuts == sorted(debuts)


class TestPlagesDeService:
    def test_aucune_tache_ne_debute_avant_la_prise_de_service(self) -> None:
        resultat = ordonnancer([tache()], [agent(debut=600, fin=900)])
        assert resultat.planifiees[0].debut_minutes >= 600

    def test_aucune_tache_ne_s_acheve_apres_la_fin_de_service(self) -> None:
        resultat = ordonnancer([tache(duree=60)], [agent(debut=600, fin=900)])
        assert resultat.planifiees[0].fin_minutes <= 900

    def test_une_tache_excedant_la_plage_demeure_non_planifiee(self) -> None:
        resultat = ordonnancer([tache(duree=400)], [agent(debut=600, fin=660)])
        assert not resultat.est_complet
        assert resultat.non_planifiees == {"T1"}


class TestEcheances:
    def test_une_tache_sous_echeance_s_acheve_avant_celle_ci(self) -> None:
        resultat = ordonnancer([tache(echeance=600)], [agent()])
        assert resultat.planifiees[0].fin_minutes <= 600

    def test_une_echeance_intenable_laisse_la_tache_non_planifiee(self) -> None:
        resultat = ordonnancer([tache(duree=60, echeance=MATIN_DEBUT + 30)], [agent()])
        assert resultat.non_planifiees == {"T1"}

    def test_une_tache_sous_echeance_precede_les_autres(self) -> None:
        taches = [
            tache("T1", duree=60),
            tache("T2", duree=60, echeance=MATIN_DEBUT + 60),
        ]
        resultat = ordonnancer(taches, [agent()])
        horaires = {p.tache: p.debut_minutes for p in resultat.planifiees}
        assert horaires["T2"] < horaires["T1"]

    def test_plusieurs_echeances_sont_toutes_respectees(self) -> None:
        taches = [
            tache("T1", duree=40, echeance=MATIN_DEBUT + 120),
            tache("T2", duree=40, echeance=MATIN_DEBUT + 120),
            tache("T3", duree=40, echeance=MATIN_DEBUT + 180),
        ]
        resultat = ordonnancer(taches, [agent()])
        assert resultat.est_complet
        echeances = {"T1": 120, "T2": 120, "T3": 180}
        for planifiee in resultat.planifiees:
            limite = MATIN_DEBUT + echeances[planifiee.tache]
            assert planifiee.fin_minutes <= limite


class TestAdmissibilite:
    """Verifie que le solveur ne retient que les paires declarees admissibles.

    Cette propriete realise la separation entre etablissement du permis, qui
    releve du moteur logique, et choix parmi le permis, qui releve du solveur.
    """

    def test_une_tache_sans_agent_admissible_demeure_non_planifiee(self) -> None:
        resultat = ordonnancer([tache(agents=frozenset())], [agent()])
        assert resultat.non_planifiees == {"T1"}

    def test_une_tache_n_est_confiee_qu_a_un_agent_admissible(self) -> None:
        resultat = ordonnancer(
            [tache(agents=frozenset({"A2"}))], [agent("A1"), agent("A2")]
        )
        assert resultat.planifiees[0].agent == "A2"

    def test_un_agent_admissible_absent_du_service_est_ignore(self) -> None:
        resultat = ordonnancer([tache(agents=frozenset({"A9"}))], [agent("A1")])
        assert resultat.non_planifiees == {"T1"}

    def test_une_ponderation_ne_rend_pas_admissible_une_paire_ecartee(self) -> None:
        poids = dict(POIDS_PAR_DEFAUT) | {"tache_non_planifiee": 100000}
        resultat = ordonnancer(
            [tache(agents=frozenset({"A2"}))], [agent("A1")], poids=poids
        )
        assert resultat.non_planifiees == {"T1"}


class TestPreferences:
    def test_une_tache_urgente_est_planifiee_avant_d_etre_sacrifiee(self) -> None:
        taches = [
            tache("T1", duree=300, priorite=1),
            tache("T2", duree=300, priorite=3),
        ]
        resultat = ordonnancer(taches, [agent(debut=MATIN_DEBUT, fin=MATIN_DEBUT + 300)])
        assert resultat.non_planifiees == {"T1"}

    def test_une_tache_elevee_prime_sur_une_tache_normale(self) -> None:
        taches = [
            tache("T1", duree=300, priorite=1),
            tache("T2", duree=300, priorite=2),
        ]
        resultat = ordonnancer(taches, [agent(debut=MATIN_DEBUT, fin=MATIN_DEBUT + 300)])
        assert resultat.non_planifiees == {"T1"}

    def test_le_secteur_habituel_est_privilegie(self) -> None:
        taches = [tache("T1", agents=frozenset({"A1", "A2"}), secteur="etage_4")]
        resultat = ordonnancer(
            taches,
            [agent("A1", secteur="etage_5"), agent("A2", secteur="etage_4")],
        )
        assert resultat.planifiees[0].agent == "A2"

    def test_une_penalite_de_secteur_nulle_n_impose_aucun_choix(self) -> None:
        poids = dict(POIDS_PAR_DEFAUT) | {"hors_secteur": 0}
        taches = [tache("T1", agents=frozenset({"A1"}), secteur="etage_4")]
        resultat = ordonnancer(taches, [agent("A1", secteur="etage_5")], poids=poids)
        assert resultat.est_complet


class TestSaturation:
    def test_une_charge_excedentaire_laisse_des_taches_non_planifiees(self) -> None:
        taches = [tache(f"T{rang}", duree=120) for rang in range(1, 8)]
        resultat = ordonnancer(taches, [agent()])
        assert not resultat.est_complet
        assert len(resultat.planifiees) == 4

    def test_les_taches_planifiees_demeurent_conformes_sous_saturation(self) -> None:
        taches = [tache(f"T{rang}", duree=120) for rang in range(1, 8)]
        resultat = ordonnancer(taches, [agent()])
        for planifiee in resultat.taches_de("A1"):
            assert planifiee.debut_minutes >= MATIN_DEBUT
            assert planifiee.fin_minutes <= MATIN_FIN

    def test_l_absence_d_agent_laisse_toute_tache_non_planifiee(self) -> None:
        resultat = ordonnancer([tache("T1"), tache("T2")], [])
        assert resultat.non_planifiees == {"T1", "T2"}


class TestRestitution:
    def test_un_ordonnancement_vide_est_complet(self) -> None:
        assert Ordonnancement().est_complet

    def test_les_taches_d_un_agent_inconnu_sont_vides(self) -> None:
        resultat = ordonnancer([tache()], [agent()])
        assert resultat.taches_de("A9") == ()

    def test_une_solution_est_signalee_optimale(self) -> None:
        resultat = ordonnancer([tache()], [agent()])
        assert resultat.optimal
        assert not resultat.interrompu


durees = st.integers(min_value=10, max_value=90)
priorites = st.integers(min_value=1, max_value=3)


@st.composite
def services_quelconques(
    tirage: st.DrawFn,
) -> tuple[list[TacheAOrdonnancer], list[AgentDisponible]]:
    """Engendre un service d'etage aux taches et agents varies."""
    nombre_agents = tirage(st.integers(min_value=1, max_value=3))
    agents = [
        agent(f"A{rang}", secteur=f"secteur_{rang % 2}")
        for rang in range(1, nombre_agents + 1)
    ]
    identifiants = [agent_disponible.identifiant for agent_disponible in agents]

    nombre_taches = tirage(st.integers(min_value=1, max_value=8))
    taches: list[TacheAOrdonnancer] = []
    for rang in range(1, nombre_taches + 1):
        admissibles = tirage(
            st.frozensets(st.sampled_from(identifiants), max_size=len(identifiants))
        )
        echeance = tirage(
            st.one_of(
                st.none(),
                st.integers(min_value=MATIN_DEBUT + 30, max_value=MATIN_FIN),
            )
        )
        taches.append(
            tache(
                f"T{rang}",
                duree=tirage(durees),
                agents=admissibles,
                echeance=echeance,
                priorite=tirage(priorites),
                secteur=f"secteur_{rang % 2}",
            )
        )
    return taches, agents


@pytest.mark.lent
class TestGarantiesDOrdonnancement:
    """Verifie les proprietes structurelles du modele sur des situations engendrees.

    Les proprietes ne portent pas sur un cas particulier: quelle que soit la
    situation, un ordonnancement restitue respecte les plages de service, les
    echeances, l'admissibilite des paires et l'absence de recouvrement.
    """

    @settings(
        max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow]
    )
    @given(service=services_quelconques())
    def test_aucune_tache_ne_recouvre_une_autre_chez_un_meme_agent(
        self, service: tuple[list[TacheAOrdonnancer], list[AgentDisponible]]
    ) -> None:
        taches, agents = service
        resultat = ordonnancer(taches, agents, temps_maximal=5.0)
        for agent_disponible in agents:
            planifiees = resultat.taches_de(agent_disponible.identifiant)
            for precedente, suivante in zip(planifiees, planifiees[1:], strict=False):
                assert precedente.fin_minutes <= suivante.debut_minutes

    @settings(
        max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow]
    )
    @given(service=services_quelconques())
    def test_toute_tache_planifiee_l_est_chez_un_agent_admissible(
        self, service: tuple[list[TacheAOrdonnancer], list[AgentDisponible]]
    ) -> None:
        taches, agents = service
        admissibles = {tache.identifiant: tache.agents_admissibles for tache in taches}
        resultat = ordonnancer(taches, agents, temps_maximal=5.0)
        for planifiee in resultat.planifiees:
            assert planifiee.agent in admissibles[planifiee.tache]

    @settings(
        max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow]
    )
    @given(service=services_quelconques())
    def test_toute_echeance_est_respectee(
        self, service: tuple[list[TacheAOrdonnancer], list[AgentDisponible]]
    ) -> None:
        taches, agents = service
        echeances = {
            tache.identifiant: tache.echeance_minutes
            for tache in taches
            if tache.echeance_minutes is not None
        }
        resultat = ordonnancer(taches, agents, temps_maximal=5.0)
        for planifiee in resultat.planifiees:
            limite = echeances.get(planifiee.tache)
            if limite is not None:
                assert planifiee.fin_minutes <= limite

    @settings(
        max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow]
    )
    @given(service=services_quelconques())
    def test_toute_tache_planifiee_tient_dans_la_plage_de_son_agent(
        self, service: tuple[list[TacheAOrdonnancer], list[AgentDisponible]]
    ) -> None:
        taches, agents = service
        plages = {
            agent_disponible.identifiant: agent_disponible
            for agent_disponible in agents
        }
        resultat = ordonnancer(taches, agents, temps_maximal=5.0)
        for planifiee in resultat.planifiees:
            plage = plages[planifiee.agent]
            assert planifiee.debut_minutes >= plage.debut_minutes
            assert planifiee.fin_minutes <= plage.fin_minutes

    @settings(
        max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow]
    )
    @given(service=services_quelconques())
    def test_toute_tache_est_soit_planifiee_soit_signalee(
        self, service: tuple[list[TacheAOrdonnancer], list[AgentDisponible]]
    ) -> None:
        taches, agents = service
        resultat = ordonnancer(taches, agents, temps_maximal=5.0)
        traitees = {planifiee.tache for planifiee in resultat.planifiees}
        assert traitees | resultat.non_planifiees == {
            tache.identifiant for tache in taches
        }
        assert not traitees & resultat.non_planifiees
