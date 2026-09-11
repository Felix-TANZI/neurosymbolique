"""Verification du journal des decisions.

Le journal etablit la tracabilite d'une decision critique: il doit en
conserver le fondement sans jamais le modifier. Il recueille par ailleurs les
ecarts entre la proposition et la decision retenue, dont l'examen ulterieur
peut eclairer les regles ou le modele.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session
from src.donnees import (
    creer_fabrique_de_sessions,
    creer_moteur,
    initialiser_schema,
)
from src.orchestration.journal import (
    ConsignerUneDecision,
    ConsulterLeJournal,
    DecisionAConsigner,
    SuiteDonnee,
)


@pytest.fixture
def session() -> Iterator[Session]:
    """Constitue une base en memoire, propre a chaque test."""
    moteur = creer_moteur("sqlite:///:memory:")
    initialiser_schema(moteur)
    fabrique = creer_fabrique_de_sessions(moteur)
    ouverte = fabrique()
    try:
        yield ouverte
    finally:
        ouverte.close()
        moteur.dispose()


def _decision(
    issue: str = SuiteDonnee.VALIDEE.value, motif: str = ""
) -> DecisionAConsigner:
    """Constitue une decision a consigner."""
    return DecisionAConsigner(
        service="chambres",
        situation="il y a une fuite dans la 319",
        proposition="R-00017 en c406",
        justification="La chambre c406 satisfait l'ensemble des contraintes.",
        issue=issue,
        valideur="essai",
        motif=motif,
    )


class TestInvariantsDeLaDecision:
    """Verifie ce qu'une decision doit comporter pour etre consignable."""

    def test_une_issue_inconnue_est_refusee(self) -> None:
        with pytest.raises(ValueError, match="issue"):
            _decision(issue="approuvee_partiellement")

    def test_une_correction_sans_motif_est_refusee(self) -> None:
        """Une correction dont la decision retenue demeure inconnue n'apprend rien."""
        with pytest.raises(ValueError, match="correction"):
            _decision(issue=SuiteDonnee.CORRIGEE.value)

    def test_une_correction_avec_motif_est_acceptee(self) -> None:
        decision = _decision(
            issue=SuiteDonnee.CORRIGEE.value, motif="R-00017 en c519"
        )
        assert decision.motif == "R-00017 en c519"

    def test_une_validation_marque_l_accord(self) -> None:
        assert not _decision().marque_un_ecart

    def test_un_refus_marque_un_ecart(self) -> None:
        """Un refus designe une divergence entre raisonnement et jugement."""
        assert _decision(issue=SuiteDonnee.REFUSEE.value).marque_un_ecart

    def test_une_correction_marque_un_ecart(self) -> None:
        assert _decision(
            issue=SuiteDonnee.CORRIGEE.value, motif="autre chambre"
        ).marque_un_ecart

    def test_un_report_ne_marque_aucun_ecart(self) -> None:
        """Differer n'est pas contester: aucune divergence n'est etablie."""
        assert not _decision(issue=SuiteDonnee.DIFFEREE.value).marque_un_ecart


class TestConsignation:
    """Verifie l'inscription et la restitution des decisions."""

    def test_une_decision_consignee_est_restituee(self, session: Session) -> None:
        ConsignerUneDecision().executer(session, _decision())
        session.commit()

        entrees = ConsulterLeJournal().executer(session)
        assert len(entrees) == 1
        assert entrees[0].situation == "il y a une fuite dans la 319"
        assert entrees[0].issue == SuiteDonnee.VALIDEE.value

    def test_la_situation_est_conservee_telle_que_formulee(
        self, session: Session
    ) -> None:
        """Reconstituer une decision suppose de savoir ce qui a ete demande."""
        ConsignerUneDecision().executer(session, _decision())
        session.commit()

        entree = ConsulterLeJournal().executer(session)[0]
        assert entree.situation == "il y a une fuite dans la 319"
        assert entree.proposition == "R-00017 en c406"
        assert "c406" in entree.justification

    def test_plusieurs_decisions_sont_toutes_conservees(
        self, session: Session
    ) -> None:
        consignateur = ConsignerUneDecision()
        for rang in range(3):
            consignateur.executer(
                session,
                DecisionAConsigner(
                    service="chambres",
                    situation=f"situation {rang}",
                    proposition=f"proposition {rang}",
                    justification="",
                    issue=SuiteDonnee.VALIDEE.value,
                ),
            )
        session.commit()

        assert len(ConsulterLeJournal().executer(session)) == 3

    def test_le_filtrage_retient_les_seuls_ecarts(self, session: Session) -> None:
        consignateur = ConsignerUneDecision()
        consignateur.executer(session, _decision())
        consignateur.executer(
            session, _decision(issue=SuiteDonnee.REFUSEE.value, motif="trop loin")
        )
        session.commit()

        tous = ConsulterLeJournal().executer(session)
        ecarts = ConsulterLeJournal().executer(session, ecarts_seulement=True)

        assert len(tous) == 2
        assert len(ecarts) == 1
        assert ecarts[0].issue == SuiteDonnee.REFUSEE.value

    def test_la_limite_borne_la_restitution(self, session: Session) -> None:
        consignateur = ConsignerUneDecision()
        for rang in range(5):
            consignateur.executer(
                session,
                DecisionAConsigner(
                    service="chambres",
                    situation=f"situation {rang}",
                    proposition="",
                    justification="",
                    issue=SuiteDonnee.VALIDEE.value,
                ),
            )
        session.commit()

        assert len(ConsulterLeJournal().executer(session, limite=2)) == 2


class TestAjoutSeul:
    """Verifie qu'aucune modification n'est possible.

    Un journal dont les entrees pourraient etre alterees ne fonderait aucune
    tracabilite: la propriete doit tenir par construction et non par
    convention.
    """

    def test_le_depot_n_expose_aucune_modification(self) -> None:
        from src.donnees import JournalDesDecisions

        exposees = {
            nom for nom in dir(JournalDesDecisions) if not nom.startswith("_")
        }
        interdites = {"modifier", "supprimer", "effacer", "mettre_a_jour", "purger"}
        assert not exposees & interdites
