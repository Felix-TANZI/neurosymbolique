/**
 * Fournisseur de la session courante.
 */

import { useCallback, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  ContexteSession,
  SESSION_INITIALE,
  type Session,
} from "./situation";

export function FournisseurDeSession({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session>(SESSION_INITIALE);

  const definir = useCallback((modification: Partial<Session>) => {
    setSession((precedente) => ({ ...precedente, ...modification }));
  }, []);

  const reinitialiser = useCallback(() => {
    setSession(SESSION_INITIALE);
  }, []);

  const valeur = useMemo(
    () => ({ session, definir, reinitialiser }),
    [session, definir, reinitialiser],
  );

  return (
    <ContexteSession.Provider value={valeur}>
      {children}
    </ContexteSession.Provider>
  );
}