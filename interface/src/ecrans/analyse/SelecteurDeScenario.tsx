/**
 * Selection d'une situation parmi les situations de reference.
 */

import { Carte } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";
import type { Service } from "@/etat/situation";

export interface Scenario {
  reference: string;
  service: Service;
  titre: string;
  resume: string;
  attendu: string;
}

interface Proprietes {
  scenarios: Scenario[];
  choisi: string;
  surChoix: (reference: string) => void;
}

export function SelecteurDeScenario({
  scenarios,
  choisi,
  surChoix,
}: Proprietes) {
  return (
    <div
      role="radiogroup"
      aria-label="Situations de reference"
      className="grid gap-4 sm:grid-cols-2"
    >
      {scenarios.map((scenario) => {
        const retenu = scenario.reference === choisi;
        return (
          <Carte key={scenario.reference} interactive retenue={retenu}>
            <button
              type="button"
              role="radio"
              aria-checked={retenu}
              onClick={() => surChoix(scenario.reference)}
              className="w-full text-left"
            >
              <div className="mb-2 flex items-start justify-between gap-3">
                <h3 className="font-display text-lg leading-snug">
                  {scenario.titre}
                </h3>
                <Pastille nature={retenu ? "accent" : "neutre"}>
                  {scenario.service === "chambres" ? "Chambres" : "Etages"}
                </Pastille>
              </div>
              <p className="text-sm leading-relaxed text-service">
                {scenario.resume}
              </p>
            </button>
          </Carte>
        );
      })}
    </div>
  );
}