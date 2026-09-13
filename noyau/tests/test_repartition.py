"""Verification de la repartition d'une charge et de la lecture des quantites.

La repartition se distingue des autres traitements en ce que ses donnees
proviennent de l'enonce et non de l'etablissement. Deux invariants en decoulent:
les quantites doivent etre correctement qualifiees, et la repartition doit
minimiser l'instant ou le dernier agent termine.
"""

from datetime import timedelta

import pytest
from src.neuronal.inference import EntiteExtraite, Interpretation
from src.neuronal.quantites_lues import relever_les_quantites
from src.orchestration.repartition import (
    RepartirUneCharge,
    RepartitionImpossibleError,
)


def _interpretation(enonce: str, quantites: list[tuple[str, int, int]]) -> Interpretation:
    """Constitue une interpretation portant des quantites extraites."""
    return Interpretation(
        enonce=enonce,
        intention="repartir_charge",
        confiance_d_intention=0.9,
        entites=tuple(
            EntiteExtraite(
                type_d_entite="quantite",
                valeur=valeur,
                confiance=0.95,
                debut=debut,
                fin=fin,
            )
            for valeur, debut, fin in quantites
        ),
    )


class TestRepartition:
    """Verifie l'equilibrage et la duree etablie."""

    def test_une_division_exacte_donne_des_parts_egales(self) -> None:
        proposee = RepartirUneCharge().executer(12, 3)
        assert [part.chambres for part in proposee.parts] == [4, 4, 4]
        assert proposee.est_equilibree

    def test_le_reste_est_distribue_une_unite_par_agent(self) -> None:
        """Concentrer le reste sur un agent retarderait l'achevement."""
        proposee = RepartirUneCharge().executer(13, 3)
        assert [part.chambres for part in proposee.parts] == [5, 4, 4]
        assert proposee.ecart_maximal == 1

    def test_l_ecart_n_excede_jamais_une_chambre(self) -> None:
        for chambres in range(1, 60):
            for agents in range(1, 8):
                proposee = RepartirUneCharge().executer(chambres, agents)
                assert proposee.ecart_maximal <= 1

    def test_la_duree_est_celle_du_dernier_agent(self) -> None:
        """C'est l'instant ou le dernier termine qui acheve le service."""
        proposee = RepartirUneCharge().executer(13, 3)
        assert proposee.duree_totale == timedelta(minutes=150)

    def test_plus_d_agents_que_de_chambres_laisse_des_parts_vides(self) -> None:
        proposee = RepartirUneCharge().executer(2, 5)
        comptes = [part.chambres for part in proposee.parts]
        assert comptes == [1, 1, 0, 0, 0]

    def test_la_duree_par_chambre_est_configurable(self) -> None:
        proposee = RepartirUneCharge().executer(
            4, 2, duree_par_chambre=timedelta(minutes=45)
        )
        assert proposee.duree_totale == timedelta(minutes=90)


class TestEcheance:
    """Verifie l'appreciation d'une contrainte horaire."""

    def test_une_echeance_tenue_est_signalee(self) -> None:
        proposee = RepartirUneCharge().executer(
            6, 3, echeance=timedelta(hours=2)
        )
        assert any("tenue" in enonce for enonce in proposee.justification)

    def test_une_echeance_depassee_indique_l_effectif_requis(self) -> None:
        """Constater un depassement sans levier laisserait sans prise."""
        proposee = RepartirUneCharge().executer(
            12, 2, echeance=timedelta(hours=1)
        )
        enonces = " ".join(proposee.justification)
        assert "depassee" in enonces
        assert "agents seraient necessaires" in enonces


class TestDemandesInexploitables:
    """Verifie le refus des demandes qui ne decrivent aucune situation."""

    def test_un_effectif_nul_est_refuse(self) -> None:
        with pytest.raises(RepartitionImpossibleError, match="aucun agent"):
            RepartirUneCharge().executer(12, 0)

    def test_une_charge_nulle_est_refusee(self) -> None:
        with pytest.raises(RepartitionImpossibleError, match="aucune chambre"):
            RepartirUneCharge().executer(0, 3)

    def test_un_effectif_demesure_est_refuse(self) -> None:
        """Un nombre invraisemblable revele une lecture erronee de l'enonce."""
        with pytest.raises(RepartitionImpossibleError, match="invraisemblable"):
            RepartirUneCharge().executer(12, 500)

    def test_une_charge_demesuree_est_refusee(self) -> None:
        with pytest.raises(RepartitionImpossibleError, match="invraisemblable"):
            RepartirUneCharge().executer(5000, 3)


class TestLectureDesQuantites:
    """Verifie la qualification des nombres releves dans un enonce."""

    def test_l_ordre_naturel_est_lu(self) -> None:
        lue = relever_les_quantites(
            _interpretation(
                "j ai 12 chambres a faire et 3 agents",
                [("12", 2, 4), ("3", 8, 9)],
            )
        )
        assert lue.charge == 12
        assert lue.effectif == 3

    def test_l_ordre_inverse_est_lu_de_meme(self) -> None:
        """Aucune convention d'ordre n'est retenue: le qualifiant tranche."""
        lue = relever_les_quantites(
            _interpretation(
                "j ai 3 agents pour 12 chambres",
                [("3", 2, 3), ("12", 5, 7)],
            )
        )
        assert lue.charge == 12
        assert lue.effectif == 3

    def test_des_quantites_sans_qualifiant_demeurent_indeterminees(self) -> None:
        """Deviner produirait une repartition fondee sur une lecture erronee."""
        lue = relever_les_quantites(
            _interpretation("12 et 3 comment repartir", [("12", 0, 2), ("3", 3, 4)])
        )
        assert not lue.est_exploitable
        assert len(lue.indeterminees) == 2

    def test_le_manque_est_designe(self) -> None:
        lue = relever_les_quantites(
            _interpretation("j ai 3 agents", [("3", 2, 3)])
        )
        assert lue.effectif == 3
        assert lue.charge is None
        assert "chambres" in lue.manque

    def test_les_nombres_en_lettres_sont_convertis(self) -> None:
        lue = relever_les_quantites(
            _interpretation(
                "j ai douze chambres et trois agents",
                [("douze", 2, 3), ("trois", 5, 6)],
            )
        )
        assert lue.charge == 12
        assert lue.effectif == 3

    def test_un_qualifiant_eloigne_n_est_pas_retenu(self) -> None:
        """Etendre la portee attribuerait a une quantite le terme de la suivante."""
        lue = relever_les_quantites(
            _interpretation(
                "12 pour le service du jour avec 3 agents",
                [("12", 0, 2), ("3", 8, 9)],
            )
        )
        assert lue.charge is None
        assert lue.effectif == 3
