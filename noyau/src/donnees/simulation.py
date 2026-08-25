"""Constitution d'un etablissement de reference.

Le generateur produit un etablissement coherent a partir d'un profil: parc de
chambres, clientele, sejours, incidents, agents et prestations de nettoyage.
Les proportions retenues reproduisent celles observees en exploitation
hoteliere, de sorte que les situations engendrees demeurent representatives.

La reproductibilite est garantie par une graine: un meme profil et une meme
graine produisent toujours le meme etablissement. Cette propriete est
indispensable au protocole d'evaluation, une mesure conduite sur un jeu
variable n'etant pas comparable d'une execution a l'autre.

Le generateur constitue un instrument de validation et non un simple
remplissage: il permet de produire a volonte les situations limites qu'une
exploitation reelle ne presenterait qu'exceptionnellement, alors meme que ce
sont elles qui mettent le raisonnement a l'epreuve.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from random import Random

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

logger = logging.getLogger(__name__)

DISTRIBUTION_CATEGORIES: dict[Categorie, float] = {
    Categorie.STANDARD: 0.65,
    Categorie.SUPERIEURE: 0.20,
    Categorie.JUNIOR_SUITE: 0.10,
    Categorie.SUITE: 0.05,
}

EQUIPEMENTS_PAR_CATEGORIE: dict[Categorie, frozenset[Equipement]] = {
    Categorie.STANDARD: frozenset({Equipement.CLIMATISATION}),
    Categorie.SUPERIEURE: frozenset(
        {Equipement.CLIMATISATION, Equipement.COFFRE_FORT}
    ),
    Categorie.JUNIOR_SUITE: frozenset(
        {Equipement.CLIMATISATION, Equipement.COFFRE_FORT, Equipement.BAIGNOIRE}
    ),
    Categorie.SUITE: frozenset(
        {
            Equipement.CLIMATISATION,
            Equipement.COFFRE_FORT,
            Equipement.BAIGNOIRE,
            Equipement.BALCON,
        }
    ),
}

CAPACITE_PAR_CATEGORIE: dict[Categorie, int] = {
    Categorie.STANDARD: 2,
    Categorie.SUPERIEURE: 2,
    Categorie.JUNIOR_SUITE: 3,
    Categorie.SUITE: 4,
}

DISTRIBUTION_GRAVITES: dict[Gravite, float] = {
    Gravite.MINEURE: 0.45,
    Gravite.MODEREE: 0.35,
    Gravite.MAJEURE: 0.15,
    Gravite.CRITIQUE: 0.05,
}

INCIDENTS_BLOQUANTS: frozenset[TypeIncident] = frozenset(
    {
        TypeIncident.DEGAT_DES_EAUX,
        TypeIncident.RISQUE_SECURITE,
        TypeIncident.PANNE_ELECTRIQUE,
    }
)

CHAMBRES_PAR_AGENT = 15
COMPETENCE_SUITE = "suite"
SECTEUR_RESERVE = "presidentielle"


@dataclass(frozen=True, slots=True)
class ProfilDEtablissement:
    """Parametres de constitution d'un etablissement."""

    nom: str
    chambres: int
    etages: int
    taux_occupation: float = 0.78
    part_incidents: float = 0.03
    part_pmr: float = 0.04
    part_communicantes: float = 0.10
    part_arrivees_a_traiter: float = 0.15
    agents_par_secteur: int | None = None
    part_agents_indisponibles: float = 0.12
    horizon_jours: int = 14
    heure_de_reference: time = time(10, 0)
    graine: int = 20260812

    def __post_init__(self) -> None:
        if self.chambres < 1:
            raise ValeurDeProfilInvalideError("un etablissement comporte des chambres")
        if self.etages < 1:
            raise ValeurDeProfilInvalideError("un etablissement comporte des etages")
        if not 0.0 <= self.taux_occupation <= 1.0:
            raise ValeurDeProfilInvalideError(
                "le taux d'occupation appartient a l'intervalle [0, 1]"
            )
        if not 0.0 <= self.part_incidents <= 1.0:
            raise ValeurDeProfilInvalideError(
                "la part d'incidents appartient a l'intervalle [0, 1]"
            )

    @property
    def chambres_par_etage(self) -> int:
        return max(1, self.chambres // self.etages)


class ValeurDeProfilInvalideError(ValueError):
    """Signale un profil dont les parametres sont incoherents."""


@dataclass(frozen=True, slots=True)
class Etablissement:
    """Etat operationnel complet d'un etablissement engendre."""

    profil: ProfilDEtablissement
    parc: tuple[tuple[Chambre, str], ...] = ()
    clients: tuple[Client, ...] = ()
    reservations: tuple[Reservation, ...] = ()
    incidents: tuple[Incident, ...] = ()
    agents: tuple[tuple[AgentEtage, frozenset[str]], ...] = ()
    taches: tuple[tuple[TacheNettoyage, frozenset[str]], ...] = ()
    secteurs_reserves: tuple[str, ...] = ()
    jour_de_reference: date = field(default_factory=date.today)

    @property
    def chambres(self) -> tuple[Chambre, ...]:
        return tuple(chambre for chambre, _ in self.parc)

    @property
    def secteurs(self) -> tuple[str, ...]:
        return tuple(sorted({secteur for _, secteur in self.parc}))

    def resumer(self) -> dict[str, int]:
        """Restitue les grandeurs caracteristiques de l'etablissement."""
        disponibles = sum(1 for chambre in self.chambres if chambre.est_attribuable)
        return {
            "chambres": len(self.parc),
            "disponibles": disponibles,
            "reservations": len(self.reservations),
            "sans_chambre": sum(
                1 for sejour in self.reservations if not sejour.est_affectee
            ),
            "incidents_ouverts": sum(
                1 for incident in self.incidents if incident.est_ouvert
            ),
            "agents": len(self.agents),
            "agents_indisponibles": sum(
                1 for agent, _ in self.agents if not agent.est_affectable
            ),
            "taches": len(self.taches),
        }


class GenerateurDEtablissement:
    """Constitue un etablissement coherent a partir d'un profil."""

    def __init__(self, profil: ProfilDEtablissement) -> None:
        self._profil = profil
        self._sort = Random(profil.graine)

    def engendrer(self, jour: date | None = None) -> Etablissement:
        """Produit l'etat operationnel complet d'un etablissement."""
        reference = jour or date(2026, 8, 12)

        parc = self._engendrer_parc()
        chambres = [chambre for chambre, _ in parc]
        secteurs = {str(chambre.numero): secteur for chambre, secteur in parc}

        clients = self._engendrer_clients(len(chambres))
        reservations = self._engendrer_reservations(chambres, clients, reference)
        incidents = self._engendrer_incidents(chambres, reference)
        parc = self._appliquer_incidents(parc, incidents)
        parc = self._appliquer_occupations(parc, reservations, reference)

        agents = self._engendrer_agents(sorted(set(secteurs.values())))
        taches = self._engendrer_taches(parc, reservations, reference)

        etablissement = Etablissement(
            profil=self._profil,
            parc=tuple(parc),
            clients=tuple(clients),
            reservations=tuple(reservations),
            incidents=tuple(incidents),
            agents=tuple(agents),
            taches=tuple(taches),
            secteurs_reserves=(SECTEUR_RESERVE,),
            jour_de_reference=reference,
        )
        logger.info(
            "etablissement %s engendre: %s",
            self._profil.nom,
            etablissement.resumer(),
        )
        return etablissement

    def _engendrer_parc(self) -> list[tuple[Chambre, str]]:
        """Constitue le parc, ses categories, equipements et voisinages.

        Les chambres accessibles sont concentrees aux etages bas, conformement
        a l'implantation habituelle des etablissements.
        """
        parc: list[tuple[Chambre, str]] = []
        par_etage = self._profil.chambres_par_etage
        numeros_par_etage: dict[int, list[str]] = {}

        for rang in range(self._profil.chambres):
            etage = min(rang // par_etage + 1, self._profil.etages)
            position = rang % par_etage + 1
            numero = f"{etage}{position:02d}"
            numeros_par_etage.setdefault(etage, []).append(numero)

            categorie = self._tirer_categorie(etage)
            equipements = set(EQUIPEMENTS_PAR_CATEGORIE[categorie])
            equipements.add(self._tirer_literie(categorie))

            if etage <= 2 and self._sort.random() < self._profil.part_pmr * 3:
                equipements.add(Equipement.ACCES_PMR)
            if etage >= self._profil.etages - 1 and categorie >= Categorie.SUPERIEURE:
                equipements.add(Equipement.BALCON)

            secteur = (
                SECTEUR_RESERVE
                if categorie is Categorie.SUITE and etage == self._profil.etages
                else f"etage_{etage}"
            )

            parc.append(
                (
                    Chambre(
                        numero=NumeroChambre(numero),
                        etage=etage,
                        capacite=CAPACITE_PAR_CATEGORIE[categorie],
                        categorie=categorie,
                        equipements=frozenset(equipements),
                        etat_proprete=self._tirer_proprete(),
                        etat_technique=EtatTechnique.OPERATIONNELLE,
                        etat_occupation=EtatOccupation.LIBRE,
                    ),
                    secteur,
                )
            )

        return self._relier_communicantes(parc, numeros_par_etage)

    def _relier_communicantes(
        self, parc: list[tuple[Chambre, str]], par_etage: dict[int, list[str]]
    ) -> list[tuple[Chambre, str]]:
        """Etablit les communications entre chambres voisines d'un meme etage."""
        voisinages: dict[str, set[str]] = {}
        for numeros in par_etage.values():
            for gauche, droite in zip(numeros, numeros[1:], strict=False):
                if self._sort.random() < self._profil.part_communicantes:
                    voisinages.setdefault(gauche, set()).add(droite)
                    voisinages.setdefault(droite, set()).add(gauche)

        return [
            (
                chambre
                if str(chambre.numero) not in voisinages
                else Chambre(
                    numero=chambre.numero,
                    etage=chambre.etage,
                    capacite=chambre.capacite,
                    categorie=chambre.categorie,
                    equipements=chambre.equipements,
                    etat_proprete=chambre.etat_proprete,
                    etat_technique=chambre.etat_technique,
                    etat_occupation=chambre.etat_occupation,
                    chambres_communicantes=frozenset(
                        NumeroChambre(voisine)
                        for voisine in voisinages[str(chambre.numero)]
                    ),
                ),
                secteur,
            )
            for chambre, secteur in parc
        ]

    def _tirer_categorie(self, etage: int) -> Categorie:
        """Tire une categorie, les plus elevees etant plus frequentes en haut."""
        tirage = self._sort.random()
        if etage >= self._profil.etages:
            tirage *= 0.5
        cumul = 0.0
        for categorie, part in DISTRIBUTION_CATEGORIES.items():
            cumul += part
            if tirage < cumul:
                return categorie
        return Categorie.STANDARD

    def _tirer_literie(self, categorie: Categorie) -> Equipement:
        if categorie >= Categorie.JUNIOR_SUITE:
            return Equipement.LIT_KING
        return self._sort.choice([Equipement.LIT_DOUBLE, Equipement.LIT_SIMPLE])

    def _tirer_proprete(self) -> EtatProprete:
        """Tire un etat de proprete conforme au moment de la journee.

        Le matin, les departs viennent d'avoir lieu et une part importante du
        parc demeure a traiter; l'apres-midi, la plupart des chambres sont
        pretes.
        """
        matinal = self._profil.heure_de_reference < time(14, 0)
        parts = (
            [
                (EtatProprete.SALE, 0.35),
                (EtatProprete.EN_NETTOYAGE, 0.20),
                (EtatProprete.A_CONTROLER, 0.10),
                (EtatProprete.PRETE, 0.35),
            ]
            if matinal
            else [
                (EtatProprete.SALE, 0.10),
                (EtatProprete.EN_NETTOYAGE, 0.08),
                (EtatProprete.A_CONTROLER, 0.07),
                (EtatProprete.PRETE, 0.75),
            ]
        )
        tirage = self._sort.random()
        cumul = 0.0
        for etat, part in parts:
            cumul += part
            if tirage < cumul:
                return etat
        return EtatProprete.PRETE

    def _engendrer_clients(self, effectif: int) -> list[Client]:
        """Constitue une clientele dont une part detient un statut de fidelite."""
        clients: list[Client] = []
        for rang in range(1, int(effectif * 1.4) + 1):
            statut = self._sort.choices(
                list(StatutFidelite),
                weights=[0.55, 0.20, 0.12, 0.09, 0.04],
                k=1,
            )[0]
            besoins = (
                frozenset({Equipement.ACCES_PMR})
                if self._sort.random() < 0.05
                else frozenset()
            )
            clients.append(
                Client(
                    identifiant=f"C-{rang:05d}",
                    statut_fidelite=statut,
                    besoins_permanents=besoins,
                )
            )
        return clients

    def _engendrer_reservations(
        self, chambres: Sequence[Chambre], clients: Sequence[Client], jour: date
    ) -> list[Reservation]:
        """Constitue les sejours couvrant l'horizon, affectes ou en attente.

        Les caracteristiques exigees sont tirees d'une chambre existante: la
        demande demeure ainsi calquee sur l'offre du parc, comme en
        exploitation ou l'on ne vend que ce que l'on possede.
        """
        duree_moyenne = 2.6
        attendus = int(
            len(chambres)
            * self._profil.taux_occupation
            * self._profil.horizon_jours
            / duree_moyenne
        )
        reservations: list[Reservation] = []

        for rang in range(1, attendus + 1):
            decalage = self._sort.randint(-2, self._profil.horizon_jours - 1)
            duree = self._sort.choices([1, 2, 3, 4, 7], weights=[0.2, 0.3, 0.25, 0.15, 0.1])[0]
            arrivee = jour + timedelta(days=decalage)
            client = self._sort.choice(list(clients))
            reference = self._tirer_chambre_de_reference(chambres, client)
            categorie = reference.categorie

            exigences = set()
            if client.besoins_permanents:
                exigences.add(Exigence(Equipement.ACCES_PMR, obligatoire=True))
            if self._sort.random() < 0.35:
                literie = next(
                    (
                        equipement
                        for equipement in reference.equipements
                        if equipement
                        in (
                            Equipement.LIT_SIMPLE,
                            Equipement.LIT_DOUBLE,
                            Equipement.LIT_KING,
                        )
                    ),
                    Equipement.LIT_DOUBLE,
                )
                exigences.add(Exigence(literie, obligatoire=True))
            if self._sort.random() < 0.30:
                exigences.add(Exigence(Equipement.BALCON, obligatoire=False))

            heure_prevue = time(self._sort.randint(12, 21), self._sort.choice([0, 15, 30, 45]))

            reservations.append(
                Reservation(
                    identifiant=IdentifiantReservation(f"R-{rang:05d}"),
                    client=client,
                    periode=Periode(arrivee=arrivee, depart=arrivee + timedelta(days=duree)),
                    nombre_personnes=self._sort.randint(
                        1, min(reference.capacite, 4)
                    ),
                    categorie_contractee=categorie,
                    heure_arrivee=HeureArrivee(prevue=heure_prevue, contractuelle=time(15, 0)),
                    exigences=frozenset(exigences),
                )
            )

        return self._affecter_sejours(reservations, chambres, jour)

    def _tirer_chambre_de_reference(
        self, chambres: Sequence[Chambre], client: Client
    ) -> Chambre:
        """Tire la chambre sur laquelle sont calquees les exigences d'un sejour.

        La chambre retenue satisfait les besoins permanents du client: sans
        cette precaution, un sejour pourrait exiger un equipement que la
        chambre de reference ne possede pas, et ne trouver aucune chambre
        compatible dans le parc.
        """
        if not client.besoins_permanents:
            return self._sort.choice(list(chambres))

        compatibles = [
            chambre
            for chambre in chambres
            if client.besoins_permanents <= chambre.equipements
        ]
        return self._sort.choice(compatibles or list(chambres))

    def _affecter_sejours(
        self, reservations: list[Reservation], chambres: Sequence[Chambre], jour: date
    ) -> list[Reservation]:
        """Affecte une chambre aux sejours, en menageant des cas a traiter.

        L'attribution intervient a la reservation et non a l'arrivee: un sejour
        futur dispose donc deja d'une chambre. Demeurent sans chambre les
        sejours dont aucune chambre ne satisfait les exigences, ainsi qu'une
        part des arrivees du jour: ce sont eux que le systeme aura a traiter.

        Les sejours sont traites par date d'arrivee croissante, de sorte que
        l'occupation se constitue chronologiquement comme en exploitation.
        """
        occupees: dict[str, list[Periode]] = {}
        affectees: list[Reservation] = []

        for reservation in sorted(reservations, key=lambda r: r.periode.arrivee):
            if (
                reservation.periode.arrivee == jour
                and self._sort.random() < self._profil.part_arrivees_a_traiter
            ):
                affectees.append(reservation)
                continue

            candidates = [
                chambre
                for chambre in chambres
                if chambre.capacite >= reservation.nombre_personnes
                and chambre.categorie >= reservation.categorie_contractee
                and reservation.exigences_obligatoires <= chambre.equipements
                and not any(
                    periode.chevauche(reservation.periode)
                    for periode in occupees.get(str(chambre.numero), [])
                )
            ]
            if not candidates:
                affectees.append(reservation)
                continue

            retenue = self._sort.choice(candidates)
            occupees.setdefault(str(retenue.numero), []).append(reservation.periode)
            affectees.append(reservation.avec_chambre(retenue.numero))

        return affectees

    def _engendrer_incidents(
        self, chambres: Sequence[Chambre], jour: date
    ) -> list[Incident]:
        """Constitue les incidents affectant une part du parc."""
        attendus = max(1, int(len(chambres) * self._profil.part_incidents))
        concernees = self._sort.sample(list(chambres), k=min(attendus, len(chambres)))

        incidents: list[Incident] = []
        for rang, chambre in enumerate(concernees, start=1):
            gravite = self._sort.choices(
                list(DISTRIBUTION_GRAVITES),
                weights=list(DISTRIBUTION_GRAVITES.values()),
                k=1,
            )[0]
            incidents.append(
                Incident(
                    identifiant=f"I-{rang:05d}",
                    chambre=chambre.numero,
                    type_incident=self._sort.choice(list(TypeIncident)),
                    gravite=gravite,
                    signale_le=datetime.combine(
                        jour, time(self._sort.randint(6, 20), self._sort.randint(0, 59))
                    ),
                    description="",
                    resolu=self._sort.random() < 0.25,
                )
            )
        return incidents

    @staticmethod
    def _appliquer_incidents(
        parc: list[tuple[Chambre, str]], incidents: Sequence[Incident]
    ) -> list[tuple[Chambre, str]]:
        """Repercute les incidents ouverts sur l'etat technique des chambres.

        Un incident grave et bloquant immobilise la chambre; les autres la
        degradent sans l'empecher de recevoir un client.
        """
        etats: dict[str, EtatTechnique] = {}
        for incident in incidents:
            if not incident.est_ouvert:
                continue
            bloquant = (
                incident.type_incident in INCIDENTS_BLOQUANTS
                and incident.gravite >= Gravite.MAJEURE
            )
            etats[str(incident.chambre)] = (
                EtatTechnique.BLOQUEE if bloquant else EtatTechnique.DEGRADEE
            )

        return [
            (
                chambre.avec_etat_technique(etats[str(chambre.numero)])
                if str(chambre.numero) in etats
                else chambre,
                secteur,
            )
            for chambre, secteur in parc
        ]

    @staticmethod
    def _appliquer_occupations(
        parc: list[tuple[Chambre, str]],
        reservations: Sequence[Reservation],
        jour: date,
    ) -> list[tuple[Chambre, str]]:
        """Repercute les sejours en cours sur l'etat d'occupation des chambres."""
        occupees = {
            str(reservation.chambre_affectee)
            for reservation in reservations
            if reservation.chambre_affectee is not None
            and reservation.periode.contient(jour)
        }
        return [
            (
                chambre.avec_etat_occupation(EtatOccupation.OCCUPEE)
                if str(chambre.numero) in occupees
                else chambre,
                secteur,
            )
            for chambre, secteur in parc
        ]

    def _engendrer_agents(
        self, secteurs: Sequence[str]
    ) -> list[tuple[AgentEtage, frozenset[str]]]:
        """Constitue l'effectif d'etage, dimensionne sur la charge du parc."""
        par_secteur = self._profil.agents_par_secteur or max(
            1, self._profil.chambres_par_etage // CHAMBRES_PAR_AGENT + 1
        )
        agents: list[tuple[AgentEtage, frozenset[str]]] = []
        rang = 0

        for secteur in secteurs:
            for _ in range(par_secteur):
                rang += 1
                indisponible = self._sort.random() < self._profil.part_agents_indisponibles
                disponibilite = (
                    self._sort.choice(
                        [DisponibiliteAgent.ABSENT, DisponibiliteAgent.RETARD]
                    )
                    if indisponible
                    else DisponibiliteAgent.PRESENT
                )
                qualifications = (
                    frozenset({COMPETENCE_SUITE})
                    if secteur == SECTEUR_RESERVE or self._sort.random() < 0.30
                    else frozenset()
                )
                agents.append(
                    (
                        AgentEtage(
                            identifiant=IdentifiantAgent(f"A-{rang:04d}"),
                            secteur=Secteur(secteur),
                            plage=PlageDeService(debut=time(8, 0), fin=time(16, 0)),
                            disponibilite=disponibilite,
                            minutes_deja_affectees=self._sort.choice([0, 0, 0, 60, 120]),
                        ),
                        qualifications,
                    )
                )
        return agents

    def _engendrer_taches(
        self,
        parc: Sequence[tuple[Chambre, str]],
        reservations: Sequence[Reservation],
        jour: date,
    ) -> list[tuple[TacheNettoyage, frozenset[str]]]:
        """Constitue les prestations de nettoyage du jour.

        Une chambre attendue par une arrivee recoit une echeance: elle doit
        etre prete avant l'heure d'acces contractuelle.
        """
        attendues = {
            str(reservation.chambre_affectee): reservation
            for reservation in reservations
            if reservation.chambre_affectee is not None
            and reservation.periode.arrivee == jour
        }

        taches: list[tuple[TacheNettoyage, frozenset[str]]] = []
        rang = 0

        for chambre, secteur in parc:
            if chambre.etat_proprete is EtatProprete.PRETE:
                continue
            rang += 1
            reservation = attendues.get(str(chambre.numero))
            prestation = (
                TypePrestation.REMISE_EN_ETAT
                if chambre.etat_technique is EtatTechnique.DEGRADEE
                else TypePrestation.DEPART
                if chambre.etat_occupation is EtatOccupation.LIBRE
                else TypePrestation.RECOUCHE
            )
            priorite = (
                PrioriteTache.URGENTE
                if reservation is not None
                and reservation.heure_arrivee.est_anticipee()
                else PrioriteTache.ELEVEE
                if reservation is not None
                else PrioriteTache.NORMALE
            )
            qualifications = (
                frozenset({COMPETENCE_SUITE})
                if chambre.categorie is Categorie.SUITE
                else frozenset()
            )

            taches.append(
                (
                    TacheNettoyage(
                        identifiant=f"T-{rang:05d}",
                        chambre=chambre.numero,
                        prestation=prestation,
                        secteur=Secteur(secteur),
                        echeance=(
                            reservation.heure_arrivee.contractuelle
                            if reservation is not None
                            else None
                        ),
                        priorite=priorite,
                        statut=StatutTache.A_PLANIFIER,
                    ),
                    qualifications,
                )
            )
        return taches


def engendrer_etablissement(
    profil: ProfilDEtablissement, jour: date | None = None
) -> Etablissement:
    """Constitue un etablissement a partir d'un profil."""
    return GenerateurDEtablissement(profil).engendrer(jour)
