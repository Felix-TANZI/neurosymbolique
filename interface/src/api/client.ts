/**
 * Acces au noyau de raisonnement.
 *
 * Les appels transitent par le prefixe /api, relaye vers le noyau. Toute
 * anomalie est convertie en erreur portant le code et le message restitues
 * par le noyau, de sorte que l'interface puisse orienter l'utilisateur.
 */

import type {
  Anomalie,
  DemandeAffectation,
  DemandePlanification,
  Planification,
  Recommandation,
} from "./contrat";

const RACINE = "/api";

export class ErreurDeNoyau extends Error {
  readonly code: string;
  readonly statut: number;

  constructor(code: string, message: string, statut: number) {
    super(message);
    this.name = "ErreurDeNoyau";
    this.code = code;
    this.statut = statut;
  }

  get estIndisponibilite(): boolean {
    return this.statut === 503;
  }

  get estDemandeInvalide(): boolean {
    return this.statut === 422;
  }
}

async function lireAnomalie(reponse: Response): Promise<ErreurDeNoyau> {
  let code = "anomalie_inconnue";
  let message = `Le noyau a repondu ${reponse.status}.`;

  try {
    const contenu = (await reponse.json()) as { detail?: Anomalie | unknown };
    const detail = contenu.detail;
    if (detail && typeof detail === "object" && "code" in detail) {
      const anomalie = detail as Anomalie;
      code = anomalie.code;
      message = anomalie.message;
    } else if (Array.isArray(detail)) {
      code = "demande_invalide";
      message = "Une valeur soumise n'est pas conforme au contrat attendu.";
    }
  } catch {
    // La reponse ne comporte pas de corps exploitable.
  }

  return new ErreurDeNoyau(code, message, reponse.status);
}

async function envoyer<E, S>(chemin: string, corps: E): Promise<S> {
  const reponse = await fetch(`${RACINE}${chemin}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corps),
  });

  if (!reponse.ok) {
    throw await lireAnomalie(reponse);
  }

  return (await reponse.json()) as S;
}

export async function verifierDisponibilite(): Promise<{ disponible: true }> {
  const reponse = await fetch(`${RACINE}/sante`, { cache: "no-store" });
  if (!reponse.ok) {
    throw await lireAnomalie(reponse);
  }
  return { disponible: true };
}

export function recommanderChambre(
  demande: DemandeAffectation,
): Promise<Recommandation> {
  return envoyer<DemandeAffectation, Recommandation>("/affectations", demande);
}

export function planifierNettoyage(
  demande: DemandePlanification,
): Promise<Planification> {
  return envoyer<DemandePlanification, Planification>(
    "/planifications",
    demande,
  );
}