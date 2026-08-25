"""Tests de la couche de persistance.

Les tests de la classe TestAllerRetour verifient la propriete centrale de la
conversion: une entite ecrite puis relue demeure identique a l'originale.
Toute perte d'information a la conversion fausserait le raisonnement conduit
sur les donnees restituees.
"""

from collections.abc import Iterator
from datetime import date, datetime, time
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from src.domaine import (
    AgentEtage,
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
    IdentifiantAgent,
    IdentifiantReservation,
    Incident,
    NumeroChambre,
    Periode,
    PlageDeService,
    PrioriteTache,
    Reservation,
    Secteur,
    StatutFidelite,
    StatutTache,
    TacheNettoyage,
    TypeIncident,
    TypePrestation,
)
from src.donnees import (
    ConversionImpossibleError,
    DepotAgents,
    DepotChambres,
    DepotClients,
    DepotIncidents,
    DepotReservations,
    DepotSecteurs,
    DepotTaches,
    EntiteIntrouvableError,
    JournalDesDecisions,
    creer_fabrique_de_sessions,
    creer_moteur,
    reinitialiser_schema,
    session_de_travail,
)
from src.donnees.conversion import vers_chambre, vers_ligne_de_chambre
from src.donnees.modeles import ChambreEnregistree, DecisionConsignee

ACCES_STANDARD = HeureArrivee(prevue=time(16, 0), contractuelle=time(15, 0))
SEJOUR = Periode(date(2026, 8, 12), date(2026, 8, 15))


