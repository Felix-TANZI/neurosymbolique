/**
 * Indicateur des etapes du traitement.
 *
 * Trois etapes, dont celle atteinte est mise en evidence. Un responsable doit
 * savoir a tout moment ou il en est et ce qui reste a faire.
 */

import type { Etape } from "@/etat/situation";

const ETAPES: { valeur: Etape; libelle: string }[] = [
  { valeur: "description", libelle: "Decrire" },
  { valeur: "proposition", libelle: "Examiner" },
  { valeur: "consignee", libelle: "Decider" },
];

export function Progression({ etape }: { etape: Etape }) {
  const rang = ETAPES.findIndex((candidate) => candidate.valeur === etape);

  return (
    <ol className="flex items-center gap-3" aria-label="Etapes du traitement">
      {ETAPES.map((candidate, position) => {
        const atteinte = position <= rang;
        const courante = position === rang;
        return (
          <li key={candidate.valeur} className="flex items-center gap-3">
            <span
              className={[
                "inline-flex items-center gap-2 rounded-[var(--radius-pastille)] px-4 py-1.5 text-sm font-medium transition-colors",
                courante
                  ? "bg-accent text-white"
                  : atteinte
                    ? "bg-encre text-creme"
                    : "bg-sourd text-service",
              ].join(" ")}
            >
              <span className="tabular-nums">{position + 1}</span>
              {candidate.libelle}
            </span>
            {position < ETAPES.length - 1 ? (
              <span
                className={[
                  "h-px w-6",
                  atteinte ? "bg-encre" : "bg-bordure",
                ].join(" ")}
              />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}