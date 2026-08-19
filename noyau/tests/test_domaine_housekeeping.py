"""Tests du domaine du service housekeeping.

Les tests portent sur les invariants et sur les comportements propres a
l'organisation du travail des etages: charge, capacite et disponibilite.
"""

from datetime import time

import pytest
from src.domaine import (
    DUREES_PAR_DEFAUT,
    AgentEtage,
    DisponibiliteAgent,
    IdentifiantAgent,
    NumeroChambre,
    PlageDeService,
    PrioriteTache,
    Secteur,
    ServiceEtage,
    StatutTache,
    TacheNettoyage,
    TypePrestation,
    ValeurInvalideError,
)

SERVICE_MATIN = PlageDeService(debut=time(8, 0), fin=time(16, 0))


def agent(
    identifiant: str = "A-001",
    secteur: str = "etage_4",
    plage: PlageDeService = SERVICE_MATIN,
    disponibilite: DisponibiliteAgent = DisponibiliteAgent.PRESENT,
    charge: int = 0,
) -> AgentEtage:
    """Construit un agent valide dont seuls les attributs utiles varient."""
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
    duree: int = 0,
) -> TacheNettoyage:
    """Construit une tache valide dont seuls les attributs utiles varient."""
    return TacheNettoyage(
        identifiant=identifiant,
        chambre=NumeroChambre(chambre),
        prestation=prestation,
        secteur=Secteur(secteur),
        echeance=echeance,
        priorite=priorite,
        statut=statut,
        duree_minutes=duree,
    )


class TestPlageDeService:
    def test_une_fin_anterieure_au_debut_est_refusee(self) -> None:
        with pytest.raises(ValeurInvalideError):
            PlageDeService(debut=time(16, 0), fin=time(8, 0))

    def test_une_plage_de_duree_nulle_est_refusee(self) -> None:
        with pytest.raises(ValeurInvalideError):
            PlageDeService(debut=time(8, 0), fin=time(8, 0))

    def test_la_duree_est_exprimee_en_minutes(self) -> None:
        assert SERVICE_MATIN.duree_minutes == 480

    def test_une_plage_couvre_ses_instants_intermediaires(self) -> None:
        assert SERVICE_MATIN.contient(time(12, 0))
        assert SERVICE_MATIN.contient(time(8, 0))
        assert not SERVICE_MATIN.contient(time(16, 0))
        assert not SERVICE_MATIN.contient(time(7, 59))


class TestIdentifiantsHousekeeping:
    def test_un_identifiant_d_agent_vide_est_refuse(self) -> None:
        with pytest.raises(ValeurInvalideError):
            IdentifiantAgent("   ")

    def test_un_nom_de_secteur_vide_est_refuse(self) -> None:
        with pytest.raises(ValeurInvalideError):
            Secteur("")

    def test_les_identifiants_s_affichent_par_leur_valeur(self) -> None:
        assert str(IdentifiantAgent("A-001")) == "A-001"
        assert str(Secteur("etage_4")) == "etage_4"


class TestAgentEtage:
    def test_une_charge_negative_est_refusee(self) -> None:
        with pytest.raises(ValeurInvalideError):
            agent(charge=-10)

    def test_une_charge_superieure_a_la_plage_est_refusee(self) -> None:
        with pytest.raises(ValeurInvalideError):
            agent(charge=500)

    def test_les_minutes_restantes_deduisent_la_charge(self) -> None:
        assert agent(charge=180).minutes_restantes == 300

    def test_un_agent_present_et_disponible_est_affectable(self) -> None:
        assert agent().est_affectable

    def test_un_agent_absent_n_est_pas_affectable(self) -> None:
        assert not agent(disponibilite=DisponibiliteAgent.ABSENT).est_affectable

    def test_un_agent_en_retard_n_est_pas_affectable(self) -> None:
        assert not agent(disponibilite=DisponibiliteAgent.RETARD).est_affectable

    def test_un_agent_sans_temps_restant_n_est_pas_affectable(self) -> None:
        assert not agent(charge=480).est_affectable

    def test_le_changement_de_disponibilite_produit_une_nouvelle_instance(self) -> None:
        present = agent()
        absent = present.avec_disponibilite(DisponibiliteAgent.ABSENT)
        assert present.est_affectable
        assert not absent.est_affectable

    def test_le_changement_de_charge_produit_une_nouvelle_instance(self) -> None:
        initial = agent(charge=0)
        charge = initial.avec_charge(120)
        assert initial.minutes_restantes == 480
        assert charge.minutes_restantes == 360

    def test_l_identite_prime_sur_les_attributs(self) -> None:
        present = agent("A-001")
        absent = agent("A-001", disponibilite=DisponibiliteAgent.ABSENT)
        assert present == absent
        assert present != agent("A-002")

    def test_un_agent_n_est_pas_egal_a_un_autre_type(self) -> None:
        assert agent("A-001") != "A-001"

    def test_un_agent_est_utilisable_comme_cle(self) -> None:
        assert len({agent("A-001"), agent("A-001"), agent("A-002")}) == 2