@pytest.fixture
def fabrique(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    """Fournit une base isolee, constituee dans un fichier temporaire.

    Un fichier est employe plutot qu'une base en memoire afin de reproduire le
    comportement reel, notamment la verification des cles etrangeres activee a
    la connexion.
    """
    moteur = creer_moteur(f"sqlite:///{tmp_path / 'essai.sqlite3'}")
    reinitialiser_schema(moteur)
    yield creer_fabrique_de_sessions(moteur)
    moteur.dispose()


def chambre(
    numero: str = "407",
    proprete: EtatProprete = EtatProprete.PRETE,
    technique: EtatTechnique = EtatTechnique.OPERATIONNELLE,
    occupation: EtatOccupation = EtatOccupation.LIBRE,
    categorie: Categorie = Categorie.STANDARD,
    equipements: frozenset[Equipement] = frozenset(),
    communicantes: frozenset[NumeroChambre] = frozenset(),
) -> Chambre:
    """Construit une chambre du domaine dont seuls les attributs utiles varient."""
    return Chambre(
        numero=NumeroChambre(numero),
        etage=4,
        capacite=2,
        categorie=categorie,
        equipements=equipements,
        etat_proprete=proprete,
        etat_technique=technique,
        etat_occupation=occupation,
        chambres_communicantes=communicantes,
    )


def reservation(
    identifiant: str = "R-0001",
    client: Client | None = None,
    periode: Periode = SEJOUR,
    exigences: frozenset[Exigence] = frozenset(),
    chambre_affectee: NumeroChambre | None = None,
) -> Reservation:
    """Construit une reservation du domaine avec des valeurs par defaut valides."""
    return Reservation(
        identifiant=IdentifiantReservation(identifiant),
        client=client or Client("C-0001"),
        periode=periode,
        nombre_personnes=2,
        categorie_contractee=Categorie.STANDARD,
        heure_arrivee=ACCES_STANDARD,
        exigences=exigences,
        chambre_affectee=chambre_affectee,
    )


class TestDepotChambres:
    def test_une_chambre_enregistree_est_restituee(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            DepotChambres(session).enregistrer(chambre("407"), "etage_4")

        with session_de_travail(fabrique) as session:
            lue = DepotChambres(session).retrouver(NumeroChambre("407"))
            assert lue.numero == NumeroChambre("407")

    def test_une_chambre_absente_est_signalee(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with (
            session_de_travail(fabrique) as session,
            pytest.raises(EntiteIntrouvableError),
        ):
            DepotChambres(session).retrouver(NumeroChambre("999"))

    def test_le_parc_est_restitue_ordonne(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            DepotChambres(session).enregistrer_plusieurs(
                [(chambre(numero), "etage_4") for numero in ("407", "401", "405")]
            )

        with session_de_travail(fabrique) as session:
            numeros = [str(lue.numero) for lue in DepotChambres(session).lister()]
            assert numeros == ["401", "405", "407"]

    def test_les_chambres_sont_filtrees_par_secteur(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            depot = DepotChambres(session)
            depot.enregistrer_plusieurs(
                [(chambre("401"), "etage_4"), (chambre("501"), "etage_5")]
            )

        with session_de_travail(fabrique) as session:
            assert len(DepotChambres(session).lister_par_secteur("etage_4")) == 1

    def test_le_secteur_d_une_chambre_est_restitue(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            DepotChambres(session).enregistrer(chambre("407"), "etage_4")

        with session_de_travail(fabrique) as session:
            assert DepotChambres(session).secteur_de(NumeroChambre("407")) == "etage_4"

    def test_un_enregistrement_remplace_l_etat_precedent(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            DepotChambres(session).enregistrer(
                chambre("407", proprete=EtatProprete.SALE), "etage_4"
            )

        with session_de_travail(fabrique) as session:
            DepotChambres(session).enregistrer(
                chambre("407", proprete=EtatProprete.PRETE), "etage_4"
            )

        with session_de_travail(fabrique) as session:
            depot = DepotChambres(session)
            assert depot.denombrer() == 1
            assert (
                depot.retrouver(NumeroChambre("407")).etat_proprete
                is EtatProprete.PRETE
            )


class TestDepotReservations:
    def test_une_reservation_enregistre_son_client(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            DepotReservations(session).enregistrer(reservation())

        with session_de_travail(fabrique) as session:
            assert DepotClients(session).retrouver("C-0001").identifiant == "C-0001"

    def test_les_sejours_chevauchants_sont_restitues(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            DepotReservations(session).enregistrer(reservation())

        with session_de_travail(fabrique) as session:
            chevauchant = Periode(date(2026, 8, 14), date(2026, 8, 17))
            assert len(DepotReservations(session).lister_sur_periode(chevauchant)) == 1

    def test_un_sejour_consecutif_n_est_pas_restitue(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            DepotReservations(session).enregistrer(reservation())

        with session_de_travail(fabrique) as session:
            consecutif = Periode(date(2026, 8, 15), date(2026, 8, 18))
            assert DepotReservations(session).lister_sur_periode(consecutif) == []

    def test_les_sejours_affectes_sont_distingues(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            DepotChambres(session).enregistrer(chambre("407"), "etage_4")
            session.flush()
            depot = DepotReservations(session)
            depot.enregistrer(
                reservation("R-0001", chambre_affectee=NumeroChambre("407"))
            )
            depot.enregistrer(reservation("R-0002"))

        with session_de_travail(fabrique) as session:
            affectes = DepotReservations(session).lister_affectees_sur_periode(SEJOUR)
            assert len(affectes) == 1

    def test_les_arrivees_sans_chambre_sont_restituees(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            DepotReservations(session).enregistrer(reservation())

        with session_de_travail(fabrique) as session:
            attendues = DepotReservations(session).lister_a_affecter(date(2026, 8, 12))
            assert len(attendues) == 1


class TestConcordanceDesConventions:
    """Verifie que la requete et le domaine appliquent la meme convention.

    La regle de chevauchement est exprimee deux fois: en Python pour le
    raisonnement, en langage de requetes pour eviter de charger l'integralite
    des sejours. Les deux expressions doivent concorder, sans quoi le systeme
    raisonnerait sur un ensemble incomplet.
    """

    @pytest.mark.parametrize(
        ("arrivee", "depart"),
        [
            (date(2026, 8, 10), date(2026, 8, 13)),
            (date(2026, 8, 13), date(2026, 8, 14)),
            (date(2026, 8, 14), date(2026, 8, 17)),
            (date(2026, 8, 15), date(2026, 8, 18)),
            (date(2026, 8, 9), date(2026, 8, 12)),
            (date(2026, 8, 1), date(2026, 8, 5)),
            (date(2026, 8, 20), date(2026, 8, 25)),
        ],
    )
    def test_la_requete_concorde_avec_le_domaine(
        self, fabrique: sessionmaker[Session], arrivee: date, depart: date
    ) -> None:
        candidate = Periode(arrivee, depart)

        with session_de_travail(fabrique) as session:
            DepotReservations(session).enregistrer(reservation(periode=SEJOUR))

        with session_de_travail(fabrique) as session:
            restituees = DepotReservations(session).lister_sur_periode(candidate)

        assert bool(restituees) is SEJOUR.chevauche(candidate)


class TestDepotIncidents:
    def test_les_incidents_ouverts_sont_ordonnes_par_gravite(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            DepotChambres(session).enregistrer(chambre("407"), "etage_4")
            session.flush()
            depot = DepotIncidents(session)
            depot.enregistrer_plusieurs(
                [
                    Incident(
                        identifiant="I-1",
                        chambre=NumeroChambre("407"),
                        type_incident=TypeIncident.NUISANCE_SONORE,
                        gravite=Gravite.MINEURE,
                        signale_le=datetime(2026, 8, 12, 9, 0),
                    ),
                    Incident(
                        identifiant="I-2",
                        chambre=NumeroChambre("407"),
                        type_incident=TypeIncident.DEGAT_DES_EAUX,
                        gravite=Gravite.CRITIQUE,
                        signale_le=datetime(2026, 8, 12, 10, 0),
                    ),
                ]
            )

        with session_de_travail(fabrique) as session:
            ouverts = DepotIncidents(session).lister_ouverts()
            assert [incident.identifiant for incident in ouverts] == ["I-2", "I-1"]

    def test_un_incident_resolu_n_est_pas_restitue(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            DepotChambres(session).enregistrer(chambre("407"), "etage_4")
            session.flush()
            DepotIncidents(session).enregistrer(
                Incident(
                    identifiant="I-1",
                    chambre=NumeroChambre("407"),
                    type_incident=TypeIncident.PANNE_CLIMATISATION,
                    gravite=Gravite.MODEREE,
                    signale_le=datetime(2026, 8, 12, 9, 0),
                    resolu=True,
                )
            )

        with session_de_travail(fabrique) as session:
            depot = DepotIncidents(session)
            assert depot.lister_ouverts() == []
            assert len(depot.lister_par_chambre(NumeroChambre("407"))) == 1


class TestDepotAgentsEtTaches:
    def test_les_qualifications_sont_restituees(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            DepotAgents(session).enregistrer(
                AgentEtage(
                    identifiant=IdentifiantAgent("A-0001"),
                    secteur=Secteur("etage_4"),
                    plage=PlageDeService(time(8, 0), time(16, 0)),
                ),
                frozenset({"suite"}),
            )

        with session_de_travail(fabrique) as session:
            assert DepotAgents(session).competences() == {"A-0001": ("suite",)}

    def test_seules_les_taches_a_planifier_sont_restituees(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            DepotChambres(session).enregistrer(chambre("407"), "etage_4")
            session.flush()
            depot = DepotTaches(session)
            depot.enregistrer_plusieurs(
                [
                    (
                        TacheNettoyage(
                            identifiant="T-1",
                            chambre=NumeroChambre("407"),
                            prestation=TypePrestation.DEPART,
                            secteur=Secteur("etage_4"),
                            priorite=PrioriteTache.URGENTE,
                        ),
                        frozenset({"suite"}),
                    ),
                    (
                        TacheNettoyage(
                            identifiant="T-2",
                            chambre=NumeroChambre("407"),
                            prestation=TypePrestation.RECOUCHE,
                            secteur=Secteur("etage_4"),
                            statut=StatutTache.ACHEVEE,
                        ),
                        frozenset(),
                    ),
                ]
            )

        with session_de_travail(fabrique) as session:
            depot = DepotTaches(session)
            assert [tache.identifiant for tache in depot.lister_a_planifier()] == ["T-1"]
            assert depot.exigences() == {"T-1": ("suite",)}

    def test_les_secteurs_reserves_sont_remplaces(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            DepotSecteurs(session).declarer_reserves(["presidentielle", "spa"])

        with session_de_travail(fabrique) as session:
            DepotSecteurs(session).declarer_reserves(["presidentielle"])

        with session_de_travail(fabrique) as session:
            assert DepotSecteurs(session).lister_reserves() == ["presidentielle"]


class TestJournalEnAjoutSeul:
    """Verifie que le journal ne permet ni modification ni suppression.

    Une decision consignee doit demeurer consultable telle qu'elle a ete prise:
    c'est ce qui rend un raisonnement passe reconstituable et opposable.
    """

    def test_le_journal_n_expose_aucune_modification(self) -> None:
        interdites = {"modifier", "supprimer", "effacer", "mettre_a_jour", "purger"}
        exposees = {nom for nom in dir(JournalDesDecisions) if not nom.startswith("_")}
        assert not exposees & interdites

    def test_une_decision_consignee_est_restituee(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            JournalDesDecisions(session).consigner(
                service="chambres",
                situation="parc de cinq chambres",
                proposition="c407",
                justification="seule chambre admissible",
                issue="validee",
                valideur="resp-1",
                motif="conforme aux attentes",
            )

        with session_de_travail(fabrique) as session:
            journal = JournalDesDecisions(session)
            assert journal.denombrer() == 1
            consignee = journal.lister()[0]
            assert consignee.issue == "validee"
            assert consignee.motif == "conforme aux attentes"

    def test_les_decisions_sont_filtrees_par_service(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            journal = JournalDesDecisions(session)
            for service in ("chambres", "housekeeping", "chambres"):
                journal.consigner(
                    service=service,
                    situation="",
                    proposition="",
                    justification="",
                    issue="validee",
                    valideur="resp-1",
                )

        with session_de_travail(fabrique) as session:
            journal = JournalDesDecisions(session)
            assert len(journal.lister_par_service("chambres")) == 2
            assert len(journal.lister_par_service("housekeeping")) == 1

    def test_les_decisions_sont_restituees_de_la_plus_recente(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            journal = JournalDesDecisions(session)
            for rang, heure in enumerate((9, 14, 11), start=1):
                journal.consigner(
                    service="chambres",
                    situation="",
                    proposition=f"c{rang}",
                    justification="",
                    issue="validee",
                    valideur="resp-1",
                    horodatage=datetime(2026, 8, 12, heure, 0),
                )

        with session_de_travail(fabrique) as session:
            propositions = [
                consignee.proposition
                for consignee in JournalDesDecisions(session).lister()
            ]
            assert propositions == ["c2", "c3", "c1"]


class TestConversionDefaillante:
    def test_une_valeur_inconnue_est_signalee(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            DepotChambres(session).enregistrer(chambre("407"), "etage_4")

        with session_de_travail(fabrique) as session:
            ligne = session.get(ChambreEnregistree, "407")
            assert ligne is not None
            ligne.etat_proprete = "impeccable"
            session.flush()
            with pytest.raises(ConversionImpossibleError):
                vers_chambre(ligne)


categories = st.sampled_from(list(Categorie))
etats_proprete = st.sampled_from(list(EtatProprete))
etats_technique = st.sampled_from(list(EtatTechnique))
etats_occupation = st.sampled_from(list(EtatOccupation))
equipements = st.frozensets(st.sampled_from(list(Equipement)), max_size=5)


@st.composite
def chambres_quelconques(tirage: st.DrawFn) -> Chambre:
    """Engendre une chambre dont tous les attributs varient librement."""
    return Chambre(
        numero=NumeroChambre(f"{tirage(st.integers(min_value=1, max_value=999)):03d}"),
        etage=tirage(st.integers(min_value=0, max_value=20)),
        capacite=tirage(st.integers(min_value=1, max_value=8)),
        categorie=tirage(categories),
        equipements=tirage(equipements),
        etat_proprete=tirage(etats_proprete),
        etat_technique=tirage(etats_technique),
        etat_occupation=tirage(etats_occupation),
    )


@pytest.mark.lent
class TestAllerRetour:
    """Verifie que la conversion ne deforme aucune entite.

    La propriete ne porte pas sur un cas particulier: quelle que soit l'entite
    engendree, sa conversion en ligne puis sa reconversion restituent une
    entite identique a l'originale.
    """

    @settings(max_examples=150, deadline=None)
    @given(originale=chambres_quelconques())
    def test_une_chambre_traverse_la_conversion_sans_alteration(
        self, originale: Chambre
    ) -> None:
        restituee = vers_chambre(vers_ligne_de_chambre(originale, "etage_4"))

        assert restituee.numero == originale.numero
        assert restituee.etage == originale.etage
        assert restituee.capacite == originale.capacite
        assert restituee.categorie is originale.categorie
        assert restituee.equipements == originale.equipements
        assert restituee.etat_proprete is originale.etat_proprete
        assert restituee.etat_technique is originale.etat_technique
        assert restituee.etat_occupation is originale.etat_occupation

    @settings(
        max_examples=40,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(originale=chambres_quelconques())
    def test_une_chambre_traverse_la_base_sans_alteration(
        self, fabrique: sessionmaker[Session], originale: Chambre
    ) -> None:
        with session_de_travail(fabrique) as session:
            DepotChambres(session).enregistrer(originale, "etage_4")

        with session_de_travail(fabrique) as session:
            restituee = DepotChambres(session).retrouver(originale.numero)

        assert restituee.categorie is originale.categorie
        assert restituee.equipements == originale.equipements
        assert restituee.etat_proprete is originale.etat_proprete
        assert restituee.etat_technique is originale.etat_technique
        assert restituee.etat_occupation is originale.etat_occupation
        assert restituee.capacite == originale.capacite


class TestReservationsPersistees:
    def test_une_reservation_traverse_la_base_sans_alteration(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        originale = reservation(
            client=Client(
                "C-0009",
                statut_fidelite=StatutFidelite.PLATINE,
                besoins_permanents=frozenset({Equipement.ACCES_PMR}),
            ),
            exigences=frozenset(
                {
                    Exigence(Equipement.LIT_KING, obligatoire=True),
                    Exigence(Equipement.BALCON, obligatoire=False),
                }
            ),
        )

        with session_de_travail(fabrique) as session:
            DepotReservations(session).enregistrer(originale)

        with session_de_travail(fabrique) as session:
            restituee = DepotReservations(session).retrouver("R-0001")

        assert restituee.periode == originale.periode
        assert restituee.exigences == originale.exigences
        assert restituee.exigences_obligatoires == originale.exigences_obligatoires
        assert restituee.client.statut_fidelite is StatutFidelite.PLATINE
        assert restituee.client.besoins_permanents == frozenset({Equipement.ACCES_PMR})
        assert restituee.heure_arrivee == originale.heure_arrivee


class TestIntegriteReferentielle:
    def test_une_reservation_vers_une_chambre_absente_est_refusee(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with pytest.raises(IntegrityError), session_de_travail(fabrique) as session:
            DepotReservations(session).enregistrer(
                reservation(chambre_affectee=NumeroChambre("999"))
            )

    def test_le_journal_conserve_ses_lignes(
        self, fabrique: sessionmaker[Session]
    ) -> None:
        with session_de_travail(fabrique) as session:
            JournalDesDecisions(session).consigner(
                service="chambres",
                situation="",
                proposition="c407",
                justification="",
                issue="validee",
                valideur="resp-1",
            )

        with session_de_travail(fabrique) as session:
            assert session.query(DecisionConsignee).count() == 1
