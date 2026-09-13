"""Verification de l'affectation des interventions de maintenance.

Le service repond a trois decisions: qualifier la portee d'une defaillance,
ordonner les interventions, et les confier a des techniciens qualifies. Chacune
comporte des invariants qu'un defaut rendrait invisible: une intervention
immediate traitee apres une differee, un technicien affecte sans qualification,
une charge depassant ce qu'un agent peut conduire.
"""

from datetime import datetime, timedelta

import pytest
from src.domaine import Gravite, TypeIncident
from src.domaine.maintenance import (
    Competence,
    Criticite,
    IdentifiantTechnicien,
    Intervention,
    MaintenanceInvalideError,
    StatutDIntervention,
    Technicien,
    TypeDEquipementCommun,
    competence_requise,
    qualifier_la_criticite,
)
from src.domaine.valeurs import NumeroChambre
from src.orchestration.maintenance import AffecterLesInterventions

MAINTENANT = datetime(2026, 8, 12, 9, 0)


def _technicien(
    reference: str, competences: tuple[Competence, ...], charge: int = 0
) -> Technicien:
    """Constitue un technicien disponible."""
    return Technicien(
        identifiant=IdentifiantTechnicien(reference),
        competences=frozenset(competences),
        disponible=True,
        charge_en_cours=charge,
    )


def _intervention(
    reference: str,
    competence: Competence,
    criticite: Criticite,
    chambre: str = "312",
    minutes: int = 0,
) -> Intervention:
    """Constitue une intervention a planifier."""
    return Intervention(
        identifiant=reference,
        competence=competence,
        criticite=int(criticite),
        duree_estimee=timedelta(minutes=60),
        chambre=NumeroChambre(chambre),
        signalee_le=MAINTENANT + timedelta(minutes=minutes),
        statut=StatutDIntervention.A_PLANIFIER.value,
    )


class TestQualificationDeLaCriticite:
    """Verifie l'appreciation de la portee d'une defaillance."""

    def test_un_risque_de_securite_demeure_immediat(self) -> None:
        """L'intensite n'attenue jamais un risque pour les personnes."""
        criticite = qualifier_la_criticite(
            TypeIncident.RISQUE_SECURITE, Gravite.MINEURE
        )
        assert criticite is Criticite.IMMEDIATE

    def test_une_gravite_critique_emporte_l_immediatete(self) -> None:
        criticite = qualifier_la_criticite(
            TypeIncident.PANNE_CLIMATISATION, Gravite.CRITIQUE
        )
        assert criticite is Criticite.IMMEDIATE

    def test_une_portee_etendue_eleve_la_criticite(self) -> None:
        """Une panne affectant plusieurs chambres immobilise davantage."""
        isolee = qualifier_la_criticite(
            TypeIncident.PANNE_ELECTRIQUE, Gravite.MODEREE, portee=1
        )
        etendue = qualifier_la_criticite(
            TypeIncident.PANNE_ELECTRIQUE, Gravite.MODEREE, portee=40
        )
        assert etendue > isolee

    def test_une_panne_mineure_isolee_demeure_differee(self) -> None:
        criticite = qualifier_la_criticite(
            TypeIncident.MOBILIER_ENDOMMAGE, Gravite.MINEURE
        )
        assert criticite is Criticite.DIFFEREE


class TestCompetenceRequise:
    """Verifie l'etablissement de la qualification appelee."""

    def test_un_degat_des_eaux_appelle_la_plomberie(self) -> None:
        assert (
            competence_requise(type_incident=TypeIncident.DEGAT_DES_EAUX)
            is Competence.PLOMBERIE
        )

    def test_un_ascenseur_appelle_sa_specialite(self) -> None:
        assert (
            competence_requise(equipement=TypeDEquipementCommun.ASCENSEUR)
            is Competence.ASCENSEUR
        )

    def test_une_defaillance_sans_specialite_restitue_la_polyvalence(self) -> None:
        assert (
            competence_requise(type_incident=TypeIncident.NUISANCE_SONORE)
            is Competence.POLYVALENT
        )


class TestQualificationDesTechniciens:
    """Verifie l'etablissement de ce qu'un technicien peut conduire."""

    def test_un_specialiste_maitrise_sa_competence(self) -> None:
        technicien = _technicien("T-0001", (Competence.PLOMBERIE,))
        assert technicien.maitrise(Competence.PLOMBERIE)

    def test_un_specialiste_ne_maitrise_pas_les_autres(self) -> None:
        technicien = _technicien("T-0001", (Competence.PLOMBERIE,))
        assert not technicien.maitrise(Competence.ASCENSEUR)

    def test_tout_technicien_conduit_une_intervention_sans_specialite(self) -> None:
        """La polyvalence requise designe l'absence d'exigence."""
        technicien = _technicien("T-0001", (Competence.PLOMBERIE,))
        assert technicien.maitrise(Competence.POLYVALENT)

    def test_un_polyvalent_couvre_toute_specialite(self) -> None:
        technicien = _technicien("T-0001", (Competence.POLYVALENT,))
        assert technicien.maitrise(Competence.ASCENSEUR)

    def test_un_technicien_sans_competence_est_refuse(self) -> None:
        with pytest.raises(MaintenanceInvalideError, match="competence"):
            Technicien(
                identifiant=IdentifiantTechnicien("T-0001"),
                competences=frozenset(),
            )


