/**
 * Restitution de ce que le systeme a etabli, et decision du responsable.
 *
 * La proposition expose les consequences etablies et leur fondement. Elle
 * demeure une proposition: aucune n'est appliquee avant que le responsable ne
 * se prononce.
 *
 * Le detail du raisonnement est disponible mais replie: un responsable presse
 * doit pouvoir decider sans le lire, un responsable qui conteste doit pouvoir
 * l'examiner.
 */

import { useState } from "react";
import { Check, ChevronDown, PenLine, X } from "lucide-react";
import type { RelogementPropose } from "@/api/contrat";
import { Carte, EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";
import type { Traitement } from "@/etat/situation";
import { enJourLisible } from "@/etat/jour";

const MOTIFS: Record<string, string> = {
  sejour_en_conflit: "chambres deja reservees sur ces dates",
  categorie_inferieure: "chambres d'une categorie insuffisante",
  equipement_absent: "chambres depourvues de l'equipement exige",
  capacite_insuffisante: "chambres trop petites",
  non_prete: "chambres non encore nettoyees",
  bloquee: "chambres immobilisees",
  non_libre: "chambres deja occupees",
};

interface Proprietes {
  traitement: Traitement;
  surDecision: () => void;
  surReprise: () => void;
}

export function Proposition({
  traitement,
  surDecision,
  surReprise,
}: Proprietes) {
  const consequences = traitement.consequences;
  const recommandation = traitement.recommandation;

  return (
    <div className="flex flex-col gap-5">
      {consequences ? <Consequences consequences={consequences} /> : null}

      {recommandation ? (
        <Panneau ton="encre">
          <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-creme/60">
            {traitement.reference}
          </p>
          <p className="font-display text-[var(--text-enorme)] leading-none text-creme">
            {recommandation.chambre_proposee ?? "Aucune"}
          </p>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-creme/80">
            {recommandation.a_conclu
              ? `Cette chambre convient. ${recommandation.chambres_admissibles.length} chambres etaient possibles sur ${recommandation.chambres_examinees} examinees.`
              : `Aucune chambre ne convient parmi les ${recommandation.chambres_examinees} examinees.`}
          </p>
        </Panneau>
      ) : null}

      {traitement.etape === "proposition" ? (
        <Decision surDecision={surDecision} surReprise={surReprise} />
      ) : (
        <Panneau>
          <button
            type="button"
            onClick={surReprise}
            className="inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-accent px-6 py-3 text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            Traiter une autre situation
          </button>
        </Panneau>
      )}
    </div>
  );
}

function Consequences({
  consequences,
}: {
  consequences: ReturnType<() => NonNullable<Traitement["consequences"]>>;
}) {
  return (
    <>
      <Panneau ton={consequences.immobilise_la_chambre ? "encre" : "sourd"}>
        <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] opacity-60">
          Chambre {consequences.chambre}
        </p>
        <p
          className={[
            "font-display text-3xl leading-tight",
            consequences.immobilise_la_chambre ? "text-creme" : "text-encre",
          ].join(" ")}
        >
          {consequences.immobilise_la_chambre
            ? "La chambre devient indisponible"
            : "La chambre reste exploitable"}
        </p>

        {consequences.nombre_de_sejours > 0 ? (
          <p className="mt-3 text-sm leading-relaxed text-creme/80">
            {consequences.nombre_de_sejours} client
            {consequences.nombre_de_sejours > 1 ? "s" : ""} doi
            {consequences.nombre_de_sejours > 1 ? "vent" : "t"} etre reloge
            {consequences.nombre_de_sejours > 1 ? "s" : ""}.{" "}
            {consequences.sejours_sans_solution === 0
              ? "Une solution existe pour chacun."
              : `${consequences.sejours_sans_solution} sans solution automatique.`}
          </p>
        ) : null}
      </Panneau>

      {consequences.sejours_a_reloger.length > 0 ? (
        <Panneau>
          <EnTeteDeSection
            eyebrow="Relogements"
            titre="Clients concernes"
            action={
              consequences.est_entierement_resolu ? (
                <Pastille nature="conforme">Tous reloges</Pastille>
              ) : (
                <Pastille nature="attente">
                  {consequences.sejours_sans_solution} sans solution
                </Pastille>
              )
            }
          />
          <div className="flex flex-col gap-3">
            {consequences.sejours_a_reloger.map((relogement) => (
              <Relogement key={relogement.reservation} relogement={relogement} />
            ))}
          </div>
        </Panneau>
      ) : null}
    </>
  );
}

