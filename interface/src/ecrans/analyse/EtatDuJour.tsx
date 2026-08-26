/**
 * Restitution de l'etat courant de l'etablissement.
 *
 * Les grandeurs presentees sont celles qui conditionnent les decisions du
 * jour: ce qui reste disponible, ce qui attend une decision, ce qui est
 * immobilise.
 */

import type { EtatDeLEtablissement } from "@/api/contrat";
import { EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";
import { enJourLisible } from "@/etat/jour";

interface Grandeur {
  libelle: string;
  valeur: number;
  accentuee?: boolean;
}

interface Proprietes {
  etat: EtatDeLEtablissement | undefined;
  enChargement: boolean;
  jour: string;
}

export function EtatDuJour({ etat, enChargement, jour }: Proprietes) {
  if (enChargement || !etat) {
    return (
      <Panneau ton="sourd">
        <EnTeteDeSection eyebrow="Etablissement" titre="Consultation en cours" />
        <p className="text-sm text-service">
          Lecture de l'etat operationnel.
        </p>
      </Panneau>
    );
  }

  const grandeurs: Grandeur[] = [
    { libelle: "chambres", valeur: etat.chambres },
    { libelle: "disponibles", valeur: etat.disponibles },
    {
      libelle: "arrivees a traiter",
      valeur: etat.arrivees_a_traiter,
      accentuee: true,
    },
    {
      libelle: "taches a planifier",
      valeur: etat.taches_a_planifier,
      accentuee: true,
    },
    { libelle: "agents en service", valeur: etat.agents_affectables },
    { libelle: "incidents ouverts", valeur: etat.incidents_ouverts },
  ];

  return (
    <Panneau ton="encre">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-creme/60">
            Etat operationnel
          </p>
          <h2 className="font-display text-2xl text-creme">
            Journee du {enJourLisible(jour)}
          </h2>
        </div>
        <Pastille nature="accent">
          {etat.arrivees_a_traiter + etat.taches_a_planifier} decisions en
          attente
        </Pastille>
      </div>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3 lg:grid-cols-6">
        {grandeurs.map(({ libelle, valeur, accentuee }) => (
          <div key={libelle}>
            <dd
              className={[
                "font-display text-4xl leading-none",
                accentuee ? "text-accent" : "text-creme",
              ].join(" ")}
            >
              {valeur}
            </dd>
            <dt className="mt-1.5 text-sm text-creme/60">{libelle}</dt>
          </div>
        ))}
      </dl>
    </Panneau>
  );
}
