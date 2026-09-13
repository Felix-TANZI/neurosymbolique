/**
 * Panneaux et blocs structurants de l'interface.
 *
 * La mise en forme repose sur de grands panneaux arrondis plutot que sur des
 * bordures: la separation entre elements resulte du contraste des fonds.
 */

import type { ReactNode } from "react";

type Ton = "clair" | "sourd" | "encre" | "accent";

const FONDS: Record<Ton, string> = {
  clair: "bg-panneau text-encre",
  sourd: "bg-sourd text-encre",
  encre: "bg-encre text-creme",
  accent: "bg-accent text-white",
};

interface ProprietesPanneau {
  children: ReactNode;
  ton?: Ton;
  className?: string;
}

export function Panneau({
  children,
  ton = "clair",
  className = "",
}: ProprietesPanneau) {
  return (
    <section
      className={`rounded-[var(--radius-panneau)] ${FONDS[ton]} p-4 sm:p-5 lg:p-6 ${className}`}
    >
      {children}
    </section>
  );
}

interface ProprietesEnTete {
  titre: string;
  eyebrow?: string;
  action?: ReactNode;
}

export function EnTeteDeSection({ titre, eyebrow, action }: ProprietesEnTete) {
  return (
    <header className="mb-3 flex flex-wrap items-end justify-between gap-x-4 gap-y-2 sm:mb-5">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-service">
            {eyebrow}
          </p>
        ) : null}
        <h2 className="font-display text-lg leading-tight sm:text-xl lg:text-2xl">
          {titre}
        </h2>
      </div>
      {action}
    </header>
  );
}

interface ProprietesCarte {
  children: ReactNode;
  interactive?: boolean;
  retenue?: boolean;
  className?: string;
}

export function Carte({
  children,
  interactive = false,
  retenue = false,
  className = "",
}: ProprietesCarte) {
  const bordure = retenue
    ? "border-2 border-accent"
    : "border border-bordure";
  const survol = interactive
    ? "transition-colors hover:border-encre focus-within:border-encre"
    : "";

  return (
    <article
      className={`min-w-0 rounded-[var(--radius-carte)] bg-panneau p-3 sm:p-4 lg:p-5 ${bordure} ${survol} ${className}`}
    >
      {children}
    </article>
  );
}