/**
 * Restitution d'une planification du service d'etage.
 *
 * Le planning est presente par agent, dans l'ordre chronologique, avec les
 * horaires reels calcules par le solveur. Les taches demeurees en attente sont
 * distinguees selon leur cause: l'absence d'agent admissible impose de
 * mobiliser une qualification, le manque de capacite impose de degager du
 * temps. La distinction determine l'action du responsable.
 */

import { Link } from "react-router-dom";
import { ArrowRight, Clock, UserX } from "lucide-react";
import type { Affectation, Planification, TacheEnAttente } from "@/api/contrat";
import { Carte, EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { CompteurDeFiltrage } from "@/composants/CompteurDeFiltrage";
import { ListeDePastilles, Pastille } from "@/composants/Pastille";

export function RestitutionHousekeeping({
  planification,
}: {
  planification: Planification;
}) {
  const total =
    planification.affectations.length + planification.taches_en_attente.length;

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Panneau>
          <EnTeteDeSection eyebrow="Planification" titre="Taches du service" />
          <CompteurDeFiltrage
            examinees={total}
            admissibles={planification.affectations.length}
            libelleExaminees="taches soumises"
            libelleAdmissibles="planifiees"
          />
        </Panneau>

        <BilanDuService planification={planification} />
      </div>

      <Panneau>
        <EnTeteDeSection
          eyebrow="Trace du raisonnement"
          titre="Justification"
        />
        <div className="flex flex-col gap-2">
          {planification.justification.map((ligne) => (
            <p key={ligne} className="text-sm leading-relaxed text-encre">
              {ligne}
            </p>
          ))}
        </div>
      </Panneau>

      {planification.affectations.length > 0 ? (
        <PlanningParAgent planification={planification} />
      ) : null}

      {planification.taches_en_attente.length > 0 ? (
        <TachesEnAttente taches={planification.taches_en_attente} />
      ) : null}
    </div>
  );
}

function BilanDuService({ planification }: { planification: Planification }) {
  const derniere = planification.affectations.reduce<string | null>(
    (fin, affectation) => (fin && fin > affectation.fin ? fin : affectation.fin),
    null,
  );

  return (
    <Panneau ton="encre" className="flex flex-col justify-between gap-5">
      <div>
        <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-creme/60">
          {planification.est_complete
            ? "Service acheve a"
            : "Planification partielle"}
        </p>
        <p className="font-display text-[var(--text-enorme)] leading-none text-creme">
          {derniere ?? "--"}
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <ListeDePastilles>
          {planification.est_complete ? (
            <Pastille nature="conforme">Toutes les taches planifiees</Pastille>
          ) : (
            <Pastille nature="attente">
              {planification.taches_en_attente.length} en attente
            </Pastille>
          )}
          {planification.sous_reserve ? (
            <Pastille nature="attente">Optimalite non garantie</Pastille>
          ) : null}
        </ListeDePastilles>

        {planification.charges.length > 0 ? (
          <div className="rounded-[var(--radius-carte)] bg-white/10 p-4">
            <p className="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-creme/60">
              Charge par agent
            </p>
            <ul className="flex flex-col gap-1.5">
              {planification.charges.map((charge) => (
                <li
                  key={charge.agent}
                  className="flex justify-between gap-4 text-sm text-creme/85"
                >
                  <span>{charge.agent}</span>
                  <span className="tabular-nums">{charge.minutes} min</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <Link
          to="/validation"
          className="inline-flex w-fit items-center gap-2 rounded-[var(--radius-pastille)] bg-accent px-6 py-3 text-sm font-medium text-white transition-opacity hover:opacity-90"
        >
          Examiner et valider
          <ArrowRight size={16} />
        </Link>
      </div>
    </Panneau>
  );
}

function PlanningParAgent({ planification }: { planification: Planification }) {
  const parAgent = new Map<string, Affectation[]>();
  for (const affectation of planification.affectations) {
    const existantes = parAgent.get(affectation.agent) ?? [];
    existantes.push(affectation);
    parAgent.set(affectation.agent, existantes);
  }

  return (
    <Panneau>
      <EnTeteDeSection
        eyebrow="Ordonnancement"
        titre="Planning des agents"
        action={<Pastille nature="neutre">{parAgent.size} agents</Pastille>}
      />
      <div className="grid gap-4 md:grid-cols-2">
        {[...parAgent.entries()].map(([agent, affectations]) => (
          <Carte key={agent}>
            <div className="mb-3 flex items-baseline justify-between gap-3">
              <p className="font-display text-lg">{agent}</p>
              <span className="text-sm tabular-nums text-service">
                {affectations.reduce(
                  (total, affectation) => total + affectation.duree_minutes,
                  0,
                )}{" "}
                min
              </span>
            </div>
            <ol className="flex flex-col">
              {affectations.map((affectation) => (
                <li
                  key={affectation.tache}
                  className="flex items-center gap-3 border-t border-bordure py-2 first:border-t-0 first:pt-0"
                >
                  <span className="w-28 shrink-0 text-sm tabular-nums text-accent">
                    {affectation.debut} — {affectation.fin}
                  </span>
                  <span className="text-sm">{affectation.tache}</span>
                </li>
              ))}
            </ol>
          </Carte>
        ))}
      </div>
    </Panneau>
  );
}

function TachesEnAttente({ taches }: { taches: TacheEnAttente[] }) {
  return (
    <Panneau ton="sourd">
      <EnTeteDeSection
        eyebrow="Tracabilite"
        titre="Taches en attente"
        action={<Pastille nature="neutre">{taches.length} taches</Pastille>}
      />
      <div className="grid gap-3 md:grid-cols-2">
        {taches.map((tache) => (
          <Carte key={tache.tache}>
            <div className="mb-2 flex items-center justify-between gap-3">
              <p className="font-display text-lg">{tache.tache}</p>
              <Pastille nature="attente">
                {tache.cause === "aucun_agent_admissible"
                  ? "Qualification"
                  : "Capacite"}
              </Pastille>
            </div>
            <div className="mb-3 flex items-start gap-2 text-sm leading-relaxed text-encre">
              {tache.cause === "aucun_agent_admissible" ? (
                <>
                  <UserX size={14} className="mt-0.5 shrink-0 text-accent" />
                  <span>
                    Aucun agent en service ne peut prendre cette tache. Mobilisez
                    une qualification ou une habilitation.
                  </span>
                </>
              ) : (
                <>
                  <Clock size={14} className="mt-0.5 shrink-0 text-accent" />
                  <span>
                    La capacite disponible ne suffit pas. Degagez du temps ou
                    reportez une tache moins prioritaire.
                  </span>
                </>
              )}
            </div>
            {tache.motifs.length > 0 ? (
              <ul className="flex flex-col gap-1">
                {tache.motifs.slice(0, 3).map((motif) => (
                  <li key={motif} className="text-xs text-service">
                    {motif}
                  </li>
                ))}
              </ul>
            ) : null}
          </Carte>
        ))}
      </div>
    </Panneau>
  );
}