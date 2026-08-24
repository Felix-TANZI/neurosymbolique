"""Depots d'acces a l'etat operationnel.

Un depot expose des operations formulees en langage metier et masque
entierement le langage de requetes. Il recoit et restitue des entites du
domaine, jamais des lignes de persistance.

Les depots ne comportent aucune logique metier: filtrer sur un etat constitue
une requete, apprecier si une chambre convient a une reservation releve des
regles. Cette frontiere preserve la possibilite de modifier les regles sans
toucher a l'acces aux donnees.
"""

import logging
from collections.abc import Iterable, Sequence
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domaine import (
    AgentEtage,
    Chambre,
    Client,
    Incident,
    NumeroChambre,
    Periode,
    Reservation,
    StatutTache,
    TacheNettoyage,
)

from .conversion import (
    competences_d_agent,
    competences_requises,
    vers_agent,
    vers_chambre,
    vers_client,
    vers_incident,
    vers_ligne_d_agent,
    vers_ligne_d_incident,
    vers_ligne_de_chambre,
    vers_ligne_de_client,
    vers_ligne_de_reservation,
    vers_ligne_de_tache,
    vers_reservation,
    vers_tache,
)
from .modeles import (
    AgentEnregistre,
    ChambreEnregistree,
    ClientEnregistre,
    DecisionConsignee,
    IncidentEnregistre,
    ReservationEnregistree,
    SecteurReserve,
    TacheEnregistree,
)

logger = logging.getLogger(__name__)


class EntiteIntrouvableError(LookupError):
    """Signale une entite absente de l'etat operationnel."""


class DepotChambres:
    """Acces au parc de chambres."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def lister(self) -> list[Chambre]:
        """Restitue l'integralite du parc, ordonnee par numero."""
        lignes = self._session.scalars(
            select(ChambreEnregistree).order_by(ChambreEnregistree.numero)
        ).all()
        return [vers_chambre(ligne) for ligne in lignes]

    def retrouver(self, numero: NumeroChambre) -> Chambre:
        """Restitue une chambre, ou signale son absence."""
        ligne = self._session.get(ChambreEnregistree, str(numero))
        if ligne is None:
            raise EntiteIntrouvableError(f"chambre absente du parc: {numero}")
        return vers_chambre(ligne)

    def lister_par_secteur(self, secteur: str) -> list[Chambre]:
        """Restitue les chambres d'un secteur donne."""
        lignes = self._session.scalars(
            select(ChambreEnregistree)
            .where(ChambreEnregistree.secteur == secteur)
            .order_by(ChambreEnregistree.numero)
        ).all()
        return [vers_chambre(ligne) for ligne in lignes]

    def secteur_de(self, numero: NumeroChambre) -> str:
        """Restitue le secteur de nettoyage auquel une chambre est rattachee."""
        ligne = self._session.get(ChambreEnregistree, str(numero))
        if ligne is None:
            raise EntiteIntrouvableError(f"chambre absente du parc: {numero}")
        return ligne.secteur

    def enregistrer(self, chambre: Chambre, secteur: str) -> None:
        """Enregistre une chambre nouvelle ou remplace son etat persiste."""
        existante = self._session.get(ChambreEnregistree, str(chambre.numero))
        if existante is not None:
            self._session.delete(existante)
            self._session.flush()
        self._session.add(vers_ligne_de_chambre(chambre, secteur))

    def enregistrer_plusieurs(
        self, chambres: Iterable[tuple[Chambre, str]]
    ) -> int:
        """Enregistre un ensemble de chambres et restitue leur nombre."""
        lignes = [
            vers_ligne_de_chambre(chambre, secteur) for chambre, secteur in chambres
        ]
        self._session.add_all(lignes)
        return len(lignes)

    def denombrer(self) -> int:
        """Restitue le nombre de chambres du parc."""
        return len(self._session.scalars(select(ChambreEnregistree.numero)).all())


