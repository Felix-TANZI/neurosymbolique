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
        <p className="font-display text-[var(--text-enorme)] leading-none text-creme">
          {repartition.duree}
        </p>
        <p className="mt-2 font-display text-2xl text-creme">
          avant l'achevement du service
        </p>
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

        <div className="mb-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {repartition.parts.map((part) => (
            <Carte key={part.rang}>
              <div className="flex items-center gap-3">
                <Users size={16} className="shrink-0 text-service" />
                <div>
                  <p className="font-display text-lg leading-none">
                    Agent {part.rang}
                  </p>
                  <p className="mt-1 text-sm text-service">
                    {part.chambres} chambres · {part.duree}
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
