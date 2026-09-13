/**
 * Consultation des decisions consignees.
 *
 * Le journal restitue ce qui a ete demande, propose et decide. Il ne decrit
 * aucun etat de l'etablissement: une decision consignee etablit qu'une
 * proposition a recu une suite, non que l'exploitation en a ete modifiee.
 *
 * Les ecarts sont distingues: un refus ou une correction designent une
 * situation ou le raisonnement et le jugement du responsable ont diverge, ce
 * qui merite examen.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { consulterLesDecisions } from "@/api/client";
import type { DecisionConsultee, IssueDeDecision } from "@/api/contrat";
import { Carte, EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";

const ISSUES: Record<IssueDeDecision, { libelle: string; nature: string }> = {
  validee: { libelle: "Validee", nature: "conforme" },
  corrigee: { libelle: "Corrigee", nature: "attente" },
  refusee: { libelle: "Refusee", nature: "accent" },
  differee: { libelle: "Differee", nature: "neutre" },
};

export function Historique() {
  const [ecartsSeulement, setEcartsSeulement] = useState(false);

  const decisions = useQuery({
    queryKey: ["decisions", ecartsSeulement],
    queryFn: () => consulterLesDecisions(50, ecartsSeulement),
  });

  const entrees = decisions.data ?? [];
  const ecarts = entrees.filter((entree) => entree.marque_un_ecart).length;

  return (
    <div className="flex flex-col gap-5">
      <Panneau ton="encre">
        <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-creme/60">
          Journal
        </p>
        <p className="font-display text-[var(--text-enorme)] leading-none text-creme">
          {entrees.length}
        </p>
        <p className="mt-2 font-display text-2xl text-creme">
          {entrees.length === 1 ? "decision consignee" : "decisions consignees"}
        </p>
        {ecarts > 0 ? (
          <p className="mt-3 text-sm leading-relaxed text-creme/70">
            {ecarts} {ecarts === 1 ? "decision s'ecarte" : "decisions s'ecartent"}{" "}
            de la proposition du systeme.
          </p>
        ) : null}
      </Panneau>

      <Panneau>
        <EnTeteDeSection
          eyebrow="Decisions"
          titre="Ce qui a ete decide"
          action={
            <button
              type="button"
              onClick={() => setEcartsSeulement(!ecartsSeulement)}
              className={[
                "rounded-[var(--radius-pastille)] px-4 py-1.5 text-sm font-medium transition-colors",
                ecartsSeulement
                  ? "bg-accent text-white"
                  : "bg-sourd text-encre hover:bg-bordure",
              ].join(" ")}
            >
              Ecarts seulement
            </button>
          }
        />

        {decisions.isPending ? (
          <p className="text-sm text-service">Consultation du journal...</p>
        ) : entrees.length === 0 ? (
          <p className="text-sm leading-relaxed text-service">
            {ecartsSeulement
              ? "Aucune decision ne s'ecarte de la proposition du systeme."
              : "Aucune decision n'a encore ete consignee."}
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {entrees.map((entree) => (
              <Entree key={entree.identifiant} entree={entree} />
            ))}
          </div>
        )}
      </Panneau>
    </div>
  );
}

function Entree({ entree }: { entree: DecisionConsultee }) {
  const [detaille, setDetaille] = useState(false);
  const issue = ISSUES[entree.issue];

  return (
    <Carte retenue={entree.marque_un_ecart}>
      <div className="mb-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-display text-lg leading-snug">{entree.situation}</p>
          <p className="text-sm text-service">
            {new Date(entree.horodatage).toLocaleString("fr-FR")}
            {entree.valideur ? ` · ${entree.valideur}` : ""}
          </p>
        </div>
        <Pastille nature={issue.nature as never}>
          {issue.libelle}
        </Pastille>
      </div>

      <p className="text-sm text-encre">{entree.proposition}</p>

      {entree.motif ? (
        <p className="mt-2 rounded-[var(--radius-carte)] bg-accent-sourd px-4 py-2.5 text-sm leading-relaxed">
          {entree.motif}
        </p>
      ) : null}

      {entree.justification ? (
        <>
          <button
            type="button"
            onClick={() => setDetaille(!detaille)}
            className="mt-3 inline-flex items-center gap-1.5 text-sm text-service hover:text-encre"
            aria-expanded={detaille}
          >
            <ChevronDown
              size={14}
              className={
                detaille
                  ? "rotate-180 transition-transform"
                  : "transition-transform"
              }
            />
            {detaille ? "Masquer le raisonnement" : "Voir le raisonnement"}
          </button>

          {detaille ? (
            <p className="mt-2 rounded-[var(--radius-carte)] bg-sourd p-4 text-sm leading-relaxed">
              {entree.justification}
            </p>
          ) : null}
        </>
      ) : null}
    </Carte>
  );
}
