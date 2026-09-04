/**
 * Contrat d'echange avec le noyau de raisonnement.
 *
 * Les types reproduisent les schemas exposes par l'interface de programmation.
 * Toute evolution du contrat cote noyau doit etre reportee ici: le compilateur
 * signale alors les usages devenus incorrects.
 */

export type Categorie = 1 | 2 | 3 | 4;
export type Priorite = 1 | 2 | 3;

export type EtatProprete = "sale" | "en_nettoyage" | "a_controler" | "prete";
export type EtatTechnique = "operationnelle" | "degradee" | "bloquee";
export type EtatOccupation = "libre" | "attribuee" | "occupee";
export type Disponibilite = "present" | "retard" | "absent";
export type Prestation = "recouche" | "depart" | "remise_en_etat";

export type Equipement =
  | "lit_simple"
  | "lit_double"
  | "lit_king"
  | "acces_pmr"
  | "baignoire"
  | "balcon"
  | "climatisation"
  | "coffre_fort";

export interface Exigence {
  equipement: Equipement;
  obligatoire: boolean;
}

export interface ChambreEntrante {
  numero: string;
  etage: number;
  capacite: number;
  categorie: Categorie;
  equipements: Equipement[];
  etat_proprete: EtatProprete;
  etat_technique: EtatTechnique;
  etat_occupation: EtatOccupation;
  chambres_communicantes: string[];
}

export interface ReservationEntrante {
  identifiant: string;
  client: string;
  statut_fidelite: number;
  arrivee: string;
  depart: string;
  nombre_personnes: number;
  categorie_contractee: Categorie;
  heure_arrivee_prevue: string;
  heure_acces_contractuelle: string;
  exigences: Exigence[];
  chambre_affectee: string | null;
}

export interface DemandeAffectation {
  parc: ChambreEntrante[];
  reservation: ReservationEntrante;
  occupations?: ReservationEntrante[];
  poids?: Record<string, number> | null;
  temps_maximal?: number | null;
}

export interface Motif {
  code: string;
  detail: string | null;
}

export interface OptionEcartee {
  chambre: string;
  motifs: Motif[];
  formulations: string[];
}

export interface Contrepartie {
  code: string;
  poids: number;
  formulation: string;
}

export interface Recommandation {
  a_conclu: boolean;
  chambre_proposee: string | null;
  justification: string;
  chambres_examinees: number;
  chambres_admissibles: string[];
  cout: number;
  optimal: boolean;
  sous_reserve: boolean;
  contreparties: Contrepartie[];
  options_ecartees: OptionEcartee[];
}

export interface AgentEntrant {
  identifiant: string;
  secteur: string;
  debut_service: string;
  fin_service: string;
  disponibilite: Disponibilite;
  minutes_deja_affectees: number;
  competences: string[];
}

export interface TacheEntrante {
  identifiant: string;
  chambre: string;
  prestation: Prestation;
  secteur: string;
  echeance: string | null;
  priorite: Priorite;
  duree_minutes: number;
  competences_requises: string[];
}

export interface DemandePlanification {
  agents: AgentEntrant[];
  taches: TacheEntrante[];
  secteurs_reserves?: string[];
  poids?: Record<string, number> | null;
  temps_maximal?: number | null;
}

export interface Affectation {
  tache: string;
  agent: string;
  debut: string;
  fin: string;
  duree_minutes: number;
}

export type CauseAttente = "aucun_agent_admissible" | "capacite_insuffisante";

export interface TacheEnAttente {
  tache: string;
  cause: CauseAttente;
  motifs: string[];
}

export interface Charge {
  agent: string;
  minutes: number;
}

export interface Planification {
  est_complete: boolean;
  justification: string[];
  affectations: Affectation[];
  taches_en_attente: TacheEnAttente[];
  charges: Charge[];
  cout: number;
  optimal: boolean;
  sous_reserve: boolean;
}

export interface Anomalie {
  code: string;
  message: string;
}

/* Consultation de l'etat de l'etablissement */

export interface ChambreConsultee {
  numero: string;
  etage: number;
  capacite: number;
  categorie: Categorie;
  categorie_libelle: string;
  equipements: Equipement[];
  etat_proprete: EtatProprete;
  etat_technique: EtatTechnique;
  etat_occupation: EtatOccupation;
  attribuable: boolean;
  chambres_communicantes: string[];
}

