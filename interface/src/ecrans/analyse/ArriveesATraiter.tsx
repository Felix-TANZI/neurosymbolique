/**
 * Liste des sejours arrivant sans chambre affectee.
 *
 * Chaque sejour constitue une decision a prendre. Les exigences obligatoires
 * sont distinguees des souhaits: les premieres ecartent une chambre, les
 * secondes degradent seulement la qualite du choix.
 */

import { ArrowRight, Clock, RefreshCw } from "lucide-react";
import type { ReservationConsultee } from "@/api/contrat";
import { Carte, EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { ListeDePastilles, Pastille } from "@/composants/Pastille";
import { enHeureLisible } from "@/etat/jour";

const CATEGORIES: Record<number, string> = {
  1: "Standard",
  2: "Superieure",
  3: "Junior suite",
  4: "Suite",
};

interface Proprietes {
  arrivees: ReservationConsultee[];
  enChargement: boolean;
  enCours: boolean;
  referenceEnCours: string | null;
  surChoix: (reference: string) => void;
}

export function ArriveesATraiter({
  arrivees,
  enChargement,
  enCours,
  referenceEnCours,
  surChoix,
}: Proprietes) {
  if (enChargement) {
    return (
      <Panneau>
        <EnTeteDeSection eyebrow="Chambres" titre="Consultation en cours" />
      </Panneau>
    );
  }

  if (arrivees.length === 0) {
    return (
      <Panneau ton="sourd">
        <EnTeteDeSection
          eyebrow="Chambres"
          titre="Aucune arrivee en attente"
        />
        <p className="max-w-lg text-sm leading-relaxed text-service">
          Tous les sejours du jour disposent d'une chambre. Constituez un
          etablissement ou changez de journee pour observer une decision.
        </p>
      </Panneau>
    );
  }

  return (
    <Panneau>
      <EnTeteDeSection
        eyebrow="Chambres"
        titre="Arrivees sans chambre affectee"
        action={<Pastille nature="neutre">{arrivees.length} sejours</Pastille>}
      />

      <div className="grid gap-3 md:grid-cols-2">
        {arrivees.map((sejour) => {
          const traite = enCours && referenceEnCours === sejour.identifiant;
          return (
            <Carte key={sejour.identifiant} interactive retenue={traite}>
              <button
                type="button"
                disabled={enCours}
                onClick={() => surChoix(sejour.identifiant)}
                className="w-full text-left disabled:opacity-60"
              >
                <div className="mb-2 flex items-start justify-between gap-3">
                  <div>
                    <p className="font-display text-lg leading-snug">
                      {sejour.identifiant}
                    </p>
                    <p className="text-sm text-service">
                      {sejour.nombre_personnes} personne
                      {sejour.nombre_personnes > 1 ? "s" : ""} ·{" "}
                      {sejour.nuitees} nuitee{sejour.nuitees > 1 ? "s" : ""} ·{" "}
                      {CATEGORIES[sejour.categorie_contractee] ?? "Standard"}
                    </p>
                  </div>
                  {traite ? (
                    <RefreshCw size={16} className="mt-1 animate-spin text-accent" />
                  ) : (
                    <ArrowRight size={16} className="mt-1 text-service" />
                  )}
                </div>

                <div className="mb-3 flex items-center gap-1.5 text-sm text-service">
                  <Clock size={14} />
                  <span>
                    Arrivee {enHeureLisible(sejour.heure_arrivee_prevue)}
                  </span>
                  {sejour.arrivee_anticipee ? (
                    <span className="text-accent">
                      · avant l'acces garanti
                    </span>
                  ) : null}
                </div>

                <ListeDePastilles>
                  {sejour.exigences_obligatoires.map((equipement) => (
                    <Pastille key={equipement} nature="accent">
                      {equipement.replace(/_/g, " ")}
                    </Pastille>
                  ))}
                  {sejour.exigences_souhaitees.map((equipement) => (
                    <Pastille key={equipement} nature="neutre">
                      {equipement.replace(/_/g, " ")}
                    </Pastille>
                  ))}
                  {sejour.statut_fidelite >= 3 ? (
                    <Pastille nature="conforme">Client fidele</Pastille>
                  ) : null}
                </ListeDePastilles>
              </button>
            </Carte>
          );
        })}
      </div>
    </Panneau>
  );
}
