/**
 * Restitution du niveau de risque etabli.
 *
 * Le niveau expose la prudence que la situation commande. Un systeme qui
 * presenterait toutes ses propositions avec la meme assurance laisserait au
 * responsable la charge de deceler celles qui reposent sur une lecture
 * incertaine.
 */

import { CircleAlert, CircleCheck, CircleHelp, TriangleAlert } from "lucide-react";
import type { RisqueApprecie } from "@/api/contrat";

const APPARENCES: Record<
  1 | 2 | 3 | 4,
  { libelle: string; classe: string; Icone: typeof CircleCheck }
> = {
  1: {
    libelle: "Risque mesure",
    classe: "text-succes",
    Icone: CircleCheck,
  },
  2: {
    libelle: "Risque modere",
    classe: "text-encre",
    Icone: CircleAlert,
  },
  3: {
    libelle: "Risque eleve",
    classe: "text-attente",
    Icone: TriangleAlert,
  },
  4: {
    libelle: "Indetermine",
    classe: "text-accent",
    Icone: CircleHelp,
  },
};

export function Risque({ risque }: { risque: RisqueApprecie }) {
  const apparence = APPARENCES[risque.niveau] ?? APPARENCES[4];
  const { Icone } = apparence;

  return (
    <div className="flex items-start gap-3">
      <Icone size={18} className={`mt-0.5 shrink-0 ${apparence.classe}`} />
      <div>
        <p className={`text-sm font-medium ${apparence.classe}`}>
          {apparence.libelle}
        </p>
        <p className="mt-0.5 text-sm leading-relaxed text-service">
          {risque.conduite}
        </p>
      </div>
    </div>
  );
}

export function Abstention({
  risque,
  surReprise,
}: {
  risque: RisqueApprecie;
  surReprise: () => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start gap-3">
        <CircleHelp size={20} className="mt-1 shrink-0 text-accent" />
        <div>
          <p className="font-display text-2xl leading-snug">
            Je ne peux pas repondre de facon fiable
          </p>
          {risque.motifs.map((motif) => (
            <p key={motif} className="mt-1 text-sm leading-relaxed text-service">
              {motif}
            </p>
          ))}
        </div>
      </div>

      {risque.precision_attendue ? (
        <p className="rounded-[var(--radius-carte)] bg-accent-sourd px-4 py-3 text-sm leading-relaxed">
          {risque.precision_attendue}
        </p>
      ) : null}

      <button
        type="button"
        onClick={surReprise}
        className="inline-flex w-fit items-center gap-2 rounded-[var(--radius-pastille)] bg-accent px-5 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
      >
        Reformuler
      </button>
    </div>
  );
}
