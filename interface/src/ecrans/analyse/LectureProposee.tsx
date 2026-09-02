/**
 * Restitution d'une lecture soumise a confirmation.
 *
 * La lecture expose ce que le noyau a compris et ce dont il n'est pas assure.
 * Les elements sans correspondance dans l'etablissement sont signales comme
 * tels: le responsable voit ce qui a ete lu et ce qui a ete verifie, non
 * seulement une conclusion.
 *
 * La confirmation est requise dans tous les cas. Une lecture recevable est
 * confirmee d'un geste, une lecture reservee appelle un examen: la difference
 * tient au degre d'attention demande, non a l'existence du controle.
 */

import { Check, CircleAlert, CircleCheck, X } from "lucide-react";
import type { LectureRestituee, ReserveExprimee } from "@/api/contrat";
import { Carte } from "@/composants/Panneau";
import { ListeDePastilles, Pastille } from "@/composants/Pastille";

const INTENTIONS: Record<string, string> = {
  degat_des_eaux: "Degat des eaux",
  panne_electrique: "Panne electrique",
  panne_climatisation: "Panne de climatisation",
  panne_plomberie: "Panne de plomberie",
  defaut_serrure: "Defaut de serrure",
  mobilier_endommage: "Mobilier endommage",
  nuisance_sonore: "Nuisance sonore",
  risque_securite: "Risque de securite",
  demande_affectation: "Demande d'affectation",
  demande_changement: "Demande de changement",
  signalement_indisponibilite: "Mise en indisponibilite",
  arrivee_anticipee: "Arrivee anticipee",
  chambre_urgente: "Chambre urgente",
  agent_indisponible: "Agent indisponible",
  demande_planification: "Demande de planification",
};

const RESERVES: Record<string, string> = {
  confiance_insuffisante:
    "Le noyau n'est pas assure de sa lecture. Verifiez l'intention retenue.",
  entite_inexistante:
    "Un element mentionne ne correspond a rien dans l'etablissement.",
  entite_manquante:
    "Un element indispensable n'a pas ete reconnu dans l'enonce.",
  hors_perimetre: "L'enonce ne releve pas des situations traitees.",
};

interface Proprietes {
  lecture: LectureRestituee;
  surConfirmation: () => void;
  surAbandon: () => void;
}

export function LectureProposee({
  lecture,
  surConfirmation,
  surAbandon,
}: Proprietes) {
  const reservee = lecture.recevabilite !== "recevable";
  const irrecevable = lecture.recevabilite === "irrecevable";

  return (
    <Carte retenue={!reservee} className="mt-2">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-service">
            Situation reconnue
          </p>
          <p className="font-display text-2xl leading-snug">
            {INTENTIONS[lecture.intention] ?? "Aucune situation reconnue"}
          </p>
        </div>
        <Confiance valeur={lecture.confiance} reservee={reservee} />
      </div>

      {lecture.entites.length > 0 ? (
        <div className="mb-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-service">
            Elements reconnus
          </p>
          <ListeDePastilles>
            {lecture.entites.map((entite) => (
              <Pastille
                key={`${entite.type_d_entite}-${entite.valeur}`}
                nature={entite.existe === false ? "attente" : "accent"}
              >
                {entite.type_d_entite.replace(/_/g, " ")} · {entite.valeur}
                {entite.existe === false ? " (inexistant)" : ""}
              </Pastille>
            ))}
          </ListeDePastilles>
        </div>
      ) : null}

      {lecture.reserves.length > 0 ? (
        <Reserves reserves={lecture.reserves} />
      ) : null}

      <div className="flex flex-wrap items-center gap-3 border-t border-bordure pt-4">
        <button
          type="button"
          onClick={surConfirmation}
          disabled={irrecevable}
          className="inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-accent px-5 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          <Check size={16} />
          {reservee ? "Confirmer malgre la reserve" : "Confirmer cette lecture"}
        </button>
        <button
          type="button"
          onClick={surAbandon}
          className="inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-sourd px-5 py-2.5 text-sm font-medium text-encre transition-colors hover:bg-bordure"
        >
          <X size={16} />
          Reformuler
        </button>
        <p className="text-sm text-service">
          Aucune action n'est engagee avant votre confirmation.
        </p>
      </div>
    </Carte>
  );
}

function Confiance({
  valeur,
  reservee,
}: {
  valeur: number;
  reservee: boolean;
}) {
  return (
    <div className="flex items-center gap-2 shrink-0">
      {reservee ? (
        <CircleAlert size={18} className="text-attente" />
      ) : (
        <CircleCheck size={18} className="text-succes" />
      )}
      <div className="text-right">
        <p className="font-display text-2xl leading-none tabular-nums">
          {Math.round(valeur * 100)}
          <span className="text-base">%</span>
        </p>
        <p className="text-xs text-service">confiance</p>
      </div>
    </div>
  );
}

function Reserves({ reserves }: { reserves: ReserveExprimee[] }) {
  return (
    <div className="mb-4 rounded-[var(--radius-carte)] bg-accent-sourd p-4">
      <p className="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-accent">
        Points a verifier
      </p>
      <ul className="flex flex-col gap-2">
        {reserves.map((reserve) => (
          <li
            key={`${reserve.motif}-${reserve.detail}`}
            className="text-sm leading-relaxed text-encre"
          >
            {RESERVES[reserve.motif] ?? reserve.motif}
            {reserve.detail ? (
              <span className="text-service"> — {reserve.detail}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}