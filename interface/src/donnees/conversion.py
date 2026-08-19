"""Conversion entre les tables de persistance et les entites du domaine.

La conversion constitue la frontiere entre deux representations: les tables,
mutables et normalisees pour le stockage, et les entites, immuables et
porteuses des invariants metier. Elle est isolee dans ce module afin d'etre
verifiable independamment des depots.

La propriete attendue est l'aller-retour: une entite convertie en ligne puis
reconvertie doit etre identique a l'originale. Toute perte d'information a la
conversion fausserait le raisonnement ulterieur.
"""

from enum import Enum

from src.domaine import (
    AgentEtage,
    Categorie,
    Chambre,
    Client,
    DisponibiliteAgent,
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

from .modeles import (
    AgentEnregistre,
    BesoinPermanent,
    ChambreEnregistree,
    ChambresCommunicantes,
    ClientEnregistre,
    CompetenceDAgent,
    CompetenceRequise,
    EquipementDeChambre,
    ExigenceDeSejour,
    IncidentEnregistre,
    ReservationEnregistree,
    TacheEnregistree,
)


class ConversionImpossibleError(ValueError):
    """Signale une ligne dont le contenu ne correspond a aucune valeur du domaine.

    L'erreur revele une incoherence entre la base et le vocabulaire du
    domaine, par exemple a la suite d'une modification manuelle ou d'une
    migration incomplete.
    """


def _valeur[MembreDEnumeration: Enum](
    enumeration: type[MembreDEnumeration], brute: object, contexte: str
) -> MembreDEnumeration:
    """Retrouve le membre d'enumeration correspondant a une valeur persistee."""
    try:
        return enumeration(brute)
    except ValueError as erreur:
        raise ConversionImpossibleError(
            f"valeur inconnue pour {contexte}: {brute!r}"
        ) from erreur


def vers_chambre(ligne: ChambreEnregistree) -> Chambre:
    """Construit l'entite chambre a partir de sa ligne de persistance."""
    return Chambre(
        numero=NumeroChambre(ligne.numero),
        etage=ligne.etage,
        capacite=ligne.capacite,
        categorie=_valeur(Categorie, ligne.categorie, "categorie"),
        equipements=frozenset(
            _valeur(Equipement, association.equipement, "equipement")
            for association in ligne.equipements
        ),
        etat_proprete=_valeur(EtatProprete, ligne.etat_proprete, "proprete"),
        etat_technique=_valeur(EtatTechnique, ligne.etat_technique, "technique"),
        etat_occupation=_valeur(EtatOccupation, ligne.etat_occupation, "occupation"),
        chambres_communicantes=frozenset(
            NumeroChambre(voisinage.numero_voisine)
            for voisinage in ligne.communications
        ),
    )


def vers_ligne_de_chambre(chambre: Chambre, secteur: str) -> ChambreEnregistree:
    """Construit la ligne de persistance d'une chambre.

    Le secteur ne figure pas dans l'entite: il releve de l'organisation du
    travail et non de la chambre elle-meme. Il est donc transmis a part.
    """
    ligne = ChambreEnregistree(
        numero=str(chambre.numero),
        etage=chambre.etage,
        capacite=chambre.capacite,
        categorie=chambre.categorie.value,
        etat_proprete=chambre.etat_proprete.value,
        etat_technique=chambre.etat_technique.value,
        etat_occupation=chambre.etat_occupation.value,
        secteur=secteur,
    )
    ligne.equipements = [
        EquipementDeChambre(equipement=equipement.value)
        for equipement in sorted(chambre.equipements)
    ]
    ligne.communications = [
        ChambresCommunicantes(
            numero_chambre=str(chambre.numero), numero_voisine=str(voisine)
        )
        for voisine in sorted(chambre.chambres_communicantes, key=str)
    ]
    return ligne


def vers_client(ligne: ClientEnregistre) -> Client:
    """Construit l'entite client a partir de sa ligne de persistance."""
    return Client(
        identifiant=ligne.identifiant,
        statut_fidelite=_valeur(StatutFidelite, ligne.statut_fidelite, "fidelite"),
        besoins_permanents=frozenset(
            _valeur(Equipement, besoin.equipement, "besoin")
            for besoin in ligne.besoins
        ),
    )


def vers_ligne_de_client(client: Client) -> ClientEnregistre:
    """Construit la ligne de persistance d'un client."""
    ligne = ClientEnregistre(
        identifiant=client.identifiant,
        statut_fidelite=client.statut_fidelite.value,
    )
    ligne.besoins = [
        BesoinPermanent(equipement=equipement.value)
        for equipement in sorted(client.besoins_permanents)
    ]
    return ligne


def vers_reservation(ligne: ReservationEnregistree) -> Reservation:
    """Construit l'entite reservation a partir de sa ligne de persistance."""
    return Reservation(
        identifiant=IdentifiantReservation(ligne.identifiant),
        client=vers_client(ligne.client),
        periode=Periode(arrivee=ligne.arrivee, depart=ligne.depart),
        nombre_personnes=ligne.nombre_personnes,
        categorie_contractee=_valeur(
            Categorie, ligne.categorie_contractee, "categorie contractee"
        ),
        heure_arrivee=HeureArrivee(
            prevue=ligne.heure_arrivee_prevue,
            contractuelle=ligne.heure_acces_contractuelle,
        ),
        exigences=frozenset(
            Exigence(
                equipement=_valeur(Equipement, exigence.equipement, "exigence"),
                obligatoire=exigence.obligatoire,
            )
            for exigence in ligne.exigences
        ),
        chambre_affectee=(
            NumeroChambre(ligne.numero_chambre)
            if ligne.numero_chambre is not None
            else None
        ),
    )


def vers_ligne_de_reservation(
    reservation: Reservation,
) -> ReservationEnregistree:
    """Construit la ligne de persistance d'une reservation."""
    ligne = ReservationEnregistree(
        identifiant=str(reservation.identifiant),
        identifiant_client=reservation.client.identifiant,
        arrivee=reservation.periode.arrivee,
        depart=reservation.periode.depart,
        nombre_personnes=reservation.nombre_personnes,
        categorie_contractee=reservation.categorie_contractee.value,
        heure_arrivee_prevue=reservation.heure_arrivee.prevue,
        heure_acces_contractuelle=reservation.heure_arrivee.contractuelle,
        numero_chambre=(
            str(reservation.chambre_affectee)
            if reservation.chambre_affectee is not None
            else None
        ),
    )
    ligne.exigences = [
        ExigenceDeSejour(
            equipement=exigence.equipement.value, obligatoire=exigence.obligatoire
        )
        for exigence in sorted(reservation.exigences, key=lambda e: e.equipement.value)
    ]
    return ligne


def vers_incident(ligne: IncidentEnregistre) -> Incident:
    """Construit l'entite incident a partir de sa ligne de persistance."""
    return Incident(
        identifiant=ligne.identifiant,
        chambre=NumeroChambre(ligne.numero_chambre),
        type_incident=_valeur(TypeIncident, ligne.type_incident, "type d'incident"),
        gravite=_valeur(Gravite, ligne.gravite, "gravite"),
        signale_le=ligne.signale_le,
        description=ligne.description,
        resolu=ligne.resolu,
    )


def vers_ligne_d_incident(incident: Incident) -> IncidentEnregistre:
    """Construit la ligne de persistance d'un incident."""
    return IncidentEnregistre(
        identifiant=incident.identifiant,
        numero_chambre=str(incident.chambre),
        type_incident=incident.type_incident.value,
        gravite=incident.gravite.value,
        signale_le=incident.signale_le,
        description=incident.description,
        resolu=incident.resolu,
    )


def vers_agent(ligne: AgentEnregistre) -> AgentEtage:
    """Construit l'entite agent a partir de sa ligne de persistance."""
    return AgentEtage(
        identifiant=IdentifiantAgent(ligne.identifiant),
        secteur=Secteur(ligne.secteur),
        plage=PlageDeService(debut=ligne.debut_service, fin=ligne.fin_service),
        disponibilite=_valeur(DisponibiliteAgent, ligne.disponibilite, "disponibilite"),
        minutes_deja_affectees=ligne.minutes_deja_affectees,
    )


def vers_ligne_d_agent(
    agent: AgentEtage, competences: frozenset[str] = frozenset()
) -> AgentEnregistre:
    """Construit la ligne de persistance d'un agent et de ses qualifications."""
    ligne = AgentEnregistre(
        identifiant=str(agent.identifiant),
        secteur=str(agent.secteur),
        debut_service=agent.plage.debut,
        fin_service=agent.plage.fin,
        disponibilite=agent.disponibilite.value,
        minutes_deja_affectees=agent.minutes_deja_affectees,
    )
    ligne.competences = [
        CompetenceDAgent(competence=competence) for competence in sorted(competences)
    ]
    return ligne


def vers_tache(ligne: TacheEnregistree) -> TacheNettoyage:
    """Construit l'entite tache a partir de sa ligne de persistance."""
    return TacheNettoyage(
        identifiant=ligne.identifiant,
        chambre=NumeroChambre(ligne.numero_chambre),
        prestation=_valeur(TypePrestation, ligne.prestation, "prestation"),
        secteur=Secteur(ligne.secteur),
        echeance=ligne.echeance,
        priorite=_valeur(PrioriteTache, ligne.priorite, "priorite"),
        statut=_valeur(StatutTache, ligne.statut, "statut"),
        duree_minutes=ligne.duree_minutes,
        agent_affecte=(
            IdentifiantAgent(ligne.identifiant_agent)
            if ligne.identifiant_agent is not None
            else None
        ),
    )


def vers_ligne_de_tache(
    tache: TacheNettoyage, competences_requises: frozenset[str] = frozenset()
) -> TacheEnregistree:
    """Construit la ligne de persistance d'une tache et de ses exigences."""
    ligne = TacheEnregistree(
        identifiant=tache.identifiant,
        numero_chambre=str(tache.chambre),
        prestation=tache.prestation.value,
        secteur=str(tache.secteur),
        echeance=tache.echeance,
        priorite=tache.priorite.value,
        statut=tache.statut.value,
        duree_minutes=tache.duree_minutes,
        identifiant_agent=(
            str(tache.agent_affecte) if tache.agent_affecte is not None else None
        ),
    )
    ligne.exigences = [
        CompetenceRequise(competence=competence)
        for competence in sorted(competences_requises)
    ]
    return ligne


def competences_d_agent(ligne: AgentEnregistre) -> frozenset[str]:
    """Restitue les qualifications persistees d'un agent."""
    return frozenset(association.competence for association in ligne.competences)


def competences_requises(ligne: TacheEnregistree) -> frozenset[str]:
    """Restitue les qualifications exigees par une tache."""
    return frozenset(association.competence for association in ligne.exigences)