class DepotReservations:
    """Acces aux sejours prevus et en cours."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def retrouver(self, identifiant: str) -> Reservation:
        """Restitue une reservation, ou signale son absence."""
        ligne = self._session.get(ReservationEnregistree, identifiant)
        if ligne is None:
            raise EntiteIntrouvableError(f"reservation absente: {identifiant}")
        return vers_reservation(ligne)

    def lister_sur_periode(self, periode: Periode) -> list[Reservation]:
        """Restitue les sejours dont la periode chevauche celle fournie.

        Le chevauchement suit la convention hoteliere: un depart le jour d'une
        arrivee ne constitue pas un conflit.
        """
        lignes = self._session.scalars(
            select(ReservationEnregistree)
            .where(ReservationEnregistree.arrivee < periode.depart)
            .where(ReservationEnregistree.depart > periode.arrivee)
            .order_by(ReservationEnregistree.arrivee)
        ).all()
        return [vers_reservation(ligne) for ligne in lignes]

    def lister_affectees_sur_periode(self, periode: Periode) -> list[Reservation]:
        """Restitue les sejours occupant deja une chambre sur la periode."""
        return [
            reservation
            for reservation in self.lister_sur_periode(periode)
            if reservation.est_affectee
        ]

    def lister_a_affecter(self, jour: date) -> list[Reservation]:
        """Restitue les sejours arrivant un jour donne sans chambre affectee."""
        lignes = self._session.scalars(
            select(ReservationEnregistree)
            .where(ReservationEnregistree.arrivee == jour)
            .where(ReservationEnregistree.numero_chambre.is_(None))
            .order_by(ReservationEnregistree.heure_arrivee_prevue)
        ).all()
        return [vers_reservation(ligne) for ligne in lignes]

    def enregistrer(self, reservation: Reservation) -> None:
        """Enregistre une reservation et son client si celui-ci est nouveau."""
        if self._session.get(ClientEnregistre, reservation.client.identifiant) is None:
            self._session.add(vers_ligne_de_client(reservation.client))
            self._session.flush()

        existante = self._session.get(
            ReservationEnregistree, str(reservation.identifiant)
        )
        if existante is not None:
            self._session.delete(existante)
            self._session.flush()
        self._session.add(vers_ligne_de_reservation(reservation))

    def denombrer(self) -> int:
        """Restitue le nombre de reservations enregistrees."""
        return len(
            self._session.scalars(select(ReservationEnregistree.identifiant)).all()
        )


class DepotClients:
    """Acces aux personnes accueillies."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def retrouver(self, identifiant: str) -> Client:
        """Restitue un client, ou signale son absence."""
        ligne = self._session.get(ClientEnregistre, identifiant)
        if ligne is None:
            raise EntiteIntrouvableError(f"client absent: {identifiant}")
        return vers_client(ligne)

    def enregistrer_plusieurs(self, clients: Iterable[Client]) -> int:
        """Enregistre un ensemble de clients et restitue leur nombre."""
        lignes = [vers_ligne_de_client(client) for client in clients]
        self._session.add_all(lignes)
        return len(lignes)


class DepotIncidents:
    """Acces aux evenements techniques affectant le parc."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def lister_ouverts(self) -> list[Incident]:
        """Restitue les incidents non resolus, du plus grave au moins grave."""
        lignes = self._session.scalars(
            select(IncidentEnregistre)
            .where(IncidentEnregistre.resolu.is_(False))
            .order_by(
                IncidentEnregistre.gravite.desc(), IncidentEnregistre.signale_le
            )
        ).all()
        return [vers_incident(ligne) for ligne in lignes]

    def lister_par_chambre(self, numero: NumeroChambre) -> list[Incident]:
        """Restitue les incidents affectant une chambre, resolus compris."""
        lignes = self._session.scalars(
            select(IncidentEnregistre)
            .where(IncidentEnregistre.numero_chambre == str(numero))
            .order_by(IncidentEnregistre.signale_le.desc())
        ).all()
        return [vers_incident(ligne) for ligne in lignes]

    def enregistrer(self, incident: Incident) -> None:
        """Enregistre un incident nouveau ou remplace son etat persiste."""
        existant = self._session.get(IncidentEnregistre, incident.identifiant)
        if existant is not None:
            self._session.delete(existant)
            self._session.flush()
        self._session.add(vers_ligne_d_incident(incident))

    def enregistrer_plusieurs(self, incidents: Iterable[Incident]) -> int:
        """Enregistre un ensemble d'incidents et restitue leur nombre."""
        lignes = [vers_ligne_d_incident(incident) for incident in incidents]
        self._session.add_all(lignes)
        return len(lignes)


class DepotAgents:
    """Acces aux agents d'etage et a leurs qualifications."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def lister(self) -> list[AgentEtage]:
        """Restitue l'ensemble des agents, ordonnes par identifiant."""
        lignes = self._session.scalars(
            select(AgentEnregistre).order_by(AgentEnregistre.identifiant)
        ).all()
        return [vers_agent(ligne) for ligne in lignes]

    def lister_par_secteur(self, secteur: str) -> list[AgentEtage]:
        """Restitue les agents rattaches a un secteur."""
        lignes = self._session.scalars(
            select(AgentEnregistre)
            .where(AgentEnregistre.secteur == secteur)
            .order_by(AgentEnregistre.identifiant)
        ).all()
        return [vers_agent(ligne) for ligne in lignes]

    def competences(self) -> dict[str, tuple[str, ...]]:
        """Restitue les qualifications de chaque agent qui en detient."""
        lignes = self._session.scalars(select(AgentEnregistre)).all()
        return {
            ligne.identifiant: tuple(sorted(competences_d_agent(ligne)))
            for ligne in lignes
            if ligne.competences
        }

    def enregistrer(
        self, agent: AgentEtage, qualifications: frozenset[str] = frozenset()
    ) -> None:
        """Enregistre un agent nouveau ou remplace son etat persiste."""
        existant = self._session.get(AgentEnregistre, str(agent.identifiant))
        if existant is not None:
            self._session.delete(existant)
            self._session.flush()
        self._session.add(vers_ligne_d_agent(agent, qualifications))

    def enregistrer_plusieurs(
        self, agents: Iterable[tuple[AgentEtage, frozenset[str]]]
    ) -> int:
        """Enregistre un ensemble d'agents et restitue leur nombre."""
        lignes = [
            vers_ligne_d_agent(agent, qualifications)
            for agent, qualifications in agents
        ]
        self._session.add_all(lignes)
        return len(lignes)


