/**
 * Consultation des decisions consignees.
 *
 * Le journal est en ajout seul: une decision consignee demeure consultable
 * telle qu'elle a ete prise, avec les regles en vigueur a cette date. La
 * persistance releve du noyau et n'est pas encore exposee.
 */

import { Archive } from "lucide-react";
import { EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";

export function Historique() {
  return (
    <Panneau className="flex flex-col items-start gap-4">
      <EnTeteDeSection
        eyebrow="Audit"
        titre="Journal des decisions"
        action={<Pastille nature="neutre">Ajout seul</Pastille>}
      />
      <div className="flex items-start gap-3 text-service">
        <Archive size={20} className="mt-0.5 shrink-0" />
        <p className="max-w-2xl text-sm leading-relaxed">
          Le journal consignera chaque situation analysee, la proposition
          etablie, la decision du responsable et son motif. Une decision
          consignee demeurera consultable avec les regles en vigueur a sa date,
          ce qui permet de reconstituer un raisonnement passe.
        </p>
      </div>
      <p className="text-sm text-service">
        La persistance releve de la couche de donnees, encore a construire.
      </p>
    </Panneau>
  );
}