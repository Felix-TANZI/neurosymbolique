/**
 * Restitution du plan d'intervention de la maintenance.
 *
 * Les interventions sont ordonnees par criticite: celle qui immobilise le plus
 * est traitee la premiere, quand bien meme une autre serait plus rapide a
 * conduire.
 */

import { TriangleAlert, Wrench } from "lucide-react";
import type { PlanRestitue } from "@/api/contrat";
import { Carte, EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";

const COURANTE = { libelle: "Courante", nature: "neutre" };

const CRITICITES: Record<number, { libelle: string; nature: string }> = {
  1: { libelle: "Differee", nature: "neutre" },
  2: COURANTE,
  3: { libelle: "Prioritaire", nature: "attente" },
  4: { libelle: "Immediate", nature: "accent" },
};

const CAUSES: Record<string, string> = {
  competence_absente: "aucun technicien qualifie",
  charge_saturee: "tous les techniciens qualifies sont a pleine charge",
  aucun_technicien_disponible: "aucun technicien disponible",
};

export function PlanDIntervention({ plan }: { plan: PlanRestitue }) {
  return (
    <>
      <Panneau ton={plan.est_complet ? "sourd" : "encre"}>
        <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] opacity-60">
          Maintenance
        </p>
        <p
          className={[
            "font-display text-xl leading-tight sm:text-2xl lg:text-3xl",
            plan.est_complet ? "text-encre" : "text-creme",
          ].join(" ")}
        >
          {plan.affectees.length} interventions affectees
        </p>
        {plan.en_attente.length > 0 ? (
          <p className="mt-3 text-sm leading-relaxed text-creme/80">
            {plan.en_attente.length} demeurent sans technicien.
          </p>
        ) : null}
      </Panneau>

      {plan.affectees.length > 0 ? (
        <Panneau>
          <EnTeteDeSection eyebrow="Ordre" titre="Interventions affectees" />
          <div className="grid grid-cols-2 gap-2 sm:gap-3 xl:grid-cols-3">
            {plan.affectees.map((intervention, position) => {
              const criticite = CRITICITES[intervention.criticite] ?? COURANTE;
              return (
                <Carte key={intervention.identifiant} retenue>
                  <div className="mb-2 flex flex-wrap items-start justify-between gap-2 sm:gap-3">
                    <div className="flex min-w-0 items-start gap-3">
                      <Wrench
                        size={16}
                        className="mt-1 hidden shrink-0 text-service sm:block"
                      />
                      <div className="min-w-0">
                        <p className="font-display text-base leading-snug sm:text-lg">
                          {position + 1}. Chambre {intervention.objet}
                        </p>
                        <p className="text-xs text-service sm:text-sm">
                          {intervention.competence === "polyvalent"
                            ? `Sans specialite requise · ${intervention.technicien}`
                            : `${intervention.competence} · ${intervention.technicien}`}
                        </p>
                      </div>
                    </div>
                    <Pastille nature={criticite.nature as never}>
                      {criticite.libelle}
                    </Pastille>
                  </div>
                  <p className="text-xs leading-relaxed text-service sm:text-sm">
                    {intervention.motif}
                  </p>
                </Carte>
              );
            })}
          </div>
        </Panneau>
      ) : null}

      {plan.en_attente.length > 0 ? (
        <Panneau>
          <EnTeteDeSection
            eyebrow="Sans solution"
            titre="Interventions en attente"
            action={
              <Pastille nature="attente">{plan.en_attente.length}</Pastille>
            }
          />
          <div className="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-3">
            {plan.en_attente.map((manquee) => (
              <Carte key={manquee.identifiant}>
                <div className="flex items-start gap-2 sm:gap-3">
                  <TriangleAlert
                    size={15}
                    className="mt-0.5 shrink-0 text-accent"
                  />
                  <div className="min-w-0">
                    <p className="font-display text-base leading-snug sm:text-lg">
                      {manquee.objet}
                    </p>
                    <p className="text-xs text-service sm:text-sm">
                      {CAUSES[manquee.cause] ?? manquee.cause}
                      {manquee.detail ? ` — ${manquee.detail}` : ""}
                    </p>
                  </div>
                </div>
              </Carte>
            ))}
          </div>
        </Panneau>
      ) : null}
    </>
  );
}