class TestOrdonnancement:
    """Verifie l'ordre dans lequel les interventions sont traitees."""

    def test_la_criticite_prime_sur_l_anciennete(self) -> None:
        """Traiter d'abord le plus ancien laisserait une urgence sans reponse."""
        ancienne = _intervention(
            "I-1", Competence.PLOMBERIE, Criticite.DIFFEREE, minutes=0
        )
        recente = _intervention(
            "I-2", Competence.PLOMBERIE, Criticite.IMMEDIATE, minutes=60
        )
        techniciens = [_technicien("T-0001", (Competence.PLOMBERIE,))]

        plan = AffecterLesInterventions().executer(
            [ancienne, recente], techniciens
        )

        assert plan.affectees[0].reference == "I-2"

    def test_a_criticite_egale_l_anciennete_departage(self) -> None:
        premiere = _intervention(
            "I-1", Competence.PLOMBERIE, Criticite.COURANTE, minutes=0
        )
        seconde = _intervention(
            "I-2", Competence.PLOMBERIE, Criticite.COURANTE, minutes=60
        )
        techniciens = [_technicien("T-0001", (Competence.PLOMBERIE,))]

        plan = AffecterLesInterventions().executer(
            [seconde, premiere], techniciens
        )

        assert plan.affectees[0].reference == "I-1"


class TestAffectation:
    """Verifie le choix des techniciens."""

    def test_un_specialiste_est_prefere_a_un_polyvalent(self) -> None:
        """Reserver la polyvalence aux interventions qu'elle seule couvre."""
        intervention = _intervention(
            "I-1", Competence.PLOMBERIE, Criticite.COURANTE
        )
        techniciens = [
            _technicien("T-0001", (Competence.POLYVALENT,)),
            _technicien("T-0002", (Competence.PLOMBERIE,)),
        ]

        plan = AffecterLesInterventions().executer([intervention], techniciens)

        assert str(plan.affectees[0].technicien.identifiant) == "T-0002"

    def test_a_qualification_egale_le_moins_charge_est_retenu(self) -> None:
        intervention = _intervention(
            "I-1", Competence.PLOMBERIE, Criticite.COURANTE
        )
        techniciens = [
            _technicien("T-0001", (Competence.PLOMBERIE,), charge=3),
            _technicien("T-0002", (Competence.PLOMBERIE,), charge=0),
        ]

        plan = AffecterLesInterventions().executer([intervention], techniciens)

        assert str(plan.affectees[0].technicien.identifiant) == "T-0002"

    def test_une_competence_absente_laisse_l_intervention_en_attente(self) -> None:
        intervention = _intervention(
            "I-1", Competence.ASCENSEUR, Criticite.IMMEDIATE
        )
        techniciens = [_technicien("T-0001", (Competence.PLOMBERIE,))]

        plan = AffecterLesInterventions().executer([intervention], techniciens)

        assert not plan.affectees
        assert plan.en_attente[0].cause == "competence_absente"
        assert plan.en_attente[0].detail == "ascenseur"

    def test_une_charge_saturee_est_distinguee_d_une_competence_absente(
        self,
    ) -> None:
        """Le motif designe ce qu'il faut lever: un renfort ou une competence."""
        interventions = [
            _intervention(
                f"I-{rang}", Competence.PLOMBERIE, Criticite.COURANTE
            )
            for rang in range(1, 7)
        ]
        techniciens = [_technicien("T-0001", (Competence.PLOMBERIE,))]

        plan = AffecterLesInterventions().executer(interventions, techniciens)

        assert len(plan.affectees) == 4
        assert all(
            manquee.cause == "charge_saturee" for manquee in plan.en_attente
        )

    def test_aucun_technicien_disponible_est_signale(self) -> None:
        intervention = _intervention(
            "I-1", Competence.PLOMBERIE, Criticite.IMMEDIATE
        )
        indisponible = Technicien(
            identifiant=IdentifiantTechnicien("T-0001"),
            competences=frozenset({Competence.PLOMBERIE}),
            disponible=False,
        )

        plan = AffecterLesInterventions().executer([intervention], [indisponible])

        assert plan.en_attente[0].cause == "aucun_technicien_disponible"

    def test_une_intervention_achevee_n_est_pas_reaffectee(self) -> None:
        from dataclasses import replace

        achevee = replace(
            _intervention("I-1", Competence.PLOMBERIE, Criticite.COURANTE),
            statut=StatutDIntervention.ACHEVEE.value,
        )
        techniciens = [_technicien("T-0001", (Competence.PLOMBERIE,))]

        plan = AffecterLesInterventions().executer([achevee], techniciens)

        assert not plan.affectees
        assert not plan.en_attente


class TestInvariantsDeLIntervention:
    """Verifie ce qu'une intervention doit comporter."""

    def test_une_intervention_sans_objet_est_refusee(self) -> None:
        with pytest.raises(MaintenanceInvalideError, match="ne porte sur rien"):
            Intervention(
                identifiant="I-1",
                competence=Competence.PLOMBERIE,
                criticite=int(Criticite.COURANTE),
                duree_estimee=timedelta(minutes=60),
            )

    def test_une_intervention_sur_deux_objets_est_refusee(self) -> None:
        with pytest.raises(MaintenanceInvalideError, match="deux objets"):
            Intervention(
                identifiant="I-1",
                competence=Competence.PLOMBERIE,
                criticite=int(Criticite.COURANTE),
                duree_estimee=timedelta(minutes=60),
                chambre=NumeroChambre("312"),
                equipement="ASC-4",
            )

    def test_une_duree_nulle_est_refusee(self) -> None:
        with pytest.raises(MaintenanceInvalideError, match="duree"):
            Intervention(
                identifiant="I-1",
                competence=Competence.PLOMBERIE,
                criticite=int(Criticite.COURANTE),
                duree_estimee=timedelta(),
                chambre=NumeroChambre("312"),
            )
