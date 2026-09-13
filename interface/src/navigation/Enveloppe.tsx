/**
 * Enveloppe commune aux ecrans.
 *
 * L'enveloppe porte l'en-tete, la zone de contenu et la capsule de
 * navigation. Elle reserve un espace en pied de page afin que la capsule
 * flottante ne recouvre jamais le dernier element d'un ecran.
 *
 * Les marges se resserrent sur petit ecran: sur un telephone, chaque pixel
 * rendu au contenu vaut davantage qu'une respiration laterale.
 */

import { Outlet } from "react-router-dom";
import { Logo } from "@/composants/Logo";
import { Capsule } from "./Capsule";
import { IndicateurDeService } from "./IndicateurDeService";

export function Enveloppe() {
  return (
    <div className="min-h-screen bg-creme">
      <header className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-3 pb-1 pt-[max(1rem,env(safe-area-inset-top))] sm:px-6 sm:pb-2 sm:pt-8">
        <div className="flex min-w-0 items-center gap-2.5 sm:gap-3">
          <Logo taille={34} />
          <div className="min-w-0">
            <p className="hidden text-xs font-medium uppercase tracking-[0.16em] text-service sm:block">
              Aide a la decision critique
            </p>
            <h1 className="truncate font-display text-lg leading-tight sm:text-2xl lg:text-3xl">
              Operations internes
            </h1>
          </div>
        </div>
        <IndicateurDeService />
      </header>

      <main className="mx-auto max-w-7xl px-3 pb-28 pt-3 sm:px-6 sm:pb-32 sm:pt-4">
        <Outlet />
      </main>

      <Capsule />
    </div>
  );
}
