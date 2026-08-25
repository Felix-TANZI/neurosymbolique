"""Tests du generateur d'etablissement.

Les tests verifient les proprietes qui font d'un jeu synthetique un instrument
de validation: la reproductibilite, sans laquelle aucune mesure n'est
comparable, et la coherence entre entites, sans laquelle l'etablissement
engendre ne represente aucune exploitation reelle.
"""

from datetime import date, time
from pathlib import Path

import pytest
from src.domaine import (
    Categorie,
    EtatOccupation,
    EtatProprete,
    EtatTechnique,
    Gravite,
    Periode,
    StatutTache,
)
from src.donnees import (
    DepotAgents,
    DepotChambres,
    DepotIncidents,
    DepotReservations,
    DepotSecteurs,
    DepotTaches,
    ProfilDEtablissement,
    ValeurDeProfilInvalideError,
    creer_fabrique_de_sessions,
    creer_moteur,
    engendrer_etablissement,
    reinitialiser_schema,
    session_de_travail,
)
from src.donnees.simulation import INCIDENTS_BLOQUANTS

JOUR = date(2026, 8, 12)


def profil(
    chambres: int = 120,
    etages: int = 6,
    taux_occupation: float = 0.78,
    part_incidents: float = 0.03,
    part_agents_indisponibles: float = 0.12,
    heure_de_reference: time = time(10, 0),
    graine: int = 20260812,
) -> ProfilDEtablissement:
    """Construit un profil dont seuls les parametres utiles varient."""
    return ProfilDEtablissement(
        nom="essai",
        chambres=chambres,
        etages=etages,
        taux_occupation=taux_occupation,
        part_incidents=part_incidents,
        part_agents_indisponibles=part_agents_indisponibles,
        heure_de_reference=heure_de_reference,
        graine=graine,
    )


class TestValiditeDuProfil:
    def test_un_etablissement_sans_chambre_est_refuse(self) -> None:
        with pytest.raises(ValeurDeProfilInvalideError):
            profil(chambres=0)

    def test_un_etablissement_sans_etage_est_refuse(self) -> None:
        with pytest.raises(ValeurDeProfilInvalideError):
            profil(etages=0)

    def test_un_taux_d_occupation_hors_bornes_est_refuse(self) -> None:
        with pytest.raises(ValeurDeProfilInvalideError):
            profil(taux_occupation=1.4)

    def test_une_part_d_incidents_hors_bornes_est_refusee(self) -> None:
        with pytest.raises(ValeurDeProfilInvalideError):
            profil(part_incidents=-0.1)

    def test_la_repartition_par_etage_est_calculee(self) -> None:
        assert profil(chambres=120, etages=6).chambres_par_etage == 20


class TestReproductibilite:
    """Verifie qu'une meme graine produit toujours le meme etablissement.

    Sans cette propriete, aucune mesure de latence ni aucune comparaison entre
    deux versions du systeme ne serait exploitable: l'ecart observe pourrait
    provenir du jeu de donnees plutot que du systeme.
    """

    def test_une_meme_graine_produit_un_meme_parc(self) -> None:
        premier = engendrer_etablissement(profil(), JOUR)
        second = engendrer_etablissement(profil(), JOUR)
        assert premier.chambres == second.chambres
        assert [chambre.categorie for chambre in premier.chambres] == [
            chambre.categorie for chambre in second.chambres
        ]

    def test_une_meme_graine_produit_les_memes_sejours(self) -> None:
        premier = engendrer_etablissement(profil(), JOUR)
        second = engendrer_etablissement(profil(), JOUR)
        assert [sejour.identifiant for sejour in premier.reservations] == [
            sejour.identifiant for sejour in second.reservations
        ]
        assert [sejour.chambre_affectee for sejour in premier.reservations] == [
            sejour.chambre_affectee for sejour in second.reservations
        ]

    def test_une_graine_differente_produit_un_etat_different(self) -> None:
        premier = engendrer_etablissement(profil(graine=1), JOUR)
        second = engendrer_etablissement(profil(graine=2), JOUR)
        assert premier.resumer() != second.resumer()

    def test_le_resume_est_stable(self) -> None:
        premier = engendrer_etablissement(profil(), JOUR)
        second = engendrer_etablissement(profil(), JOUR)
        assert premier.resumer() == second.resumer()


