/**
 * Capsule de navigation flottante.
 *
 * La navigation demeure accessible sans occuper d'espace permanent: elle
 * flotte au-dessus du contenu, ce qui preserve la densite d'information des
 * ecrans operationnels.
 *
 * Les libelles s'effacent a mesure que la largeur manque: tous sur grand
 * ecran, celui de l'ecran courant seul sur tablette, aucun sur telephone, ou
 * les icones suffisent et chaque entree demeure nommee pour les lecteurs
 * d'ecran.
 */

import { NavLink } from "react-router-dom";
import {
  Building2,
  FileText,
  FlaskConical,
  LayoutGrid,
  Sparkles,
} from "lucide-react";
import type { ComponentType } from "react";

interface Entree {
  chemin: string;
  libelle: string;
  Icone: ComponentType<{ size?: number; strokeWidth?: number }>;
}

const ENTREES: Entree[] = [
  { chemin: "/", libelle: "Aujourd'hui", Icone: LayoutGrid },
  { chemin: "/traiter", libelle: "Traiter", Icone: Sparkles },
  { chemin: "/etablissement", libelle: "Etablissement", Icone: Building2 },
  { chemin: "/historique", libelle: "Historique", Icone: FileText },
  { chemin: "/simulation", libelle: "Simulation", Icone: FlaskConical },
];

export function Capsule() {
  return (
    <nav
      aria-label="Navigation principale"
      className="fixed bottom-[max(0.75rem,env(safe-area-inset-bottom))] left-1/2 z-50 -translate-x-1/2 sm:bottom-5"
    >
      <ul className="flex items-center gap-0.5 rounded-[var(--radius-pastille)] bg-encre p-1.5 shadow-lg shadow-black/15 sm:gap-1 sm:p-2">
        {ENTREES.map(({ chemin, libelle, Icone }) => (
          <li key={chemin}>
            <NavLink
              to={chemin}
              end={chemin === "/"}
              aria-label={libelle}
              title={libelle}
              className={({ isActive }) =>
                [
                  "flex items-center gap-2 rounded-[var(--radius-pastille)] px-3.5 py-2.5 text-sm font-medium transition-colors sm:px-4 sm:py-2",
                  isActive
                    ? "bg-accent text-white"
                    : "text-creme/70 hover:bg-white/10 hover:text-creme",
                ].join(" ")
              }
            >
              {({ isActive }) => (
                <>
                  <Icone size={17} strokeWidth={2} />
                  <span
                    className={
                      isActive ? "hidden sm:inline" : "hidden lg:inline"
                    }
                  >
                    {libelle}
                  </span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
