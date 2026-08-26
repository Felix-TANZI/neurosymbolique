/**
 * Jour de reference de la consultation.
 *
 * L'etablissement engendre porte une date de reference qui peut differer du
 * jour courant. Le jour consulte est donc un parametre explicite plutot qu'une
 * valeur implicite, ce qui permet d'examiner une journee passee ou a venir.
 */

const JOUR_DE_DEMONSTRATION = "2026-08-12";

export function jourParDefaut(): string {
  return JOUR_DE_DEMONSTRATION;
}

export function enJourLisible(iso: string): string {
  const [annee, mois, jour] = iso.split("-");
  return `${jour}/${mois}/${annee}`;
}

export function enHeureLisible(heure: string): string {
  const [heures, minutes] = heure.split(":");
  return `${heures}h${minutes}`;
}