class TestTacheNettoyage:
    def test_un_identifiant_vide_est_refuse(self) -> None:
        with pytest.raises(ValeurInvalideError):
            tache(identifiant="  ")

    def test_une_duree_negative_est_refusee(self) -> None:
        with pytest.raises(ValeurInvalideError):
            tache(duree=-5)

    def test_la_duree_par_defaut_depend_de_la_prestation(self) -> None:
        assert tache(prestation=TypePrestation.RECOUCHE).duree_effective == (
            DUREES_PAR_DEFAUT[TypePrestation.RECOUCHE]
        )
        assert tache(prestation=TypePrestation.DEPART).duree_effective == (
            DUREES_PAR_DEFAUT[TypePrestation.DEPART]
        )

    def test_une_duree_precisee_prime_sur_celle_de_la_prestation(self) -> None:
        assert tache(prestation=TypePrestation.RECOUCHE, duree=35).duree_effective == 35

    def test_une_tache_sans_echeance_n_est_pas_sous_contrainte(self) -> None:
        assert not tache().est_sous_echeance

    def test_une_tache_avec_echeance_est_sous_contrainte(self) -> None:
        assert tache(echeance=time(13, 0)).est_sous_echeance

    def test_une_tache_neuve_est_a_planifier(self) -> None:
        assert tache().est_a_planifier

    def test_une_tache_planifiee_n_est_plus_a_planifier(self) -> None:
        assert not tache(statut=StatutTache.PLANIFIEE).est_a_planifier

    def test_le_changement_de_priorite_produit_une_nouvelle_instance(self) -> None:
        normale = tache()
        urgente = normale.avec_priorite(PrioriteTache.URGENTE)
        assert normale.priorite is PrioriteTache.NORMALE
        assert urgente.priorite is PrioriteTache.URGENTE

    def test_le_changement_d_echeance_produit_une_nouvelle_instance(self) -> None:
        sans = tache()
        avec = sans.avec_echeance(time(13, 0))
        assert not sans.est_sous_echeance
        assert avec.est_sous_echeance

    def test_l_affectation_d_un_agent_produit_une_nouvelle_instance(self) -> None:
        libre = tache()
        affectee = libre.avec_agent(IdentifiantAgent("A-001"))
        assert libre.agent_affecte is None
        assert affectee.agent_affecte == IdentifiantAgent("A-001")

    def test_le_changement_de_statut_produit_une_nouvelle_instance(self) -> None:
        initiale = tache()
        planifiee = initiale.avec_statut(StatutTache.PLANIFIEE)
        assert initiale.est_a_planifier
        assert not planifiee.est_a_planifier

    def test_l_identite_prime_sur_les_attributs(self) -> None:
        assert tache("T-001") == tache("T-001", priorite=PrioriteTache.URGENTE)
        assert tache("T-001") != tache("T-002")

    def test_une_tache_n_est_pas_egale_a_un_autre_type(self) -> None:
        assert tache("T-001") != "T-001"

    def test_une_tache_est_utilisable_comme_cle(self) -> None:
        assert len({tache("T-1"), tache("T-1"), tache("T-2")}) == 2


class TestPriorites:
    def test_les_priorites_sont_ordonnees(self) -> None:
        assert PrioriteTache.NORMALE < PrioriteTache.ELEVEE
        assert PrioriteTache.ELEVEE < PrioriteTache.URGENTE

    def test_la_comparaison_large_accepte_l_egalite(self) -> None:
        assert PrioriteTache.URGENTE <= PrioriteTache.URGENTE


class TestServiceEtage:
    def test_un_service_vide_ne_comporte_ni_charge_ni_capacite(self) -> None:
        service = ServiceEtage()
        assert service.charge_totale_minutes == 0
        assert service.capacite_totale_minutes == 0

    def test_seules_les_taches_a_planifier_comptent_dans_la_charge(self) -> None:
        service = ServiceEtage(
            taches=frozenset(
                {
                    tache("T-1", prestation=TypePrestation.DEPART),
                    tache(
                        "T-2",
                        prestation=TypePrestation.DEPART,
                        statut=StatutTache.ACHEVEE,
                    ),
                }
            )
        )
        assert len(service.taches_a_planifier) == 1
        assert service.charge_totale_minutes == 40

    def test_seuls_les_agents_affectables_comptent_dans_la_capacite(self) -> None:
        service = ServiceEtage(
            agents=frozenset(
                {
                    agent("A-1"),
                    agent("A-2", disponibilite=DisponibiliteAgent.ABSENT),
                }
            )
        )
        assert len(service.agents_affectables) == 1
        assert service.capacite_totale_minutes == 480

    def test_une_capacite_suffisante_n_est_pas_signalee(self) -> None:
        service = ServiceEtage(
            taches=frozenset({tache("T-1")}),
            agents=frozenset({agent("A-1")}),
        )
        assert not service.est_sous_capacite

    def test_une_charge_excedant_la_capacite_est_signalee(self) -> None:
        taches = frozenset(
            tache(f"T-{rang}", prestation=TypePrestation.REMISE_EN_ETAT)
            for rang in range(1, 10)
        )
        service = ServiceEtage(
            taches=taches,
            agents=frozenset({agent("A-1", charge=300)}),
        )
        assert service.est_sous_capacite

    def test_l_absence_d_agent_rend_toute_charge_excedentaire(self) -> None:
        service = ServiceEtage(taches=frozenset({tache("T-1")}))
        assert service.est_sous_capacite
