/**
 * Conservation de la decision courante entre les ecrans.
 *
 * L'ecran d'analyse designe l'entite a traiter, les ecrans de restitution et
 * de validation exploitent l'issue du raisonnement. La conservation demeure en
 * memoire: le noyau demeure seul detenteur de l'etat de l'etablissement.
 */

import { createContext, useContext } from "react";
import type { Planification, Recommandation } from "@/api/contrat";

export type Service = "chambres" | "housekeeping";

export interface Session {
  service: Service;
  reference: string | null;
  secteur: string | null;
  recommandation: Recommandation | null;
  planification: Planification | null;
  etabliLe: Date | null;
}

export const SESSION_INITIALE: Session = {
  service: "chambres",
  reference: null,
  secteur: null,
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
