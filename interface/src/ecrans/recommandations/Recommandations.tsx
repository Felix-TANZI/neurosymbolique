/**
 * Restitution de l'issue du raisonnement.
 *
 * L'ecran presente la recommandation, les contreparties consenties et le motif
 * de rejet de chaque option ecartee. Aucune decision n'est appliquee: la
 * validation demeure une action distincte.
 */

import { Link } from "react-router-dom";
import { ArrowRight, Inbox } from "lucide-react";
import { EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";
import { useSession } from "@/etat/situation";
import { RestitutionChambres } from "./RestitutionChambres";
import { RestitutionHousekeeping } from "./RestitutionHousekeeping";

export function Recommandations() {
  const { session } = useSession();

  if (session.service === "chambres" && session.recommandation) {
    return (
      <div className="flex flex-col gap-5">
        <EnTeteDeDecision
          eyebrow="Gestion des chambres"
          titre={`Sejour ${session.reference}`}
        />
        <RestitutionChambres recommandation={session.recommandation} />
      </div>
    );
  }

  if (session.service === "housekeeping" && session.planification) {
    return (
      <div className="flex flex-col gap-5">
        <EnTeteDeDecision
          eyebrow="Housekeeping"
          titre={`Secteur ${session.secteur?.replace(/_/g, " ") ?? ""}`}
        />
        <RestitutionHousekeeping planification={session.planification} />
      </div>
    );
  }

  return <AucuneSituation />;
}

function EnTeteDeDecision({
  eyebrow,
  titre,
}: {
  eyebrow: string;
  titre: string;
}) {
  return (
    <Panneau ton="sourd" className="py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-service">
            {eyebrow}
          </p>
          <p className="font-display text-xl">{titre}</p>
        </div>
        <Pastille nature="neutre">Situation composee par le noyau</Pastille>
      </div>
    </Panneau>
  );
}

function AucuneSituation() {
  return (
    <Panneau className="flex flex-col items-start gap-4">
      <EnTeteDeSection eyebrow="Etape 2" titre="Aucune situation soumise" />
      <div className="flex items-start gap-3 text-service">
        <Inbox size={20} className="mt-0.5 shrink-0" />
        <p className="max-w-lg text-sm leading-relaxed">
          Designez une situation dans l'ecran d'analyse. Les options
          admissibles et les motifs de rejet s'afficheront ici.
        </p>
      </div>
      <Link
        to="/analyse"
        className="inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-encre px-5 py-2.5 text-sm font-medium text-creme transition-opacity hover:opacity-90"
      >
        Designer une situation
        <ArrowRight size={16} />
      </Link>
    </Panneau>
  );
}
