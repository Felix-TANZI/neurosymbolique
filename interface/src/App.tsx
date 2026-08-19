/**
 * Routage des ecrans du systeme.
 */

import { BrowserRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Enveloppe } from "@/navigation/Enveloppe";
import { TableauDeBord } from "@/ecrans/tableau-de-bord/TableauDeBord";
import { Analyse } from "@/ecrans/analyse/Analyse";
import { Recommandations } from "@/ecrans/recommandations/Recommandations";
import { Validation } from "@/ecrans/validation/Validation";
import { Historique } from "@/ecrans/historique/Historique";
import { Administration } from "@/ecrans/administration/Administration";
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
              <Route index element={<TableauDeBord />} />
              <Route path="analyse" element={<Analyse />} />
              <Route path="recommandations" element={<Recommandations />} />
              <Route path="validation" element={<Validation />} />
              <Route path="historique" element={<Historique />} />
              <Route path="administration" element={<Administration />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </FournisseurDeSession>
    </QueryClientProvider>
  );
}