class TestCoherenceDuParc:
    def test_le_parc_comporte_le_nombre_demande(self) -> None:
        assert len(engendrer_etablissement(profil(chambres=250), JOUR).parc) == 250

    def test_les_numeros_sont_uniques(self) -> None:
        chambres = engendrer_etablissement(profil(chambres=300), JOUR).chambres
        assert len({str(chambre.numero) for chambre in chambres}) == 300

    def test_les_etages_demeurent_dans_les_bornes(self) -> None:
        etablissement = engendrer_etablissement(profil(chambres=120, etages=6), JOUR)
        assert all(1 <= chambre.etage <= 6 for chambre in etablissement.chambres)

    def test_la_capacite_suit_la_categorie(self) -> None:
        chambres = engendrer_etablissement(profil(), JOUR).chambres
        suites = [c for c in chambres if c.categorie is Categorie.SUITE]
        standards = [c for c in chambres if c.categorie is Categorie.STANDARD]
        assert all(chambre.capacite >= 4 for chambre in suites)
        assert all(chambre.capacite == 2 for chambre in standards)

    def test_chaque_chambre_dispose_d_une_literie(self) -> None:
        from src.domaine import Equipement

        literies = {Equipement.LIT_SIMPLE, Equipement.LIT_DOUBLE, Equipement.LIT_KING}
        chambres = engendrer_etablissement(profil(), JOUR).chambres
        assert all(chambre.equipements & literies for chambre in chambres)

    def test_les_categories_suivent_la_distribution_du_secteur(self) -> None:
        """La pyramide des categories demeure large a sa base."""
        chambres = engendrer_etablissement(profil(chambres=400, etages=10), JOUR).chambres
        standards = sum(1 for c in chambres if c.categorie is Categorie.STANDARD)
        suites = sum(1 for c in chambres if c.categorie is Categorie.SUITE)
        assert standards > suites * 3

    def test_les_communications_sont_reciproques(self) -> None:
        chambres = engendrer_etablissement(profil(), JOUR).chambres
        par_numero = {str(chambre.numero): chambre for chambre in chambres}
        for chambre in chambres:
            for voisine in chambre.chambres_communicantes:
                assert str(voisine) in par_numero
                assert chambre.numero in par_numero[str(voisine)].chambres_communicantes

    def test_les_secteurs_couvrent_le_parc(self) -> None:
        etablissement = engendrer_etablissement(profil(), JOUR)
        assert len(etablissement.secteurs) >= 1
        assert all(secteur for _, secteur in etablissement.parc)


class TestCoherenceEntreOffreEtDemande:
    """Verifie que la demande engendree correspond a l'offre du parc.

    Un jeu synthetique dont les caracteristiques sont tirees independamment
    produit des sejours qu'aucune chambre ne peut satisfaire. La validite d'un
    tel jeu ne tient pas au realisme de chaque entite prise isolement, mais a
    la coherence entre elles.
    """

    def test_chaque_sejour_trouve_une_chambre_compatible(self) -> None:
        etablissement = engendrer_etablissement(profil(), JOUR)
        chambres = etablissement.chambres

        for sejour in etablissement.reservations:
            compatibles = [
                chambre
                for chambre in chambres
                if chambre.capacite >= sejour.nombre_personnes
                and chambre.categorie >= sejour.categorie_contractee
                and sejour.exigences_obligatoires <= chambre.equipements
            ]
            assert compatibles, f"aucune chambre compatible pour {sejour.identifiant}"

    def test_la_part_de_sejours_sans_chambre_demeure_faible(self) -> None:
        etablissement = engendrer_etablissement(profil(), JOUR)
        resume = etablissement.resumer()
        assert resume["sans_chambre"] < resume["reservations"] * 0.15

    def test_les_arrivees_du_jour_comportent_des_cas_a_traiter(self) -> None:
        etablissement = engendrer_etablissement(profil(), JOUR)
        a_traiter = [
            sejour
            for sejour in etablissement.reservations
            if sejour.periode.arrivee == JOUR and not sejour.est_affectee
        ]
        assert a_traiter

    def test_aucune_chambre_ne_recoit_deux_sejours_simultanes(self) -> None:
        etablissement = engendrer_etablissement(profil(), JOUR)
        par_chambre: dict[str, list[Periode]] = {}

        for sejour in etablissement.reservations:
            if sejour.chambre_affectee is None:
                continue
            reference = str(sejour.chambre_affectee)
            for periode in par_chambre.get(reference, []):
                assert not sejour.periode.chevauche(periode)
            par_chambre.setdefault(reference, []).append(sejour.periode)

    def test_une_chambre_affectee_appartient_au_parc(self) -> None:
        etablissement = engendrer_etablissement(profil(), JOUR)
        numeros = {str(chambre.numero) for chambre in etablissement.chambres}
        for sejour in etablissement.reservations:
            if sejour.chambre_affectee is not None:
                assert str(sejour.chambre_affectee) in numeros


