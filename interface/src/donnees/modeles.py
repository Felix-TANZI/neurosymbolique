"""Tables de persistance de l'etat operationnel.

Les tables sont declarees independamment des entites du domaine. Cette
separation impose une conversion explicite, prise en charge par les depots,
mais elle preserve l'ignorance du domaine a l'egard de la persistance: les
entites demeurent immuables et sans dependance a l'ORM.

Le choix resulte d'une contrainte: le mappage imperatif de SQLAlchemy, qui
associerait directement les entites aux tables, exige des instances mutables.
L'immuabilite ayant ete retenue pour garantir le determinisme et
l'auditabilite, le mappage explicite demeure la seule voie compatible.
"""

from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative commune aux tables de persistance."""


class ChambreEnregistree(Base):
    """Etat persiste d'une chambre du parc."""

    __tablename__ = "chambre"

    numero: Mapped[str] = mapped_column(String(16), primary_key=True)
    etage: Mapped[int] = mapped_column(Integer, nullable=False)
    capacite: Mapped[int] = mapped_column(Integer, nullable=False)
    categorie: Mapped[int] = mapped_column(Integer, nullable=False)
    etat_proprete: Mapped[str] = mapped_column(String(24), nullable=False)
    etat_technique: Mapped[str] = mapped_column(String(24), nullable=False)
    etat_occupation: Mapped[str] = mapped_column(String(24), nullable=False)
    secteur: Mapped[str] = mapped_column(String(64), nullable=False)

    equipements: Mapped[list["EquipementDeChambre"]] = relationship(
        back_populates="chambre", cascade="all, delete-orphan", lazy="selectin"
    )
    communications: Mapped[list["ChambresCommunicantes"]] = relationship(
        foreign_keys="ChambresCommunicantes.numero_chambre",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("index_chambre_etat", "etat_proprete", "etat_technique"),
        Index("index_chambre_secteur", "secteur"),
    )


class EquipementDeChambre(Base):
    """Equipement dont dispose une chambre."""

    __tablename__ = "equipement_de_chambre"

    identifiant: Mapped[int] = mapped_column(Integer, primary_key=True)
    numero_chambre: Mapped[str] = mapped_column(
        ForeignKey("chambre.numero", ondelete="CASCADE"), nullable=False
    )
    equipement: Mapped[str] = mapped_column(String(32), nullable=False)

    chambre: Mapped[ChambreEnregistree] = relationship(back_populates="equipements")

    __table_args__ = (
        UniqueConstraint("numero_chambre", "equipement", name="unicite_equipement"),
    )


