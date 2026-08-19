/**
 * Restitution d'une recommandation d'affectation de chambre.
 *
 * Le comptage des options examinees precede la recommandation: il constitue
 * la trace visible du filtrage et distingue une decision etablie d'une simple
 * suggestion. Les options ecartees sont restituees avec leur motif, ce que
 * seul un raisonnement conservant sa trace permet.
 */

import { Link } from "react-router-dom";
import { ArrowRight, ShieldAlert, TriangleAlert } from "lucide-react";
import type { Recommandation } from "@/api/contrat";
import { Carte, EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { CompteurDeFiltrage } from "@/composants/CompteurDeFiltrage";
import { ListeDePastilles, Pastille } from "@/composants/Pastille";

export function RestitutionChambres({
  recommandation,
}: {
  recommandation: Recommandation;
}) {
  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Panneau>
          <EnTeteDeSection eyebrow="Filtrage" titre="Options du parc" />
          <CompteurDeFiltrage
            examinees={recommandation.chambres_examinees}
            admissibles={recommandation.chambres_admissibles.length}
            libelleExaminees="chambres examinees"
            libelleAdmissibles="admissibles"
          />
        </Panneau>

        {recommandation.a_conclu ? (
          <ChambreRetenue recommandation={recommandation} />
        ) : (
          <AucuneChambreAdmissible />
        )}
      </div>

      <Panneau>
        <EnTeteDeSection
          eyebrow="Trace du raisonnement"
          titre="Justification"
        />
        <div className="flex flex-col gap-2">
          {recommandation.justification.split("\n").map((ligne) => (
            <p key={ligne} className="text-sm leading-relaxed text-encre">
              {ligne}
            </p>
          ))}
        </div>
      </Panneau>

      {recommandation.options_ecartees.length > 0 ? (
        <OptionsEcartees recommandation={recommandation} />
      ) : null}
    </div>
  );
}

function ChambreRetenue({
  recommandation,
}: {
  recommandation: Recommandation;
}) {
  return (
    <Panneau ton="encre" className="flex flex-col justify-between gap-5">
      <div>
        <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-creme/60">
          Recommandation
        </p>
        <p className="font-display text-[var(--text-enorme)] leading-none text-creme">
          {recommandation.chambre_proposee}
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <ListeDePastilles>
          {recommandation.optimal ? (
            <Pastille nature="conforme">Optimale</Pastille>
          ) : null}
          {recommandation.sous_reserve ? (
            <Pastille nature="attente">Optimalite non garantie</Pastille>
          ) : null}
          <Pastille nature="neutre">Cout {recommandation.cout}</Pastille>
        </ListeDePastilles>

        {recommandation.contreparties.length > 0 ? (
          <div className="rounded-[var(--radius-carte)] bg-white/10 p-4">
            <p className="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-creme/60">
              Contreparties consenties
            </p>
            <ul className="flex flex-col gap-1.5">
              {recommandation.contreparties.map((contrepartie) => (
                <li
                  key={contrepartie.code}
                  className="text-sm leading-relaxed text-creme/85"
                >
                  {contrepartie.formulation}
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

function AucuneChambreAdmissible() {
  return (
    <Panneau ton="sourd" className="flex flex-col justify-center gap-3">
      <div className="flex items-center gap-2 text-accent">
        <ShieldAlert size={20} />
        <p className="text-xs font-medium uppercase tracking-[0.14em]">
          Aucune affectation possible
        </p>
      </div>
      <p className="font-display text-2xl leading-snug">
        Toutes les chambres du parc sont ecartees
      </p>
      <p className="max-w-md text-sm leading-relaxed text-service">
        Le motif de rejet de chaque chambre figure ci-dessous. Levez l'une des
        contraintes signalees, puis soumettez la situation a nouveau.
      </p>
    </Panneau>
  );
}

function OptionsEcartees({
  recommandation,
}: {
  recommandation: Recommandation;
}) {
  return (
    <Panneau ton="sourd">
      <EnTeteDeSection
        eyebrow="Tracabilite"
        titre="Options ecartees"
        action={
          <Pastille nature="neutre">
            {recommandation.options_ecartees.length} chambres
          </Pastille>
        }
      />
      <div className="grid gap-3 md:grid-cols-2">
        {recommandation.options_ecartees.map((option) => (
          <Carte key={option.chambre}>
            <div className="mb-2 flex items-center justify-between gap-3">
              <p className="font-display text-lg">{option.chambre}</p>
              <Pastille nature="ecarte">
                {option.motifs.length === 1
                  ? "1 motif"
                  : `${option.motifs.length} motifs`}
              </Pastille>
            </div>
            <ul className="flex flex-col gap-1.5">
              {option.formulations.map((formulation) => (
                <li
                  key={formulation}
                  className="flex gap-2 text-sm leading-relaxed text-service"
                >
                  <TriangleAlert
                    size={14}
                    className="mt-0.5 shrink-0 text-accent"
                  />
                  <span>{formulation}</span>
                </li>
              ))}
            </ul>
          </Carte>
        ))}
      </div>
    </Panneau>
  );
}