/**
 * Restitution integrale de la trace du raisonnement.
 *
 * La trace permet au responsable de verifier que la justification correspond
 * au raisonnement effectivement conduit. Elle constitue le fondement de la
 * fidelite explicative: chaque enonce restitue se rattache a un element de
 * cette trace.
 */

import { EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";
import type { Session } from "@/etat/situation";

export function TraceDuRaisonnement({ session }: { session: Session }) {
  const enonces =
    session.service === "chambres"
      ? (session.recommandation?.justification.split("\n") ?? [])
      : (session.planification?.justification ?? []);

  const elements = compterElements(session);

  return (
    <Panneau ton="sourd">
      <EnTeteDeSection
        eyebrow="Verification"
        titre="Trace du raisonnement"
        action={
          <Pastille nature="neutre">
            {elements} elements mobilises
          </Pastille>
        }
      />
      <ol className="flex flex-col">
        {enonces.map((enonce, rang) => (
          <li
            key={enonce}
            className="flex gap-4 border-t border-bordure py-3 first:border-t-0 first:pt-0"
          >
            <span className="w-8 shrink-0 text-sm tabular-nums text-service">
              {String(rang + 1).padStart(2, "0")}
            </span>
            <span className="text-sm leading-relaxed text-encre">{enonce}</span>
          </li>
        ))}
      </ol>
      <p className="mt-4 text-sm leading-relaxed text-service">
        Chaque enonce derive d'un element etabli par le raisonnement. Aucun
        contenu n'est ajoute a la formulation.
      </p>
    </Panneau>
  );
}

function compterElements(session: Session): number {
  if (session.service === "chambres" && session.recommandation) {
    const motifs = session.recommandation.options_ecartees.reduce(
      (total, option) => total + option.motifs.length,
      0,
    );
    return motifs + session.recommandation.contreparties.length + 1;
  }
  if (session.planification) {
    return (
      session.planification.affectations.length +
      session.planification.taches_en_attente.length +
      1
    );
  }
  return 0;
}