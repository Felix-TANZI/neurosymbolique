/**
 * Conservation de la situation soumise entre les ecrans.
 *
 * L'ecran d'analyse etablit la situation, les ecrans de recommandation et de
 * validation l'exploitent. La conservation demeure en memoire: aucune donnee
 * n'est persistee cote interface, le noyau demeurant seul detenteur de l'etat.
 */

import { createContext, useContext } from "react";
import type {
  DemandeAffectation,
  DemandePlanification,
  Planification,
  Recommandation,
} from "@/api/contrat";

export type Service = "chambres" | "housekeeping";

export interface Session {
  service: Service;
  demandeChambres: DemandeAffectation | null;
  demandeHousekeeping: DemandePlanification | null;
  recommandation: Recommandation | null;
  planification: Planification | null;
  etabliLe: Date | null;
}

export const SESSION_INITIALE: Session = {
  service: "chambres",
  demandeChambres: null,
  demandeHousekeeping: null,
  recommandation: null,
  planification: null,
  etabliLe: null,
};

export interface ContexteDeSession {
  session: Session;
  definir: (modification: Partial<Session>) => void;
  reinitialiser: () => void;
}

export const ContexteSession = createContext<ContexteDeSession | null>(null);

export function useSession(): ContexteDeSession {
  const contexte = useContext(ContexteSession);
  if (!contexte) {
    throw new Error(
      "useSession doit etre employe a l'interieur du fournisseur de session.",
    );
  }
  return contexte;
}