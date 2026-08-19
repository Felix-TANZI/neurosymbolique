/**
 * Enveloppe commune aux ecrans.
 *
 * L'enveloppe porte l'en-tete, la zone de contenu et la capsule de
 * navigation. Elle reserve un espace en pied de page afin que la capsule
 * flottante ne recouvre jamais le dernier element d'un ecran.
 */

import { Outlet } from "react-router-dom";
import { Capsule } from "./Capsule";
import { IndicateurDeService } from "./IndicateurDeService";

export function Enveloppe() {
  return (
    <div className="min-h-screen bg-creme">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 pb-2 pt-8">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-service">
            Aide a la decision critique
          </p>
          <h1 className="font-display text-3xl leading-tight">
            Operations internes
          </h1>
        </div>
        <IndicateurDeService />
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-32 pt-4">
        <Outlet />
      </main>

      <Capsule />
    </div>
  );
}