function Relogement({ relogement }: { relogement: RelogementPropose }) {
  const [detaille, setDetaille] = useState(false);

  return (
    <Carte retenue={relogement.a_trouve_une_chambre}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-display text-lg leading-snug">
            {relogement.reservation}
          </p>
          <p className="text-sm text-service">
            {relogement.nombre_personnes} personne
            {relogement.nombre_personnes > 1 ? "s" : ""}, du{" "}
            {enJourLisible(relogement.arrivee)} au{" "}
            {enJourLisible(relogement.depart)}
          </p>
        </div>

        {relogement.a_trouve_une_chambre ? (
          <div className="text-right">
            <p className="font-display text-2xl leading-none text-accent">
              {relogement.chambre_proposee}
            </p>
            <p className="mt-1 text-xs text-service">chambre proposee</p>
          </div>
        ) : (
          <Pastille nature="attente">A traiter manuellement</Pastille>
        )}
      </div>

      {!relogement.a_trouve_une_chambre &&
      relogement.motifs_dominants.length > 0 ? (
        <ul className="mt-3 flex flex-col gap-1">
          {relogement.motifs_dominants.map((motif) => {
            const [code = motif, compte] = motif.split(": ");
            const nombre = compte?.replace(" chambres", "") ?? "";
            return (
              <li key={motif} className="text-sm text-service">
                {nombre} {MOTIFS[code] ?? code}
              </li>
            );
          })}
        </ul>
      ) : null}

      <button
        type="button"
        onClick={() => setDetaille(!detaille)}
        className="mt-3 inline-flex items-center gap-1.5 text-sm text-service hover:text-encre"
        aria-expanded={detaille}
      >
        <ChevronDown
          size={14}
          className={detaille ? "rotate-180 transition-transform" : "transition-transform"}
        />
        {detaille ? "Masquer le detail" : "Comment cette proposition a ete etablie"}
      </button>

      {detaille ? (
        <div className="mt-3 rounded-[var(--radius-carte)] bg-sourd p-4">
          <p className="text-sm leading-relaxed text-encre">
            {relogement.justification}
          </p>
          <p className="mt-2 text-sm text-service">
            {relogement.chambres_admissibles} chambres convenaient sur{" "}
            {relogement.chambres_examinees} examinees.
          </p>
        </div>
      ) : null}
    </Carte>
  );
}

function Decision({
  surDecision,
  surReprise,
}: {
  surDecision: () => void;
  surReprise: () => void;
}) {
  return (
    <Panneau>
      <EnTeteDeSection eyebrow="Etape 3" titre="Votre decision" />
      <p className="mb-4 max-w-2xl text-sm leading-relaxed text-service">
        Rien n'a ete applique. Validez pour engager les changements proposes,
        ou reprenez si la proposition ne convient pas.
      </p>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={surDecision}
          className="inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-accent px-6 py-3 text-sm font-medium text-white transition-opacity hover:opacity-90"
        >
          <Check size={16} />
          Valider
        </button>
        <button
          type="button"
          onClick={surDecision}
          className="inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-sourd px-5 py-3 text-sm font-medium text-encre transition-colors hover:bg-bordure"
        >
          <PenLine size={16} />
          Corriger
        </button>
        <button
          type="button"
          onClick={surReprise}
          className="inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-sourd px-5 py-3 text-sm font-medium text-encre transition-colors hover:bg-bordure"
        >
          <X size={16} />
          Refuser
        </button>
      </div>
    </Panneau>
  );
}