/**
 * Choix du secteur dont le service est a organiser.
 *
 * Les secteurs sont deduits des taches en attente: presenter un secteur sans
 * charge conduirait a une planification vide.
 */

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, RefreshCw } from "lucide-react";
import { consulterAgents, consulterTaches } from "@/api/client";
import { Carte, EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";

interface Proprietes {
  enCours: boolean;
  secteurEnCours: string | null;
  surChoix: (secteur: string) => void;
}

export function ServicesDEtage({
  enCours,
  secteurEnCours,
  surChoix,
}: Proprietes) {
  const taches = useQuery({ queryKey: ["taches"], queryFn: () => consulterTaches() });
  const agents = useQuery({ queryKey: ["agents"], queryFn: () => consulterAgents() });

  if (taches.isPending || agents.isPending) {
    return (
      <Panneau>
        <EnTeteDeSection eyebrow="Housekeeping" titre="Consultation en cours" />
      </Panneau>
    );
  }

  const parSecteur = new Map<string, { taches: number; agents: number }>();
  for (const tache of taches.data ?? []) {
    const compte = parSecteur.get(tache.secteur) ?? { taches: 0, agents: 0 };
    compte.taches += 1;
    parSecteur.set(tache.secteur, compte);
  }
  for (const agent of agents.data ?? []) {
    const compte = parSecteur.get(agent.secteur);
    if (compte && agent.affectable) {
      compte.agents += 1;
    }
  }

  if (parSecteur.size === 0) {
    return (
      <Panneau ton="sourd">
        <EnTeteDeSection eyebrow="Housekeeping" titre="Aucune tache en attente" />
        <p className="max-w-lg text-sm leading-relaxed text-service">
          Le service d'etage n'a rien a planifier. Constituez un etablissement
          pour observer une planification.
        </p>
      </Panneau>
    );
  }

  return (
    <Panneau>
      <EnTeteDeSection
        eyebrow="Housekeeping"
        titre="Secteurs a organiser"
        action={
          <Pastille nature="neutre">{parSecteur.size} secteurs</Pastille>
        }
      />

      <div className="grid gap-3 md:grid-cols-3">
        {[...parSecteur.entries()]
          .sort(([gauche], [droite]) => gauche.localeCompare(droite))
          .map(([secteur, compte]) => {
            const traite = enCours && secteurEnCours === secteur;
            const sansAgent = compte.agents === 0;
            return (
              <Carte key={secteur} interactive retenue={traite}>
                <button
                  type="button"
                  disabled={enCours}
                  onClick={() => surChoix(secteur)}
                  className="w-full text-left disabled:opacity-60"
                >
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <p className="font-display text-lg">
                      {secteur.replace(/_/g, " ")}
                    </p>
                    {traite ? (
                      <RefreshCw size={16} className="animate-spin text-accent" />
                    ) : (
                      <ArrowRight size={16} className="text-service" />
                    )}
                  </div>

                  <div className="flex items-baseline gap-4">
                    <div>
                      <p className="font-display text-3xl leading-none text-accent">
                        {compte.taches}
                      </p>
                      <p className="mt-1 text-sm text-service">taches</p>
                    </div>
                    <div>
                      <p className="font-display text-2xl leading-none">
                        {compte.agents}
                      </p>
                      <p className="mt-1 text-sm text-service">agents</p>
                    </div>
                  </div>

                  {sansAgent ? (
                    <p className="mt-3 text-sm text-accent">
                      Aucun agent en service sur ce secteur
                    </p>
                  ) : null}
                </button>
              </Carte>
            );
          })}
      </div>
    </Panneau>
  );
}
