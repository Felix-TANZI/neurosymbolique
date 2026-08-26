"""Schemas de consultation de l'etat de l'etablissement.

Les schemas exposent l'etat persiste sous une forme destinee a l'affichage.
Ils demeurent distincts des schemas de decision: consulter le parc et soumettre
une situation au raisonnement repondent a des besoins differents, et lier les
deux contraindrait inutilement leur evolution.
"""

from datetime import date, time

from pydantic import BaseModel, Field

from src.domaine import (
    AgentEtage,
    Chambre,
    Incident,
    Reservation,
    TacheNettoyage,
)


class ChambreConsultee(BaseModel):
    """Chambre du parc telle que restituee a la consultation."""

    numero: str
    etage: int
    capacite: int
    categorie: int
    categorie_libelle: str
    equipements: list[str]
    etat_proprete: str
    etat_technique: str
    etat_occupation: str
    attribuable: bool = Field(
        description="La chambre peut recevoir une reservation en l'etat"
    )
    chambres_communicantes: list[str]

    @classmethod
    def depuis(cls, chambre: Chambre) -> "ChambreConsultee":
        return cls(
            numero=str(chambre.numero),
            etage=chambre.etage,
            capacite=chambre.capacite,
            categorie=chambre.categorie.value,
            categorie_libelle=chambre.categorie.name.lower(),
            equipements=sorted(
                equipement.value for equipement in chambre.equipements
            ),
            etat_proprete=chambre.etat_proprete.value,
            etat_technique=chambre.etat_technique.value,
            etat_occupation=chambre.etat_occupation.value,
            attribuable=chambre.est_attribuable,
            chambres_communicantes=sorted(
                str(voisine) for voisine in chambre.chambres_communicantes
            ),
        )


class ReservationConsultee(BaseModel):
    """Sejour tel que restitue a la consultation."""

    identifiant: str
    client: str
    statut_fidelite: int
    arrivee: date
    depart: date
    nuitees: int
    nombre_personnes: int
    categorie_contractee: int
    heure_arrivee_prevue: time
    heure_acces_contractuelle: time
    arrivee_anticipee: bool = Field(
        description="Le client se presente avant l'heure d'acces garantie"
    )
    exigences_obligatoires: list[str]
    exigences_souhaitees: list[str]
    chambre_affectee: str | None

    @classmethod
    def depuis(cls, reservation: Reservation) -> "ReservationConsultee":
        return cls(
            identifiant=str(reservation.identifiant),
            client=reservation.client.identifiant,
            statut_fidelite=reservation.client.statut_fidelite.value,
            arrivee=reservation.periode.arrivee,
            depart=reservation.periode.depart,
            nuitees=reservation.periode.nombre_nuitees,
            nombre_personnes=reservation.nombre_personnes,
            categorie_contractee=reservation.categorie_contractee.value,
            heure_arrivee_prevue=reservation.heure_arrivee.prevue,
            heure_acces_contractuelle=reservation.heure_arrivee.contractuelle,
            arrivee_anticipee=reservation.heure_arrivee.est_anticipee(),
            exigences_obligatoires=sorted(
                equipement.value
                for equipement in reservation.exigences_obligatoires
            ),
            exigences_souhaitees=sorted(
                equipement.value for equipement in reservation.exigences_souhaitees
            ),
            chambre_affectee=(
                str(reservation.chambre_affectee)
                if reservation.chambre_affectee is not None
                else None
            ),
        )


class AgentConsulte(BaseModel):
    """Agent d'etage tel que restitue a la consultation."""

    identifiant: str
    secteur: str
    debut_service: time
    fin_service: time
    disponibilite: str
    minutes_restantes: int
    affectable: bool = Field(description="L'agent peut recevoir une affectation")
    competences: list[str]

    @classmethod
    def depuis(
        cls, agent: AgentEtage, competences: tuple[str, ...] = ()
    ) -> "AgentConsulte":
        return cls(
            identifiant=str(agent.identifiant),
            secteur=str(agent.secteur),
            debut_service=agent.plage.debut,
            fin_service=agent.plage.fin,
            disponibilite=agent.disponibilite.value,
            minutes_restantes=agent.minutes_restantes,
            affectable=agent.est_affectable,
            competences=list(competences),
        )


class TacheConsultee(BaseModel):
    """Prestation de nettoyage telle que restituee a la consultation."""

    identifiant: str
    chambre: str
    prestation: str
    secteur: str
    echeance: time | None
    priorite: int
    statut: str
    duree_minutes: int
    competences_requises: list[str]

    @classmethod
    def depuis(
        cls, tache: TacheNettoyage, competences: tuple[str, ...] = ()
    ) -> "TacheConsultee":
        return cls(
            identifiant=tache.identifiant,
            chambre=str(tache.chambre),
            prestation=tache.prestation.value,
            secteur=str(tache.secteur),
            echeance=tache.echeance,
            priorite=tache.priorite.value,
            statut=tache.statut.value,
            duree_minutes=tache.duree_effective,
            competences_requises=list(competences),
        )


class IncidentConsulte(BaseModel):
    """Evenement technique tel que restitue a la consultation."""

    identifiant: str
    chambre: str
    type_incident: str
    gravite: int
    signale_le: str
    description: str
    resolu: bool

    @classmethod
    def depuis(cls, incident: Incident) -> "IncidentConsulte":
        return cls(
            identifiant=incident.identifiant,
            chambre=str(incident.chambre),
            type_incident=incident.type_incident.value,
            gravite=incident.gravite.value,
            signale_le=incident.signale_le.isoformat(),
            description=incident.description,
            resolu=incident.resolu,
        )


class EtatDeLEtablissement(BaseModel):
    """Grandeurs caracteristiques de l'etat courant."""

    jour: date
    chambres: int
    disponibles: int
    arrivees_a_traiter: int
    incidents_ouverts: int
    taches_a_planifier: int
    agents_affectables: int


class DemandeParReference(BaseModel):
    """Parametres facultatifs d'une decision portant sur l'etat persiste."""

    poids: dict[str, int] | None = Field(
        default=None,
        description=(
            "Ponderation des preferences. Une ponderation ne peut rendre "
            "admissible une option qu'une contrainte dure ecarte."
        ),
    )
    temps_maximal: float | None = Field(
        default=None,
        gt=0,
        le=60,
        description="Duree de calcul allouee, en secondes",
    )