class DepotTaches:
    """Acces aux prestations de nettoyage."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def lister_a_planifier(self) -> list[TacheNettoyage]:
        """Restitue les taches en attente de planification."""
        lignes = self._session.scalars(
            select(TacheEnregistree)
            .where(TacheEnregistree.statut == StatutTache.A_PLANIFIER.value)
            .order_by(TacheEnregistree.priorite.desc(), TacheEnregistree.identifiant)
        ).all()
        return [vers_tache(ligne) for ligne in lignes]

    def lister_par_secteur(self, secteur: str) -> list[TacheNettoyage]:
        """Restitue les taches d'un secteur, quel que soit leur statut."""
        lignes = self._session.scalars(
            select(TacheEnregistree)
            .where(TacheEnregistree.secteur == secteur)
            .order_by(TacheEnregistree.identifiant)
        ).all()
        return [vers_tache(ligne) for ligne in lignes]

    def exigences(self) -> dict[str, tuple[str, ...]]:
        """Restitue les qualifications exigees par chaque tache qui en exige."""
        lignes = self._session.scalars(select(TacheEnregistree)).all()
        return {
            ligne.identifiant: tuple(sorted(competences_requises(ligne)))
            for ligne in lignes
            if ligne.exigences
        }

    def enregistrer(
        self, tache: TacheNettoyage, qualifications: frozenset[str] = frozenset()
    ) -> None:
        """Enregistre une tache nouvelle ou remplace son etat persiste."""
        existante = self._session.get(TacheEnregistree, tache.identifiant)
        if existante is not None:
            self._session.delete(existante)
            self._session.flush()
        self._session.add(vers_ligne_de_tache(tache, qualifications))

    def enregistrer_plusieurs(
        self, taches: Iterable[tuple[TacheNettoyage, frozenset[str]]]
    ) -> int:
        """Enregistre un ensemble de taches et restitue leur nombre."""
        lignes = [
            vers_ligne_de_tache(tache, qualifications)
            for tache, qualifications in taches
        ]
        self._session.add_all(lignes)
        return len(lignes)


class DepotSecteurs:
    """Acces aux secteurs a acces restreint."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def lister_reserves(self) -> list[str]:
        """Restitue les secteurs dont l'acces est restreint."""
        return sorted(self._session.scalars(select(SecteurReserve.nom)).all())

    def declarer_reserves(self, secteurs: Iterable[str]) -> None:
        """Declare les secteurs a acces restreint, en remplacant les precedents."""
        for ligne in self._session.scalars(select(SecteurReserve)).all():
            self._session.delete(ligne)
        self._session.flush()
        self._session.add_all(SecteurReserve(nom=nom) for nom in sorted(set(secteurs)))


class JournalDesDecisions:
    """Consignation des decisions soumises aux responsables.

    Le journal est en ajout seul: il n'expose ni modification ni suppression.
    Une decision consignee demeure ainsi consultable telle qu'elle a ete prise,
    ce qui rend le raisonnement reconstituable a posteriori.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def consigner(
        self,
        service: str,
        situation: str,
        proposition: str,
        justification: str,
        issue: str,
        valideur: str,
        motif: str = "",
        version_regles: str = "",
        horodatage: datetime | None = None,
    ) -> None:
        """Ajoute une decision au journal."""
        self._session.add(
            DecisionConsignee(
                service=service,
                situation=situation,
                proposition=proposition,
                justification=justification,
                issue=issue,
                motif=motif,
                valideur=valideur,
                version_regles=version_regles,
                horodatage=horodatage or datetime.now(),
            )
        )
        logger.info("decision consignee: %s, issue %s", service, issue)

    def lister(self, limite: int = 100) -> Sequence[DecisionConsignee]:
        """Restitue les decisions les plus recentes."""
        return self._session.scalars(
            select(DecisionConsignee)
            .order_by(DecisionConsignee.horodatage.desc())
            .limit(limite)
        ).all()

    def lister_par_service(
        self, service: str, limite: int = 100
    ) -> Sequence[DecisionConsignee]:
        """Restitue les decisions d'un service donne."""
        return self._session.scalars(
            select(DecisionConsignee)
            .where(DecisionConsignee.service == service)
            .order_by(DecisionConsignee.horodatage.desc())
            .limit(limite)
        ).all()

    def denombrer(self) -> int:
        """Restitue le nombre de decisions consignees."""
        return len(self._session.scalars(select(DecisionConsignee.identifiant)).all())
