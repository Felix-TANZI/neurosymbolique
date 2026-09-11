"""Verification de la production de plusieurs options comparees.

Une decision critique suppose que le responsable arbitre. Lui soumettre
plusieurs options n'a de sens que si celles-ci sont reellement distinctes,
ordonnees par un critere etabli, et accompagnees de ce qui les separe.
"""

from datetime import date, time, timedelta
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
    HeureArrivee,
    IdentifiantReservation,
    NatureDeLaPreference,
    NumeroChambre,
    Periode,
    Preference,
    Preferences,
    Reservation,
    StatutFidelite,
)
from src.orchestration import creer_cas_usage
from src.orchestration.affectation import demande_depuis
from src.orchestration.options import Eventail, Option, ProposerDesOptions

RACINE = Path(__file__).resolve().parents[2] / "connaissances"


def _chambre(numero: str, categorie: Categorie = Categorie.STANDARD) -> Chambre:
    """Constitue une chambre libre, prete et operationnelle."""
    return Chambre(
        numero=NumeroChambre(numero),
        etage=int(numero[0]),
        capacite=2,
        categorie=categorie,
        equipements=frozenset({Equipement.LIT_DOUBLE, Equipement.CLIMATISATION}),
        etat_proprete=EtatProprete.PRETE,
        etat_technique=EtatTechnique.OPERATIONNELLE,
        etat_occupation=EtatOccupation.LIBRE,
        chambres_communicantes=frozenset(),
    )


def _sejour(reference: str = "R-00001") -> Reservation:
    """Constitue un sejour a venir, sans exigence particuliere."""
    arrivee = date(2026, 8, 20)
    return Reservation(
        identifiant=IdentifiantReservation(reference),
        client=Client(
            identifiant="C-0001",
            statut_fidelite=StatutFidelite.AUCUN,
            besoins_permanents=frozenset(),
        ),
        periode=Periode(arrivee, arrivee + timedelta(days=2)),
        nombre_personnes=2,
        categorie_contractee=Categorie.STANDARD,
        heure_arrivee=HeureArrivee(prevue=time(14, 0), contractuelle=time(15, 0)),
        exigences=frozenset(),
        chambre_affectee=None,
    )


@pytest.fixture(scope="module")
def producteur() -> ProposerDesOptions:
    """Constitue le producteur d'options une fois pour le module."""
    return ProposerDesOptions(creer_cas_usage(RACINE))


class TestProductionDesOptions:
    """Verifie que plusieurs options distinctes sont produites."""

    def test_trois_options_sont_produites_quand_le_parc_le_permet(
        self, producteur: ProposerDesOptions
    ) -> None:
        parc = [_chambre(f"1{rang:02d}") for rang in range(1, 6)]
        eventail = producteur.executer(
            demande_depuis(parc, _sejour(), jour=date(2026, 8, 12)), 3, 10.0
        )
        assert len(eventail.options) == 3

    def test_les_options_sont_toutes_distinctes(
        self, producteur: ProposerDesOptions
    ) -> None:
        """Une option repetee ne constituerait aucun choix."""
        parc = [_chambre(f"1{rang:02d}") for rang in range(1, 6)]
        eventail = producteur.executer(
            demande_depuis(parc, _sejour(), jour=date(2026, 8, 12)), 3, 10.0
        )
        chambres = [option.chambre for option in eventail.options]
        assert len(set(chambres)) == len(chambres)

    def test_les_rangs_se_suivent(self, producteur: ProposerDesOptions) -> None:
        parc = [_chambre(f"1{rang:02d}") for rang in range(1, 6)]
        eventail = producteur.executer(
            demande_depuis(parc, _sejour(), jour=date(2026, 8, 12)), 3, 10.0
        )
        assert [option.rang for option in eventail.options] == [1, 2, 3]

    def test_les_couts_ne_decroissent_pas(
        self, producteur: ProposerDesOptions
    ) -> None:
        """Chaque option est l'optimum de ce qui demeurait disponible."""
        parc = [_chambre(f"1{rang:02d}") for rang in range(1, 6)]
        parc.append(_chambre("205", Categorie.SUITE))
        eventail = producteur.executer(
            demande_depuis(parc, _sejour(), jour=date(2026, 8, 12)), 3, 10.0
        )
        couts = [option.cout for option in eventail.options]
        assert couts == sorted(couts)

    def test_un_parc_restreint_ne_produit_qu_une_option(
        self, producteur: ProposerDesOptions
    ) -> None:
        eventail = producteur.executer(
            demande_depuis([_chambre("101")], _sejour(), jour=date(2026, 8, 12)),
            3,
            10.0,
        )
        assert len(eventail.options) == 1
        assert not eventail.offre_un_choix

    def test_un_parc_vide_est_refuse(self) -> None:
        """L'invariant releve de la demande, non de la production d'options."""
        from src.orchestration.affectation import DemandeInvalideError

        with pytest.raises(DemandeInvalideError, match="aucune chambre"):
            demande_depuis([], _sejour(), jour=date(2026, 8, 12))


