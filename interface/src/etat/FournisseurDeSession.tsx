/**
 * Fournisseur de la session courante.
 */

import { useCallback, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  ContexteSession,
  TRAITEMENT_INITIAL,
  type Traitement,
} from "./situation";

export function FournisseurDeSession({ children }: { children: ReactNode }) {
  const [traitement, setTraitement] = useState<Traitement>(TRAITEMENT_INITIAL);

  const definir = useCallback((modification: Partial<Traitement>) => {
    setTraitement((precedent) => ({ ...precedent, ...modification }));
  }, []);

  const reinitialiser = useCallback(() => {
    setTraitement(TRAITEMENT_INITIAL);
  }, []);

  const valeur = useMemo(
    () => ({ traitement, definir, reinitialiser }),
    [traitement, definir, reinitialiser],
  );

  return (
    <ContexteSession.Provider value={valeur}>
      {children}
    </ContexteSession.Provider>
  );
}
