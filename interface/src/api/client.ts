/**
 * Acces au noyau de raisonnement.
 *
 * Les appels transitent par le prefixe /api, relaye vers le noyau. Toute
 * anomalie est convertie en erreur portant le code et le message restitues
 * par le noyau, de sorte que l'interface puisse orienter l'utilisateur.
 */

import type {
  AgentConsulte,
  Anomalie,
  ChambreConsultee,
  DemandeAffectation,
  DemandePlanification,
  EnonceSoumis,
  EtatDeLEtablissement,
  IncidentConsulte,
  LectureRestituee,
  ParametresDeDecision,
  Planification,
  Recommandation,
  ReservationConsultee,
  TacheConsultee,
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

async function lire<S>(chemin: string): Promise<S> {
  const reponse = await fetch(`${RACINE}${chemin}`, { cache: "no-store" });

  if (!reponse.ok) {
    throw await lireAnomalie(reponse);
  }

  return (await reponse.json()) as S;
}

function parametres(entrees: Record<string, string | boolean | undefined>): string {
  const retenues = Object.entries(entrees).filter(
    ([, valeur]) => valeur !== undefined && valeur !== false,
  );
  if (retenues.length === 0) {
    return "";
  }
  const chaine = new URLSearchParams(
    retenues.map(([cle, valeur]) => [cle, String(valeur)]),
  );
  return `?${chaine.toString()}`;
}

export function consulterEtablissement(
  jour: string,
): Promise<EtatDeLEtablissement> {
  return lire<EtatDeLEtablissement>(`/etablissement${parametres({ jour })}`);
}

export function consulterChambres(options: {
  secteur?: string;
  attribuables?: boolean;
} = {}): Promise<ChambreConsultee[]> {
  return lire<ChambreConsultee[]>(`/chambres${parametres(options)}`);
}

export function consulterArriveesATraiter(
  jour: string,
): Promise<ReservationConsultee[]> {
  return lire<ReservationConsultee[]>(
    `/reservations/a-traiter${parametres({ jour })}`,
  );
}

export function consulterReservation(
  reference: string,
): Promise<ReservationConsultee> {
  return lire<ReservationConsultee>(`/reservations/${reference}`);
}

export function consulterAgents(
  secteur?: string,
): Promise<AgentConsulte[]> {
  return lire<AgentConsulte[]>(`/agents${parametres({ secteur })}`);
}

export function consulterTaches(secteur?: string): Promise<TacheConsultee[]> {
  return lire<TacheConsultee[]>(`/taches${parametres({ secteur })}`);
}

export function consulterIncidents(): Promise<IncidentConsulte[]> {
  return lire<IncidentConsulte[]>("/incidents");
}

export function recommanderPourReservation(
  reference: string,
  options: ParametresDeDecision = {},
): Promise<Recommandation> {
  return envoyer<ParametresDeDecision, Recommandation>(
    `/affectations/${reference}`,
    options,
  );
}

export function planifierLeService(
  secteur?: string,
  options: ParametresDeDecision = {},
): Promise<Planification> {
  return envoyer<ParametresDeDecision, Planification>(
    `/planifications/service${parametres({ secteur })}`,
    options,
  );
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

export function interpreterEnonce(
  enonce: string,
): Promise<LectureRestituee> {
  return envoyer<EnonceSoumis, LectureRestituee>("/interpretations", {
    enonce,
  });
}