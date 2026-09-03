/**
 * Conservation du traitement en cours entre les etapes.
 *
 * Un traitement suit un fil unique: une situation est decrite, le systeme
 * etablit ce qu'elle implique, un responsable decide. La session porte l'etape
 * atteinte et ce qui a ete etabli.
 */

import { createContext, useContext } from "react";
import type {
  ConsequencesRestituees,
  LectureRestituee,
  Planification,
  Recommandation,
} from "@/api/contrat";

export type Etape = "description" | "proposition" | "consignee";

export interface Traitement {
  etape: Etape;
  lecture: LectureRestituee | null;
  consequences: ConsequencesRestituees | null;
  recommandation: Recommandation | null;
  planification: Planification | null;
  reference: string | null;
  etabliLe: Date | null;
}

export const TRAITEMENT_INITIAL: Traitement = {
  etape: "description",
  lecture: null,
  consequences: null,
  recommandation: null,
  planification: null,
  reference: null,
  etabliLe: null,
};

export interface ContexteDeTraitement {
  traitement: Traitement;
  definir: (modification: Partial<Traitement>) => void;
  reinitialiser: () => void;
}

export const ContexteSession = createContext<ContexteDeTraitement | null>(null);

export function useSession(): ContexteDeTraitement {
  const contexte = useContext(ContexteSession);
  if (!contexte) {
    throw new Error(
      "useSession doit etre employe a l'interieur du fournisseur de session.",
    );
  }
  return contexte;
}
