/**
 * Restitution d'une repartition de charge.
 *
 * La repartition etablit une organisation possible, non une affectation:
 * l'attribution effective des chambres aux agents releve du responsable, qui
 * connait les competences et les contraintes que le systeme ignore.
 */

import { Users } from "lucide-react";
import type { RepartitionRestituee } from "@/api/contrat";
import { Carte, EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";

export function Repartition({
  repartition,
}: {
  repartition: RepartitionRestituee;
}) {
  return (
    <>
      <Panneau ton="encre">
        <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-creme/60">
          {repartition.chambres} chambres · {repartition.agents} agents
        </p>
        <div className="flex flex-wrap items-end gap-x-3 gap-y-1">
          <p className="font-display text-[var(--text-enorme)] leading-none text-creme">
            {repartition.duree}
          </p>
          <p className="pb-1 font-display text-base text-creme sm:text-xl lg:text-2xl">
            avant l'achevement du service
          </p>
        </div>
      </Panneau>

      <Panneau>
        <EnTeteDeSection
          eyebrow="Repartition"
          titre="Charge par agent"
          action={
            repartition.est_equilibree ? (
              <Pastille nature="conforme">Equilibree</Pastille>
            ) : (
              <Pastille nature="attente">Inegale d'une chambre</Pastille>
            )
          }
        />

        <div className="mb-4 grid grid-cols-3 gap-2 sm:grid-cols-4 sm:gap-3 lg:grid-cols-6">
          {repartition.parts.map((part) => (
            <Carte key={part.rang}>
              <div className="flex items-center gap-2 sm:gap-3">
                <Users size={15} className="hidden shrink-0 text-service sm:block" />
                <div className="min-w-0">
                  <p className="font-display text-base leading-none sm:text-lg">
                    Agent {part.rang}
                  </p>
                  <p className="mt-1 text-xs text-service sm:text-sm">
                    {part.chambres} ch. · {part.duree}
                  </p>
                </div>
              </div>
            </Carte>
          ))}
        </div>

        <ul className="flex flex-col gap-2 border-t border-bordure pt-4">
          {repartition.justification.map((enonce) => (
            <li key={enonce} className="text-sm leading-relaxed text-encre">
              {enonce}
            </li>
          ))}
        </ul>
      </Panneau>
    </>
  );
}
