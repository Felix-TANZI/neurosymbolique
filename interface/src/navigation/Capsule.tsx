/**
 * Capsule de navigation flottante.
 *
 * La navigation demeure accessible sans occuper d'espace permanent: elle
 * flotte au-dessus du contenu, ce qui preserve la densite d'information des
 * ecrans operationnels.
 */

import { NavLink } from "react-router-dom";
import {
  ClipboardList,
  FileText,
  LayoutGrid,
  ListChecks,
  Settings,
  Sparkles,
} from "lucide-react";
import type { ComponentType } from "react";

interface Entree {
  chemin: string;
  libelle: string;
  Icone: ComponentType<{ size?: number; strokeWidth?: number }>;
}

const ENTREES: Entree[] = [
  { chemin: "/", libelle: "Tableau de bord", Icone: LayoutGrid },
  { chemin: "/analyse", libelle: "Analyse", Icone: Sparkles },
  { chemin: "/recommandations", libelle: "Recommandations", Icone: ListChecks },
  { chemin: "/validation", libelle: "Validation", Icone: ClipboardList },
  { chemin: "/historique", libelle: "Historique", Icone: FileText },
  { chemin: "/administration", libelle: "Regles", Icone: Settings },
];

export function Capsule() {
  return (
    <nav
      aria-label="Navigation principale"
      className="fixed bottom-5 left-1/2 z-50 -translate-x-1/2"
    >
      <ul className="flex items-center gap-1 rounded-[var(--radius-pastille)] bg-encre px-2 py-2 shadow-lg shadow-black/15">
        {ENTREES.map(({ chemin, libelle, Icone }) => (
          <li key={chemin}>
            <NavLink
              to={chemin}
              end={chemin === "/"}
              className={({ isActive }) =>
                [
                  "flex items-center gap-2 rounded-[var(--radius-pastille)] px-4 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-accent text-white"
                    : "text-creme/70 hover:bg-white/10 hover:text-creme",
                ].join(" ")
              }
            >
              <Icone size={16} strokeWidth={2} />
              <span className="hidden sm:inline">{libelle}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}