class TestEquivalenceDesOptions:
    """Verifie que l'absence de critere departageant est signalee."""

    def test_des_options_de_meme_cout_sont_declarees_equivalentes(
        self, producteur: ProposerDesOptions
    ) -> None:
        """Un classement sans fondement laisserait croire a une preference."""
        parc = [_chambre(f"1{rang:02d}") for rang in range(1, 6)]
        eventail = producteur.executer(
            demande_depuis(parc, _sejour(), jour=date(2026, 8, 12)), 3, 10.0
        )
        assert eventail.sont_equivalentes
        assert "Aucun critere" in eventail.resumer()

    def test_une_option_unique_n_est_pas_equivalente(self) -> None:
        eventail = Eventail(
            options=(Option(rang=1, chambre="c101", cout=0, justification=""),)
        )
        assert not eventail.sont_equivalentes


class TestEffetDesPreferences:
    """Verifie qu'une preference exprimee reordonne les options."""

    def test_une_proximite_fait_remonter_la_chambre_voisine(
        self, producteur: ProposerDesOptions
    ) -> None:
        """C'est le point ou une formulation acquiert une portee sur le choix."""
        parc = [_chambre("101"), _chambre("105"), _chambre("110")]
        preferences = Preferences().avec(
            Preference(
                nature=NatureDeLaPreference.PROXIMITE.value, reference="106"
            )
        )

        eventail = producteur.executer(
            demande_depuis(
                parc,
                _sejour(),
                jour=date(2026, 8, 12),
                preferences=preferences,
            ),
            3,
            10.0,
        )

        assert eventail.preferee is not None
        assert eventail.preferee.chambre == "c105"

    def test_la_preference_departage_des_options_autrement_equivalentes(
        self, producteur: ProposerDesOptions
    ) -> None:
        """Une reference presente au parc permet d'ordonner; une reference
        absente laisse les options equivalentes, faute de mesure possible."""
        parc = [_chambre("101"), _chambre("105"), _chambre("110")]
        sans = producteur.executer(
            demande_depuis(parc, _sejour(), jour=date(2026, 8, 12)), 3, 10.0
        )
        avec = producteur.executer(
            demande_depuis(
                parc,
                _sejour(),
                jour=date(2026, 8, 12),
                preferences=Preferences().avec(
                    Preference(
                        nature=NatureDeLaPreference.PROXIMITE.value,
                        reference="102",
                    )
                ),
            ),
            3,
            10.0,
        )

        assert sans.sont_equivalentes
        assert not avec.sont_equivalentes
        assert avec.preferee is not None
        assert avec.preferee.chambre == "c101"

    def test_une_reference_hors_de_portee_laisse_les_options_equivalentes(
        self, producteur: ProposerDesOptions
    ) -> None:
        """Au-dela du seuil retenu, la proximite ne distingue plus rien.

        Les chambres concernees subissent alors une penalite identique, ce qui
        les laisse equivalentes: le systeme n'invente pas un ordre la ou sa
        mesure ne s'applique plus.
        """
        parc = [_chambre("101"), _chambre("115"), _chambre("116")]
        eventail = producteur.executer(
            demande_depuis(
                parc,
                _sejour(),
                jour=date(2026, 8, 12),
                preferences=Preferences().avec(
                    Preference(
                        nature=NatureDeLaPreference.PROXIMITE.value,
                        reference="101",
                    )
                ),
            ),
            3,
            10.0,
        )
        assert eventail.sont_equivalentes
