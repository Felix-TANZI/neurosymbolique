/**
 * Ecran de validation humaine.
 *
 * Aucune recommandation n'est appliquee par le systeme: la decision revient au
 * responsable, qui valide, corrige ou refuse. Les trois issues sont traitees a
 * egalite et consignees avec leur motif: un refus constitue une information
 * d'evaluation aussi precieuse qu'une validation.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { Check, Inbox, PenLine, X } from "lucide-react";
import { EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";
import { useSession } from "@/etat/situation";
import { TraceDuRaisonnement } from "./TraceDuRaisonnement";

type Issue = "validee" | "corrigee" | "refusee";

const ISSUES: { valeur: Issue; libelle: string; Icone: typeof Check }[] = [
  { valeur: "validee", libelle: "Valider", Icone: Check },
  { valeur: "corrigee", libelle: "Corriger", Icone: PenLine },
  { valeur: "refusee", libelle: "Refuser", Icone: X },
];

export function Validation() {
  const { session } = useSession();
  const [issue, setIssue] = useState<Issue | null>(null);
  const [motif, setMotif] = useState("");
  const [consignee, setConsignee] = useState(false);

  const proposition =
    session.service === "chambres"
      ? (session.recommandation?.chambre_proposee ?? "Aucune chambre admissible")
      : session.planification?.est_complete
        ? "Planning complet"
        : "Planification partielle";

  if (!session.etabliLe) {
    return <AucuneDecisionAExaminer />;
  }

  if (consignee) {
    return (
      <DecisionConsignee
        issue={issue}
        motif={motif}
        surReprise={() => {
          setConsignee(false);
          setIssue(null);
          setMotif("");
        }}
      />
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <Panneau ton="encre">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-creme/60">
              Proposition soumise a votre decision
            </p>
            <p className="font-display text-3xl text-creme">{proposition}</p>
            <p className="mt-1 text-sm text-creme/60">
              {session.service === "chambres"
                ? `Sejour ${session.reference}`
                : `Secteur ${session.secteur?.replace(/_/g, " ") ?? ""}`}
            </p>
          </div>
          <Pastille nature="accent">
            {session.service === "chambres" ? "Chambres" : "Housekeeping"}
          </Pastille>
        </div>
      </Panneau>

      <TraceDuRaisonnement session={session} />

      <Panneau>
        <EnTeteDeSection
          eyebrow="Etape 3"
          titre="Votre decision"
          action={
            <Pastille nature="neutre">Aucune application automatique</Pastille>
          }
        />

        <div
          role="radiogroup"
          aria-label="Issue de la decision"
          className="mb-4 flex flex-wrap gap-2"
        >
          {ISSUES.map(({ valeur, libelle, Icone }) => {
            const retenue = issue === valeur;
            return (
              <button
                key={valeur}
                type="button"
                role="radio"
                aria-checked={retenue}
                onClick={() => setIssue(valeur)}
                className={[
                  "inline-flex items-center gap-2 rounded-[var(--radius-pastille)] px-5 py-2.5 text-sm font-medium transition-colors",
                  retenue
                    ? "bg-accent text-white"
                    : "bg-sourd text-encre hover:bg-bordure",
                ].join(" ")}
              >
                <Icone size={16} />
                {libelle}
              </button>
            );
          })}
        </div>

        <label
          htmlFor="motif"
          className="mb-2 block text-sm font-medium text-encre"
        >
          Motif de la decision
        </label>
        <textarea
          id="motif"
          value={motif}
          onChange={(evenement) => setMotif(evenement.target.value)}
          rows={3}
          placeholder="Precisez ce qui a motive cette decision."
          className="w-full rounded-[var(--radius-carte)] border border-bordure bg-creme px-4 py-3 text-sm leading-relaxed outline-none placeholder:text-service/60 focus:border-encre"
        />
        <p className="mt-2 text-sm text-service">
          Le motif alimente le corpus d'apprentissage de la couche
          d'interpretation. Il ne modifie jamais les contraintes du systeme.
        </p>

        <button
          type="button"
          disabled={!issue}
          onClick={() => setConsignee(true)}
          className="mt-5 inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-encre px-6 py-3 text-sm font-medium text-creme transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          Consigner la decision
        </button>
      </Panneau>
    </div>
  );
}

function AucuneDecisionAExaminer() {
  return (
    <Panneau className="flex flex-col items-start gap-4">
      <EnTeteDeSection eyebrow="Etape 3" titre="Aucune decision a examiner" />
      <div className="flex items-start gap-3 text-service">
        <Inbox size={20} className="mt-0.5 shrink-0" />
        <p className="max-w-lg text-sm leading-relaxed">
          Soumettez une situation au raisonnement pour obtenir une proposition a
          examiner.
        </p>
      </div>
      <Link
        to="/analyse"
        className="inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-encre px-5 py-2.5 text-sm font-medium text-creme transition-opacity hover:opacity-90"
      >
        Decrire une situation
      </Link>
    </Panneau>
  );
}

function DecisionConsignee({
  issue,
  motif,
  surReprise,
}: {
  issue: Issue | null;
  motif: string;
  surReprise: () => void;
}) {
  const libelles: Record<Issue, string> = {
    validee: "Decision validee",
    corrigee: "Decision corrigee",
    refusee: "Proposition refusee",
  };

  return (
    <Panneau className="flex flex-col items-start gap-4">
      <EnTeteDeSection eyebrow="Consignee" titre={issue ? libelles[issue] : ""} />
      <p className="max-w-lg text-sm leading-relaxed text-service">
        La decision, la trace du raisonnement, votre identite et l'horodatage
        sont consignes au journal. Le journal est en ajout seul: une decision
        consignee demeure consultable telle qu'elle a ete prise.
      </p>
      {motif ? (
        <blockquote className="w-full rounded-[var(--radius-carte)] bg-sourd p-4 text-sm leading-relaxed">
          {motif}
        </blockquote>
      ) : null}
      <div className="flex flex-wrap gap-3">
        <Link
          to="/analyse"
          className="inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-accent px-5 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
        >
          Situation suivante
        </Link>
        <button
          type="button"
          onClick={surReprise}
          className="inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-sourd px-5 py-2.5 text-sm font-medium text-encre transition-colors hover:bg-bordure"
        >
          Reprendre la decision
        </button>
      </div>
    </Panneau>
  );
}