export interface ReservationConsultee {
  identifiant: string;
  client: string;
  statut_fidelite: number;
  arrivee: string;
  depart: string;
  nuitees: number;
  nombre_personnes: number;
  categorie_contractee: Categorie;
  heure_arrivee_prevue: string;
  heure_acces_contractuelle: string;
  arrivee_anticipee: boolean;
  exigences_obligatoires: Equipement[];
  exigences_souhaitees: Equipement[];
  chambre_affectee: string | null;
}

export interface AgentConsulte {
  identifiant: string;
  secteur: string;
  debut_service: string;
  fin_service: string;
  disponibilite: Disponibilite;
  minutes_restantes: number;
  affectable: boolean;
  competences: string[];
}

export interface TacheConsultee {
  identifiant: string;
  chambre: string;
  prestation: Prestation;
  secteur: string;
  echeance: string | null;
  priorite: Priorite;
  statut: string;
  duree_minutes: number;
  competences_requises: string[];
}

export interface IncidentConsulte {
  identifiant: string;
  chambre: string;
  type_incident: string;
  gravite: number;
  signale_le: string;
  description: string;
  resolu: boolean;
}

export interface EtatDeLEtablissement {
  jour: string;
  chambres: number;
  disponibles: number;
  arrivees_a_traiter: number;
  incidents_ouverts: number;
  taches_a_planifier: number;
  agents_affectables: number;
}

export interface ParametresDeDecision {
  poids?: Record<string, number> | null;
  temps_maximal?: number | null;
}

/* Interpretation d'enonces libres */

export type Recevabilite = "recevable" | "a_confirmer" | "irrecevable";

export interface EntiteLue {
  type_d_entite: string;
  valeur: string;
  confiance: number;
  existe: boolean | null;
}

export interface ReserveExprimee {
  motif: string;
  detail: string;
}

export interface LectureRestituee {
  enonce: string;
  intention: string;
  confiance: number;
  entites: EntiteLue[];
  reserves: ReserveExprimee[];
  recevabilite: Recevabilite;
  modele: string;
}

export interface EnonceSoumis {
  enonce: string;
  confiance_minimale?: number | null;
}

/* Traitement d'incident */

export type TypeIncident =
  | "degat_des_eaux"
  | "panne_electrique"
  | "panne_climatisation"
  | "panne_plomberie"
  | "defaut_serrure"
  | "mobilier_endommage"
  | "nuisance_sonore"
  | "risque_securite";

export type Gravite = 1 | 2 | 3 | 4;

export interface IncidentSignale {
  chambre: string;
  type_incident: TypeIncident;
  gravite?: Gravite;
  description?: string;
  jour?: string | null;
  temps_maximal?: number | null;
}

export interface RelogementPropose {
  reservation: string;
  client: string;
  arrivee: string;
  depart: string;
  nombre_personnes: number;
  chambre_proposee: string | null;
  a_trouve_une_chambre: boolean;
  justification: string;
  chambres_examinees: number;
  chambres_admissibles: number;
  motifs_dominants: string[];
}

export interface ConsequencesRestituees {
  chambre: string;
  immobilise_la_chambre: boolean;
  justification: string[];
  sejours_a_reloger: RelogementPropose[];
  nombre_de_sejours: number;
  sejours_sans_solution: number;
  est_entierement_resolu: boolean;
  demande_une_intervention: boolean;
}

/* Demandes en langue naturelle */

export type NatureDeLaReponse =
  | "consultation"
  | "arbitrage"
  | "consequences"
  | "confirmation_requise"
  | "hors_perimetre";

export interface DemandeSoumise {
  enonce: string;
  jour?: string | null;
  temps_maximal?: number | null;
}

export interface EtatRestitue {
  enonce: string;
  elements: string[];
  nombre: number | null;
}

export interface LevierRestitue {
  relachement: string;
  enonce: string;
  chambres_ainsi_ouvertes: number;
}

export interface ArbitrageRestitue {
  nature: string;
  chambre: string;
  sejour_maintenu: string | null;
  sejour_a_reloger: string | null;
  motif: string;
  chambre_proposee: string | null;
  justification: string;
  constats: string[];
  leviers: LevierRestitue[];
  anomalie: boolean;
  demande_une_intervention: boolean;
}

export interface ReponseRestituee {
  nature: NatureDeLaReponse;
  lecture: LectureRestituee;
  etat: EtatRestitue | null;
  arbitrage: ArbitrageRestitue | null;
  consequences: ConsequencesRestituees | null;
  message: string;
}
