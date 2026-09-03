/**
 * Routage des ecrans du systeme.
 */

import { BrowserRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Enveloppe } from "@/navigation/Enveloppe";
import { Aujourdhui } from "@/ecrans/aujourdhui/Aujourdhui";
import { Traiter } from "@/ecrans/traiter/Traiter";
import { Historique } from "@/ecrans/historique/Historique";
import { FournisseurDeSession } from "@/etat/FournisseurDeSession";

const clientDeRequetes = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={clientDeRequetes}>
      <FournisseurDeSession>
        <BrowserRouter>
          <Routes>
            <Route element={<Enveloppe />}>
              <Route index element={<Aujourdhui />} />
              <Route path="traiter" element={<Traiter />} />
              <Route path="historique" element={<Historique />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </FournisseurDeSession>
    </QueryClientProvider>
  );
}