class TestPropagationDesIncidents:
    """Verifie que les incidents se repercutent sur l'etat des chambres.

    La propagation constitue la trace, dans les donnees, de la coherence entre
    services que le systeme est charge de maintenir.
    """

    def test_un_incident_grave_et_bloquant_immobilise_la_chambre(self) -> None:
        etablissement = engendrer_etablissement(profil(part_incidents=0.2), JOUR)
        par_numero = {str(c.numero): c for c in etablissement.chambres}

        bloquantes = [
            incident
            for incident in etablissement.incidents
            if incident.est_ouvert
            and incident.type_incident in INCIDENTS_BLOQUANTS
            and incident.gravite >= Gravite.MAJEURE
        ]
        for incident in bloquantes:
            assert (
                par_numero[str(incident.chambre)].etat_technique
                is EtatTechnique.BLOQUEE
            )

    def test_un_incident_resolu_n_affecte_pas_la_chambre(self) -> None:
        etablissement = engendrer_etablissement(profil(part_incidents=0.25), JOUR)
        par_numero = {str(c.numero): c for c in etablissement.chambres}
        ouverts = {
            str(incident.chambre)
            for incident in etablissement.incidents
            if incident.est_ouvert
        }
        resolus = [
            incident
            for incident in etablissement.incidents
            if not incident.est_ouvert and str(incident.chambre) not in ouverts
        ]
        for incident in resolus:
            assert (
                par_numero[str(incident.chambre)].etat_technique
                is EtatTechnique.OPERATIONNELLE
            )

    def test_les_incidents_portent_sur_des_chambres_du_parc(self) -> None:
        etablissement = engendrer_etablissement(profil(), JOUR)
        numeros = {str(chambre.numero) for chambre in etablissement.chambres}
        assert all(
            str(incident.chambre) in numeros for incident in etablissement.incidents
        )


class TestServiceDEtage:
    def test_les_agents_sont_dimensionnes_sur_la_charge(self) -> None:
        etablissement = engendrer_etablissement(profil(chambres=120, etages=6), JOUR)
        assert len(etablissement.agents) >= len(etablissement.secteurs)

    def test_chaque_agent_est_rattache_a_un_secteur_du_parc(self) -> None:
        etablissement = engendrer_etablissement(profil(), JOUR)
        secteurs = set(etablissement.secteurs)
        assert all(str(agent.secteur) in secteurs for agent, _ in etablissement.agents)

    def test_une_part_des_agents_est_indisponible(self) -> None:
        etablissement = engendrer_etablissement(
            profil(chambres=300, etages=10, part_agents_indisponibles=0.3), JOUR
        )
        assert etablissement.resumer()["agents_indisponibles"] > 0

    def test_les_taches_portent_sur_des_chambres_non_pretes(self) -> None:
        etablissement = engendrer_etablissement(profil(), JOUR)
        par_numero = {str(c.numero): c for c in etablissement.chambres}
        for tache, _ in etablissement.taches:
            assert (
                par_numero[str(tache.chambre)].etat_proprete is not EtatProprete.PRETE
            )

    def test_les_taches_sont_a_planifier(self) -> None:
        etablissement = engendrer_etablissement(profil(), JOUR)
        assert all(
            tache.statut is StatutTache.A_PLANIFIER
            for tache, _ in etablissement.taches
        )

    def test_une_tache_de_suite_exige_une_qualification(self) -> None:
        etablissement = engendrer_etablissement(profil(chambres=300, etages=10), JOUR)
        par_numero = {str(c.numero): c for c in etablissement.chambres}
        for tache, qualifications in etablissement.taches:
            if par_numero[str(tache.chambre)].categorie is Categorie.SUITE:
                assert qualifications

    def test_le_secteur_reserve_est_declare(self) -> None:
        etablissement = engendrer_etablissement(profil(), JOUR)
        assert etablissement.secteurs_reserves