class ChambresCommunicantes(Base):
    """Communication entre deux chambres voisines."""

    __tablename__ = "chambres_communicantes"

    identifiant: Mapped[int] = mapped_column(Integer, primary_key=True)
    numero_chambre: Mapped[str] = mapped_column(
        ForeignKey("chambre.numero", ondelete="CASCADE"), nullable=False
    )
    numero_voisine: Mapped[str] = mapped_column(
        ForeignKey("chambre.numero", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("numero_chambre", "numero_voisine", name="unicite_voisinage"),
    )


class ClientEnregistre(Base):
    """Personne accueillie, porteuse de caracteristiques durables."""

    __tablename__ = "client"

    identifiant: Mapped[str] = mapped_column(String(64), primary_key=True)
    statut_fidelite: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    besoins: Mapped[list["BesoinPermanent"]] = relationship(
        back_populates="client", cascade="all, delete-orphan", lazy="selectin"
    )


class BesoinPermanent(Base):
    """Besoin durable d'un client, independant du sejour."""

    __tablename__ = "besoin_permanent"

    identifiant: Mapped[int] = mapped_column(Integer, primary_key=True)
    identifiant_client: Mapped[str] = mapped_column(
        ForeignKey("client.identifiant", ondelete="CASCADE"), nullable=False
    )
    equipement: Mapped[str] = mapped_column(String(32), nullable=False)

    client: Mapped[ClientEnregistre] = relationship(back_populates="besoins")


class ReservationEnregistree(Base):
    """Sejour prevu ou en cours."""

    __tablename__ = "reservation"

    identifiant: Mapped[str] = mapped_column(String(64), primary_key=True)
    identifiant_client: Mapped[str] = mapped_column(
        ForeignKey("client.identifiant"), nullable=False
    )
    arrivee: Mapped[date] = mapped_column(Date, nullable=False)
    depart: Mapped[date] = mapped_column(Date, nullable=False)
    nombre_personnes: Mapped[int] = mapped_column(Integer, nullable=False)
    categorie_contractee: Mapped[int] = mapped_column(Integer, nullable=False)
    heure_arrivee_prevue: Mapped[time] = mapped_column(Time, nullable=False)
    heure_acces_contractuelle: Mapped[time] = mapped_column(Time, nullable=False)
    numero_chambre: Mapped[str | None] = mapped_column(
        ForeignKey("chambre.numero"), nullable=True
    )

    client: Mapped[ClientEnregistre] = relationship(lazy="selectin")
    exigences: Mapped[list["ExigenceDeSejour"]] = relationship(
        back_populates="reservation", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("index_reservation_periode", "arrivee", "depart"),
        Index("index_reservation_chambre", "numero_chambre"),
    )


class ExigenceDeSejour(Base):
    """Besoin exprime pour un sejour donne."""

    __tablename__ = "exigence_de_sejour"

    identifiant: Mapped[int] = mapped_column(Integer, primary_key=True)
    identifiant_reservation: Mapped[str] = mapped_column(
        ForeignKey("reservation.identifiant", ondelete="CASCADE"), nullable=False
    )
    equipement: Mapped[str] = mapped_column(String(32), nullable=False)
    obligatoire: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    reservation: Mapped[ReservationEnregistree] = relationship(
        back_populates="exigences"
    )


class IncidentEnregistre(Base):
    """Evenement technique affectant une chambre."""

    __tablename__ = "incident"

    identifiant: Mapped[str] = mapped_column(String(64), primary_key=True)
    numero_chambre: Mapped[str] = mapped_column(
        ForeignKey("chambre.numero"), nullable=False
    )
    type_incident: Mapped[str] = mapped_column(String(48), nullable=False)
    gravite: Mapped[int] = mapped_column(Integer, nullable=False)
    signale_le: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    resolu: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (Index("index_incident_ouvert", "resolu", "gravite"),)


class AgentEnregistre(Base):
    """Agent d'etage et son affectation de service."""

    __tablename__ = "agent"

    identifiant: Mapped[str] = mapped_column(String(64), primary_key=True)
    secteur: Mapped[str] = mapped_column(String(64), nullable=False)
    debut_service: Mapped[time] = mapped_column(Time, nullable=False)
    fin_service: Mapped[time] = mapped_column(Time, nullable=False)
    disponibilite: Mapped[str] = mapped_column(String(24), nullable=False)
    minutes_deja_affectees: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    competences: Mapped[list["CompetenceDAgent"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (Index("index_agent_secteur", "secteur", "disponibilite"),)


class CompetenceDAgent(Base):
    """Qualification detenue par un agent."""

    __tablename__ = "competence_agent"

    identifiant: Mapped[int] = mapped_column(Integer, primary_key=True)
    identifiant_agent: Mapped[str] = mapped_column(
        ForeignKey("agent.identifiant", ondelete="CASCADE"), nullable=False
    )
    competence: Mapped[str] = mapped_column(String(48), nullable=False)

    agent: Mapped[AgentEnregistre] = relationship(back_populates="competences")

    __table_args__ = (
        UniqueConstraint("identifiant_agent", "competence", name="unicite_competence"),
    )


class TacheEnregistree(Base):
    """Prestation de nettoyage a realiser sur une chambre."""

    __tablename__ = "tache_nettoyage"

    identifiant: Mapped[str] = mapped_column(String(64), primary_key=True)
    numero_chambre: Mapped[str] = mapped_column(
        ForeignKey("chambre.numero"), nullable=False
    )
    prestation: Mapped[str] = mapped_column(String(32), nullable=False)
    secteur: Mapped[str] = mapped_column(String(64), nullable=False)
    echeance: Mapped[time | None] = mapped_column(Time, nullable=True)
    priorite: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    statut: Mapped[str] = mapped_column(String(24), nullable=False)
    duree_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    identifiant_agent: Mapped[str | None] = mapped_column(
        ForeignKey("agent.identifiant"), nullable=True
    )

    exigences: Mapped[list["CompetenceRequise"]] = relationship(
        back_populates="tache", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (Index("index_tache_statut", "statut", "secteur"),)


class CompetenceRequise(Base):
    """Qualification exigee par une tache de nettoyage."""

    __tablename__ = "competence_requise"

    identifiant: Mapped[int] = mapped_column(Integer, primary_key=True)
    identifiant_tache: Mapped[str] = mapped_column(
        ForeignKey("tache_nettoyage.identifiant", ondelete="CASCADE"), nullable=False
    )
    competence: Mapped[str] = mapped_column(String(48), nullable=False)

    tache: Mapped[TacheEnregistree] = relationship(back_populates="exigences")


class SecteurReserve(Base):
    """Secteur dont l'acces est restreint aux agents habilites."""

    __tablename__ = "secteur_reserve"

    nom: Mapped[str] = mapped_column(String(64), primary_key=True)


class DecisionConsignee(Base):
    """Decision soumise a un responsable et son issue.

    Le journal est en ajout seul: aucune ligne n'est modifiee ni supprimee,
    de sorte qu'une decision consignee demeure consultable telle qu'elle a
    ete prise.
    """

    __tablename__ = "decision_consignee"

    identifiant: Mapped[int] = mapped_column(Integer, primary_key=True)
    service: Mapped[str] = mapped_column(String(32), nullable=False)
    situation: Mapped[str] = mapped_column(String(4096), nullable=False)
    proposition: Mapped[str] = mapped_column(String(512), nullable=False)
    justification: Mapped[str] = mapped_column(String(8192), nullable=False)
    issue: Mapped[str] = mapped_column(String(24), nullable=False)
    motif: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    valideur: Mapped[str] = mapped_column(String(64), nullable=False)
    horodatage: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    version_regles: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    __table_args__ = (
        Index("index_decision_horodatage", "horodatage"),
        Index("index_decision_service", "service", "issue"),
    )