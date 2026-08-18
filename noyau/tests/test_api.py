"""Tests de l'interface de programmation.

Les tests portent sur le contrat public: forme des echanges, codes de reponse
et traduction des defaillances. La logique metier, verifiee en amont, n'est pas
rejouee ici.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from src.api import application

RESERVATION = {
    "identifiant": "R-4471",
    "client": "C-001",
    "arrivee": "2026-08-12",
    "depart": "2026-08-15",
    "nombre_personnes": 2,
    "categorie_contractee": 1,
    "exigences": [
        {"equipement": "lit_double", "obligatoire": True},
        {"equipement": "balcon", "obligatoire": False},
    ],
}


def chambre(numero: str, **surcharges: Any) -> dict[str, Any]:
    """Construit une chambre entrante dont seuls les attributs utiles varient."""
    defauts: dict[str, Any] = {
        "numero": numero,
        "etage": 4,
        "capacite": 2,
        "categorie": 1,
        "equipements": ["lit_double"],
    }
    return defauts | surcharges


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    """Fournit un client de test partage par l'ensemble des cas."""
    with TestClient(application) as session:
        yield session


class TestDisponibiliteDuService:
    def test_le_service_signale_sa_disponibilite(self, client: TestClient) -> None:
        reponse = client.get("/sante")
        assert reponse.status_code == 200
        assert reponse.json() == {"etat": "disponible"}

    def test_la_documentation_est_engendree(self, client: TestClient) -> None:
        schema = client.get("/openapi.json").json()
        assert "/affectations" in schema["paths"]
        assert schema["info"]["title"]


class TestRecommandation:
    def test_une_situation_valide_produit_une_recommandation(
        self, client: TestClient
    ) -> None:
        reponse = client.post(
            "/affectations",
            json={"parc": [chambre("407")], "reservation": RESERVATION},
        )
        assert reponse.status_code == 200
        contenu = reponse.json()
        assert contenu["a_conclu"] is True
        assert contenu["chambre_proposee"] == "c407"

    def test_la_justification_accompagne_la_recommandation(
        self, client: TestClient
    ) -> None:
        reponse = client.post(
            "/affectations",
            json={"parc": [chambre("407")], "reservation": RESERVATION},
        )
        assert "c407" in reponse.json()["justification"]

    def test_les_options_ecartees_exposent_leurs_motifs(
        self, client: TestClient
    ) -> None:
        parc = [
            chambre("312", etat_technique="bloquee"),
            chambre("405", etat_proprete="a_controler"),
            chambre("407"),
        ]
        contenu = client.post(
            "/affectations", json={"parc": parc, "reservation": RESERVATION}
        ).json()

        par_chambre = {
            option["chambre"]: option for option in contenu["options_ecartees"]
        }
        assert set(par_chambre) == {"c312", "c405"}
        assert par_chambre["c312"]["motifs"][0]["code"] == "bloquee"
        assert par_chambre["c405"]["formulations"]

    def test_le_detail_d_un_motif_est_expose(self, client: TestClient) -> None:
        parc = [chambre("401", equipements=["lit_simple"]), chambre("407")]
        contenu = client.post(
            "/affectations", json={"parc": parc, "reservation": RESERVATION}
        ).json()
        motifs = [
            motif
            for option in contenu["options_ecartees"]
            for motif in option["motifs"]
            if motif["code"] == "equipement_absent"
        ]
        assert motifs
        assert motifs[0]["detail"] == "lit_double"

    def test_les_contreparties_sont_exposees(self, client: TestClient) -> None:
        contenu = client.post(
            "/affectations",
            json={"parc": [chambre("407")], "reservation": RESERVATION},
        ).json()
        assert contenu["contreparties"]
        assert contenu["contreparties"][0]["code"] == "souhait_non_satisfait"
        assert contenu["contreparties"][0]["formulation"]

    def test_l_absence_de_solution_conserve_les_motifs(self, client: TestClient) -> None:
        parc = [
            chambre("401", etat_technique="bloquee"),
            chambre("402", etat_proprete="sale"),
        ]
        contenu = client.post(
            "/affectations", json={"parc": parc, "reservation": RESERVATION}
        ).json()
        assert contenu["a_conclu"] is False
        assert contenu["chambre_proposee"] is None
        assert len(contenu["options_ecartees"]) == 2

    def test_le_denombrement_des_options_est_expose(self, client: TestClient) -> None:
        parc = [chambre("401"), chambre("402", etat_technique="bloquee")]
        contenu = client.post(
            "/affectations", json={"parc": parc, "reservation": RESERVATION}
        ).json()
        assert contenu["chambres_examinees"] == 2
        assert contenu["chambres_admissibles"] == ["c401"]

    def test_la_ponderation_transmise_influe_sur_le_choix(
        self, client: TestClient
    ) -> None:
        parc = [
            chambre("401"),
            chambre("501", categorie=4, equipements=["lit_double", "balcon"]),
        ]
        base = {"souhait_non_satisfait": 3, "hors_secteur": 2, "etage_non_souhaite": 1}

        couteux = client.post(
            "/affectations",
            json={
                "parc": parc,
                "reservation": RESERVATION,
                "poids": base | {"surclassement": 100},
            },
        ).json()
        gratuit = client.post(
            "/affectations",
            json={
                "parc": parc,
                "reservation": RESERVATION,
                "poids": base | {"surclassement": 0},
            },
        ).json()

        assert couteux["chambre_proposee"] == "c401"
        assert gratuit["chambre_proposee"] == "c501"

    def test_les_occupations_existantes_sont_prises_en_compte(
        self, client: TestClient
    ) -> None:
        occupante = RESERVATION | {
            "identifiant": "R-1000",
            "arrivee": "2026-08-13",
            "depart": "2026-08-16",
            "chambre_affectee": "401",
        }
        contenu = client.post(
            "/affectations",
            json={
                "parc": [chambre("401"), chambre("407")],
                "reservation": RESERVATION,
                "occupations": [occupante],
            },
        ).json()
        assert contenu["chambre_proposee"] == "c407"