class TestMomentDeLaJournee:
    def test_le_matin_laisse_une_part_importante_du_parc_a_traiter(self) -> None:
        matin = engendrer_etablissement(
            profil(heure_de_reference=time(9, 0), graine=7), JOUR
        )
        apres_midi = engendrer_etablissement(
            profil(heure_de_reference=time(17, 0), graine=7), JOUR
        )
        assert len(matin.taches) > len(apres_midi.taches)


@pytest.mark.lent
class TestConstitutionDeLaBase:
    """Verifie qu'un etablissement engendre peut etre persiste integralement."""

    def test_un_etablissement_est_enregistre_puis_relu(self, tmp_path: Path) -> None:
        moteur = creer_moteur(f"sqlite:///{tmp_path}/etablissement.sqlite3")
        reinitialiser_schema(moteur)
        fabrique = creer_fabrique_de_sessions(moteur)
        etablissement = engendrer_etablissement(profil(chambres=60, etages=3), JOUR)

        with session_de_travail(fabrique) as session:
            DepotChambres(session).enregistrer_plusieurs(etablissement.parc)
            session.flush()
            for reservation in etablissement.reservations:
                DepotReservations(session).enregistrer(reservation)
            DepotIncidents(session).enregistrer_plusieurs(etablissement.incidents)
            DepotAgents(session).enregistrer_plusieurs(etablissement.agents)
            DepotTaches(session).enregistrer_plusieurs(etablissement.taches)
            DepotSecteurs(session).declarer_reserves(etablissement.secteurs_reserves)

        with session_de_travail(fabrique) as session:
            assert DepotChambres(session).denombrer() == 60
            assert DepotReservations(session).denombrer() == len(
                etablissement.reservations
            )
            assert len(DepotAgents(session).lister()) == len(etablissement.agents)
            assert len(DepotTaches(session).lister_a_planifier()) == len(
                etablissement.taches
            )

        moteur.dispose()

    def test_les_etats_persistes_correspondent_a_ceux_engendres(
        self, tmp_path: Path
    ) -> None:
        moteur = creer_moteur(f"sqlite:///{tmp_path}/etats.sqlite3")
        reinitialiser_schema(moteur)
        fabrique = creer_fabrique_de_sessions(moteur)
        etablissement = engendrer_etablissement(profil(chambres=40, etages=2), JOUR)

        with session_de_travail(fabrique) as session:
            DepotChambres(session).enregistrer_plusieurs(etablissement.parc)

        with session_de_travail(fabrique) as session:
            relues = {
                str(chambre.numero): chambre
                for chambre in DepotChambres(session).lister()
            }

        for originale in etablissement.chambres:
            relue = relues[str(originale.numero)]
            assert relue.etat_proprete is originale.etat_proprete
            assert relue.etat_technique is originale.etat_technique
            assert relue.etat_occupation is originale.etat_occupation
            assert relue.equipements == originale.equipements
            assert relue.categorie is originale.categorie

        moteur.dispose()


@pytest.mark.lent
class TestMonteeEnCharge:
    """Verifie que le generateur demeure coherent a differentes echelles."""

    @pytest.mark.parametrize(
        ("chambres", "etages"), [(120, 6), (400, 10), (800, 16)]
    )
    def test_un_etablissement_demeure_coherent_a_toute_echelle(
        self, chambres: int, etages: int
    ) -> None:
        etablissement = engendrer_etablissement(
            profil(chambres=chambres, etages=etages), JOUR
        )
        resume = etablissement.resumer()

        assert resume["chambres"] == chambres
        assert resume["reservations"] > chambres
        assert resume["agents"] >= etages
        assert 0 < resume["disponibles"] <= chambres
        assert resume["taches"] <= chambres

    def test_les_occupations_refletent_les_sejours_en_cours(self) -> None:
        etablissement = engendrer_etablissement(profil(chambres=200, etages=8), JOUR)
        occupees = {
            str(chambre.numero)
            for chambre in etablissement.chambres
            if chambre.etat_occupation is EtatOccupation.OCCUPEE
        }
        attendues = {
            str(sejour.chambre_affectee)
            for sejour in etablissement.reservations
            if sejour.chambre_affectee is not None and sejour.periode.contient(JOUR)
        }
        assert occupees == attendues
