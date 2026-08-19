/**
 * Situations de reference pour l'analyse.
 *
 * Les scenarios permettent de soumettre une situation complete sans saisie
 * prealable. Ils reproduisent des cas d'exploitation courants et servent
 * egalement de point de depart a une saisie modifiee.
 */

import type { DemandeAffectation, DemandePlanification } from "@/api/contrat";

export const AFFECTATION_APRES_INCIDENT: DemandeAffectation = {
  parc: [
    {
      numero: "312",
      etage: 3,
      capacite: 2,
      categorie: 1,
      equipements: ["lit_double"],
      etat_proprete: "prete",
      etat_technique: "bloquee",
      etat_occupation: "libre",
      chambres_communicantes: [],
    },
    {
      numero: "405",
      etage: 4,
      capacite: 2,
      categorie: 1,
      equipements: ["lit_double", "balcon"],
      etat_proprete: "a_controler",
      etat_technique: "operationnelle",
      etat_occupation: "libre",
      chambres_communicantes: [],
    },
    {
      numero: "407",
      etage: 4,
      capacite: 2,
      categorie: 1,
      equipements: ["lit_double"],
      etat_proprete: "prete",
      etat_technique: "operationnelle",
      etat_occupation: "libre",
      chambres_communicantes: [],
    },
    {
      numero: "512",
      etage: 5,
      capacite: 4,
      categorie: 4,
      equipements: ["lit_double", "balcon"],
      etat_proprete: "prete",
      etat_technique: "operationnelle",
      etat_occupation: "libre",
      chambres_communicantes: [],
    },
    {
      numero: "201",
      etage: 2,
      capacite: 1,
      categorie: 1,
      equipements: ["lit_simple"],
      etat_proprete: "prete",
      etat_technique: "operationnelle",
      etat_occupation: "libre",
      chambres_communicantes: [],
    },
  ],
  reservation: {
    identifiant: "R-4471",
    client: "C-001",
    statut_fidelite: 3,
    arrivee: "2026-08-12",
    depart: "2026-08-15",
    nombre_personnes: 2,
    categorie_contractee: 1,
    heure_arrivee_prevue: "16:00",
    heure_acces_contractuelle: "15:00",
    exigences: [
      { equipement: "lit_double", obligatoire: true },
      { equipement: "balcon", obligatoire: false },
    ],
    chambre_affectee: null,
  },
  occupations: [],
};

export const AFFECTATION_SANS_ISSUE: DemandeAffectation = {
  ...AFFECTATION_APRES_INCIDENT,
  parc: AFFECTATION_APRES_INCIDENT.parc.map((chambre) => ({
    ...chambre,
    etat_technique: "bloquee" as const,
  })),
};

export const SERVICE_ETAGE: DemandePlanification = {
  agents: [
    {
      identifiant: "A-001",
      secteur: "etage_4",
      debut_service: "08:00",
      fin_service: "16:00",
      disponibilite: "present",
      minutes_deja_affectees: 0,
      competences: [],
    },
    {
      identifiant: "A-002",
      secteur: "etage_5",
      debut_service: "08:00",
      fin_service: "16:00",
      disponibilite: "absent",
      minutes_deja_affectees: 0,
      competences: [],
    },
    {
      identifiant: "A-003",
      secteur: "etage_5",
      debut_service: "08:00",
      fin_service: "16:00",
      disponibilite: "present",
      minutes_deja_affectees: 0,
      competences: ["suite"],
    },
  ],
  taches: [
    {
      identifiant: "T-001",
      chambre: "407",
      prestation: "depart",
      secteur: "etage_4",
      echeance: "13:00",
      priorite: 3,
      duree_minutes: 0,
      competences_requises: [],
    },
    {
      identifiant: "T-002",
      chambre: "405",
      prestation: "recouche",
      secteur: "etage_4",
      echeance: null,
      priorite: 1,
      duree_minutes: 0,
      competences_requises: [],
    },
    {
      identifiant: "T-003",
      chambre: "512",
      prestation: "remise_en_etat",
      secteur: "presidentielle",
      echeance: null,
      priorite: 2,
      duree_minutes: 0,
      competences_requises: ["suite"],
    },
    {
      identifiant: "T-004",
      chambre: "501",
      prestation: "depart",
      secteur: "etage_5",
      echeance: null,
      priorite: 1,
      duree_minutes: 0,
      competences_requises: [],
    },
  ],
  secteurs_reserves: ["presidentielle"],
};

export const SERVICE_SATURE: DemandePlanification = {
  ...SERVICE_ETAGE,
  agents: [SERVICE_ETAGE.agents[0]!],
  taches: Array.from({ length: 9 }, (_, rang) => ({
    identifiant: `T-${String(rang + 1).padStart(3, "0")}`,
    chambre: `${400 + rang}`,
    prestation: "remise_en_etat" as const,
    secteur: "etage_4",
    echeance: null,
    priorite: 1 as const,
    duree_minutes: 0,
    competences_requises: [],
  })),
  secteurs_reserves: [],
};