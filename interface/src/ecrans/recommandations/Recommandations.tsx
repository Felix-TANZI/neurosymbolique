/**
 * Restitution de l'issue du raisonnement.
 *
 * L'ecran presente la recommandation, les contreparties consenties et le
 * motif de rejet de chaque option ecartee. Aucune decision n'est appliquee:
 * la validation demeure une action distincte.
 */

import { Link } from "react-router-dom";
import { ArrowRight, Inbox } from "lucide-react";
import { EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { useSession } from "@/etat/situation";
import { RestitutionChambres } from "./RestitutionChambres";
import { RestitutionHousekeeping } from "./RestitutionHousekeeping";

export function Recommandations() {
  const { session } = useSession();

  if (session.service === "chambres" && session.recommandation) {
    return <RestitutionChambres recommandation={session.recommandation} />;
  }

  if (session.service === "housekeeping" && session.planification) {
    return <RestitutionHousekeeping planification={session.planification} />;
  }

  return <AucuneSituation />;
}

function AucuneSituation() {
  return (
    <Panneau className="flex flex-col items-start gap-4">
      <EnTeteDeSection
        eyebrow="Etape 2"
        titre="Aucune situation soumise"
      />
      <div className="flex items-start gap-3 text-service">
        <Inbox size={20} className="mt-0.5 shrink-0" />
        <p className="max-w-lg text-sm leading-relaxed">
          Choisissez une situation dans l'ecran d'analyse et soumettez-la au
          raisonnement. Les options admissibles et les motifs de rejet
          s'afficheront ici.
        </p>
      </div>
      <Link
        to="/analyse"
        className="inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-encre px-5 py-2.5 text-sm font-medium text-creme transition-opacity hover:opacity-90"
      >
        Decrire une situation
        <ArrowRight size={16} />
      </Link>
    </Panneau>
  );
}