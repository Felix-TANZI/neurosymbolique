"""Verification des preferences exprimees et de leur effet sur la decision.

Les preferences constituent la charniere entre la couche neuronale et la
couche symbolique: une formulation en langue naturelle y acquiert une portee
sur le raisonnement. Une preference sans effet observable romprait cette
chaine sans qu'aucune mesure ne le signale.
"""


import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from src.domaine import (
    NatureDeLaPreference,
    NumeroChambre,
    Preference,
    Preferences,
    distance_entre,
    etage_de,
    sont_voisines,
)


class TestDistance:
    """Verifie le calcul de proximite entre chambres."""

    def test_deux_chambres_consecutives_sont_voisines(self) -> None:
        assert sont_voisines(NumeroChambre("405"), NumeroChambre("406"))

    def test_la_distance_compte_les_portes(self) -> None:
        assert distance_entre(NumeroChambre("405"), NumeroChambre("412")) == 7

    def test_la_distance_est_symetrique(self) -> None:
        aller = distance_entre(NumeroChambre("405"), NumeroChambre("412"))
        retour = distance_entre(NumeroChambre("412"), NumeroChambre("405"))
        assert aller == retour

    def test_la_distance_entre_etages_demeure_indefinie(self) -> None:
        """Aucune proximite ne s'etablit sans plan de l'etablissement."""
        assert distance_entre(NumeroChambre("405"), NumeroChambre("305")) is None

    def test_une_chambre_est_a_distance_nulle_d_elle_meme(self) -> None:
        assert distance_entre(NumeroChambre("405"), NumeroChambre("405")) == 0

    def test_l_etage_se_deduit_de_la_numerotation(self) -> None:
        assert etage_de(NumeroChambre("405")) == 4
        assert etage_de(NumeroChambre("1205")) == 12

    @settings(max_examples=100, deadline=None)
    @given(
        etage=st.integers(min_value=1, max_value=9),
        premier=st.integers(min_value=1, max_value=99),
        second=st.integers(min_value=1, max_value=99),
    )
    def test_la_distance_ne_depasse_jamais_l_ecart_des_rangs(
        self, etage: int, premier: int, second: int
    ) -> None:
        gauche = NumeroChambre(f"{etage}{premier:02d}")
        droite = NumeroChambre(f"{etage}{second:02d}")
        distance = distance_entre(gauche, droite)
        assert distance == abs(premier - second)


class TestPreference:
    """Verifie les invariants d'une preference exprimee."""

    def test_une_intensite_nulle_est_refusee(self) -> None:
        with pytest.raises(ValueError, match="intensite"):
            Preference(nature=NatureDeLaPreference.SURCLASSEMENT.value, intensite=0)

    def test_une_proximite_sans_reference_est_refusee(self) -> None:
        """Une proximite sans reference ne designe rien et n'ordonne rien."""
        with pytest.raises(ValueError, match="reference"):
            Preference(nature=NatureDeLaPreference.PROXIMITE.value)

    def test_un_surclassement_se_passe_de_reference(self) -> None:
        preference = Preference(nature=NatureDeLaPreference.SURCLASSEMENT.value)
        assert preference.reference == ""


class TestPreferences:
    """Verifie l'assemblage des preferences."""

    def test_un_ensemble_vide_est_faux(self) -> None:
        assert not Preferences()

    def test_l_ajout_restitue_un_nouvel_ensemble(self) -> None:
        """L'immuabilite interdit qu'un ajout modifie l'ensemble initial."""
        initial = Preferences()
        augmente = initial.avec(
            Preference(
                nature=NatureDeLaPreference.PROXIMITE.value, reference="405"
            )
        )
        assert len(initial) == 0
        assert len(augmente) == 1

    def test_le_filtrage_par_nature_retient_les_bonnes(self) -> None:
        ensemble = (
            Preferences()
            .avec(
                Preference(
                    nature=NatureDeLaPreference.PROXIMITE.value, reference="405"
                )
            )
            .avec(
                Preference(
                    nature=NatureDeLaPreference.ELOIGNEMENT.value, reference="312"
                )
            )
        )
        retenues = ensemble.de_nature(NatureDeLaPreference.PROXIMITE.value)
        assert len(retenues) == 1
        assert retenues[0].reference == "405"