class TestValidationDesEchanges:
    def test_un_parc_vide_est_refuse(self, client: TestClient) -> None:
        reponse = client.post(
            "/affectations", json={"parc": [], "reservation": RESERVATION}
        )
        assert reponse.status_code == 422

    def test_un_parc_comportant_des_doublons_est_refuse(
        self, client: TestClient
    ) -> None:
        reponse = client.post(
            "/affectations",
            json={"parc": [chambre("407"), chambre("407")], "reservation": RESERVATION},
        )
        assert reponse.status_code == 422
        assert reponse.json()["detail"]["code"] == "demande_invalide"

    def test_des_dates_inversees_sont_refusees(self, client: TestClient) -> None:
        reponse = client.post(
            "/affectations",
            json={
                "parc": [chambre("407")],
                "reservation": RESERVATION | {"depart": "2026-08-10"},
            },
        )
        assert reponse.status_code == 422

    def test_une_capacite_nulle_est_refusee(self, client: TestClient) -> None:
        reponse = client.post(
            "/affectations",
            json={"parc": [chambre("407", capacite=0)], "reservation": RESERVATION},
        )
        assert reponse.status_code == 422

    def test_un_etage_negatif_est_refuse(self, client: TestClient) -> None:
        reponse = client.post(
            "/affectations",
            json={"parc": [chambre("407", etage=-1)], "reservation": RESERVATION},
        )
        assert reponse.status_code == 422

    def test_un_equipement_inconnu_est_refuse(self, client: TestClient) -> None:
        reponse = client.post(
            "/affectations",
            json={
                "parc": [chambre("407", equipements=["jacuzzi_prive"])],
                "reservation": RESERVATION,
            },
        )
        assert reponse.status_code == 422

    def test_un_etat_inconnu_est_refuse(self, client: TestClient) -> None:
        reponse = client.post(
            "/affectations",
            json={
                "parc": [chambre("407", etat_proprete="impeccable")],
                "reservation": RESERVATION,
            },
        )
        assert reponse.status_code == 422

    def test_un_numero_vide_est_refuse(self, client: TestClient) -> None:
        reponse = client.post(
            "/affectations",
            json={"parc": [chambre("")], "reservation": RESERVATION},
        )
        assert reponse.status_code == 422

    def test_un_temps_maximal_hors_bornes_est_refuse(self, client: TestClient) -> None:
        reponse = client.post(
            "/affectations",
            json={
                "parc": [chambre("407")],
                "reservation": RESERVATION,
                "temps_maximal": 0,
            },
        )
        assert reponse.status_code == 422

    def test_une_reservation_absente_est_refusee(self, client: TestClient) -> None:
        reponse = client.post("/affectations", json={"parc": [chambre("407")]})
        assert reponse.status_code == 422


class TestPropagationDesDefaillances:
    def test_une_defaillance_du_raisonnement_est_signalee(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.symbolique.regles import MoteurIndisponibleError

        def defaillir(*arguments: object, **nommes: object) -> None:
            raise MoteurIndisponibleError("moteur simule indisponible")

        monkeypatch.setattr("src.orchestration.affectation.resoudre", defaillir)
        reponse = client.post(
            "/affectations",
            json={"parc": [chambre("407")], "reservation": RESERVATION},
        )
        assert reponse.status_code == 500
        assert reponse.json()["detail"]["code"] == "raisonnement_indisponible"

    def test_une_justification_incomplete_est_signalee(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.gouvernance import GabaritIntrouvableError

        def defaillir(*arguments: object, **nommes: object) -> None:
            raise GabaritIntrouvableError("motif sans formulation")

        monkeypatch.setattr(
            "src.gouvernance.explication.GenerateurParGabarits.justifier", defaillir
        )
        reponse = client.post(
            "/affectations",
            json={"parc": [chambre("407")], "reservation": RESERVATION},
        )
        assert reponse.status_code == 500
        assert reponse.json()["detail"]["code"] == "justification_incomplete"
