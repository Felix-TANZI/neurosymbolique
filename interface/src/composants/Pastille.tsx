/**
 * Pastilles d'etat et d'etiquetage.
 *
 * Le rouge d'accent demeure reserve a la decision retenue et au comptage des
 * options: les etats operationnels emploient des teintes sourdes afin de ne
 * pas entrer en concurrence avec lui.
 */

import type { ReactNode } from "react";

type Nature = "neutre" | "accent" | "conforme" | "attente" | "ecarte";

const NATURES: Record<Nature, string> = {
  neutre: "bg-sourd text-service",
  accent: "bg-accent-sourd text-accent",
  conforme: "bg-[color-mix(in_srgb,var(--color-succes)_12%,white)] text-succes",
  attente: "bg-[color-mix(in_srgb,var(--color-attente)_14%,white)] text-attente",
  ecarte: "bg-sourd text-service line-through decoration-1",
};

interface ProprietesPastille {
  children: ReactNode;
  nature?: Nature;
}

export function Pastille({ children, nature = "neutre" }: ProprietesPastille) {
  return (
    <span
      className={`inline-flex items-center rounded-[var(--radius-pastille)] px-3 py-1 text-xs font-medium ${NATURES[nature]}`}
    >
      {children}
    </span>
  );
}

interface ProprietesListe {
  children: ReactNode;
}

export function ListeDePastilles({ children }: ProprietesListe) {
  return <div className="flex flex-wrap gap-2">{children}</div>;
}