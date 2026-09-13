/**
 * Presentation d'une reponse selon sa nature.
 *
 * Une consultation restitue un etat: elle s'affiche et se referme. Un
 * arbitrage ou des consequences constituent une proposition: ils appellent une
 * decision du responsable. Presenter les deux de la meme maniere conduirait
 * soit a faire valider une simple information, soit a laisser appliquer une
 * decision sans qu'elle ait ete arretee.
 */

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Check,
  ChevronDown,
  Info,
  PenLine,
  RotateCcw,
  TriangleAlert,
  X,
} from "lucide-react";
import { consignerUneDecision } from "@/api/client";
import type {
  ArbitrageRestitue,
  ConsequencesRestituees,
  EtatRestitue,
  IssueDeDecision,
  OptionProposee,
  RelogementPropose,
  ReponseRestituee,
} from "@/api/contrat";
import { Carte, EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";
import { Abstention, Risque } from "@/composants/Risque";
import { enJourLisible } from "@/etat/jour";
import { PlanDIntervention } from "./PlanDIntervention";
import { Repartition } from "./Repartition";

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
  reponse: ReponseRestituee;
  surReprise: () => void;
}

export function Restitution({ reponse, surReprise }: Proprietes) {
  const consignation = useMutation({
    mutationFn: (decision: {
      issue: IssueDeDecision;
      motif: string;
    }) =>
      consignerUneDecision({
        service: reponse.consequences ? "chambres" : "arbitrage",
        situation: reponse.lecture.enonce,
        proposition: _resumerLaProposition(reponse),
        justification: _rassemblerLaJustification(reponse),
        issue: decision.issue,
        motif: decision.motif,
      }),
  });

  if (
    reponse.risque?.abstention &&
    (reponse.nature === "hors_perimetre" ||
      reponse.nature === "confirmation_requise")
  ) {
    return (
      <Panneau>
        <Abstention risque={reponse.risque} surReprise={surReprise} />
      </Panneau>
    );
  }

  if (reponse.nature === "consultation" && reponse.etat) {
    return <Consultation etat={reponse.etat} surReprise={surReprise} />;
  }

  if (reponse.nature === "repartition" && reponse.repartition) {
    return (
      <div className="flex flex-col gap-3 sm:gap-5">
        <Repartition repartition={reponse.repartition} />
        <Panneau>
          <button
            type="button"
            onClick={surReprise}
            className="inline-flex items-center gap-2 text-sm font-medium text-accent hover:underline"
          >
            <RotateCcw size={14} />
            Poser une autre question
          </button>
        </Panneau>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 sm:gap-5">
      {reponse.arbitrage ? <Arbitrage arbitrage={reponse.arbitrage} /> : null}
      {reponse.consequences ? (
        <Consequences consequences={reponse.consequences} />
      ) : null}
      {reponse.repartition ? (
        <Repartition repartition={reponse.repartition} />
      ) : null}
      {reponse.plan ? <PlanDIntervention plan={reponse.plan} /> : null}

      {reponse.risque && reponse.risque.appelle_une_verification ? (
        <Panneau ton="sourd">
          <Risque risque={reponse.risque} />
        </Panneau>
      ) : null}

      {consignation.isSuccess ? (
        <Panneau ton="sourd">
          <p className="mb-4 text-sm leading-relaxed text-service">
            La decision est consignee au journal, avec la situation et le
            raisonnement qui l'a produite. L'etat de l'etablissement demeure
            inchange : son application releve de vos procedures.
          </p>
          <button
            type="button"
            onClick={surReprise}
            className="inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-accent px-6 py-3 text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            Traiter une autre situation
          </button>
        </Panneau>
      ) : (
        <Decision
          enCours={consignation.isPending}
          anomalie={consignation.error}
          surDecision={(issue, motif) => consignation.mutate({ issue, motif })}
          surReprise={surReprise}
        />
      )}
    </div>
  );
}

function Consultation({
  etat,
  surReprise,
}: {
  etat: EtatRestitue;
  surReprise: () => void;
}) {
  return (
    <Panneau>
      <div className="mb-4 flex items-start gap-3">
        <Info size={18} className="mt-1 shrink-0 text-service" />
        <p className="font-display text-lg leading-snug sm:text-xl lg:text-2xl">
          {etat.enonce}
        </p>
      </div>

      {etat.elements.length > 0 ? (
        <ul className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-4">
          {etat.elements.map((element) => (
            <li
              key={element}
              className="min-w-0 rounded-[var(--radius-carte)] bg-sourd px-3 py-2 text-xs leading-snug sm:px-4 sm:py-2.5 sm:text-sm"
            >
              {element}
            </li>
          ))}
        </ul>
      ) : null}

      <button
        type="button"
        onClick={surReprise}
        className="inline-flex items-center gap-2 text-sm font-medium text-accent hover:underline"
      >
        <RotateCcw size={14} />
        Poser une autre question
      </button>
    </Panneau>
  );
}

function Arbitrage({ arbitrage }: { arbitrage: ArbitrageRestitue }) {
  if (arbitrage.nature === "absent") {
    return (
      <Panneau ton="sourd">
        <div className="flex items-start gap-3">
          <Info size={18} className="mt-1 shrink-0 text-service" />
          <div>
            {arbitrage.constats.map((constat) => (
              <p key={constat} className="text-sm leading-relaxed">
                {constat}
              </p>
            ))}
          </div>
        </div>
      </Panneau>
    );
  }

  return (
    <>
      <Panneau ton="encre">
        <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-creme/60">
          Chambre {arbitrage.chambre}
        </p>
        <p className="font-display text-xl leading-tight text-creme sm:text-2xl lg:text-3xl">
          {arbitrage.chambre_proposee
            ? `${arbitrage.sejour_a_reloger} est reloge en ${arbitrage.chambre_proposee}`
            : `${arbitrage.sejour_a_reloger} ne peut etre reloge`}
        </p>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-creme/80">
          {arbitrage.motif}
        </p>
      </Panneau>

      {arbitrage.anomalie ? (
        <Panneau>
          <div className="flex items-start gap-3 rounded-[var(--radius-carte)] bg-accent-sourd p-4">
            <TriangleAlert size={18} className="mt-0.5 shrink-0 text-accent" />
            <div>
              <p className="text-sm font-medium text-accent">
                Anomalie constatee
              </p>
              <p className="mt-1 text-sm leading-relaxed text-encre">
                Deux clients occupent simultanement cette chambre. Verifiez la
                situation sur place avant d'appliquer la proposition.
              </p>
            </div>
          </div>
        </Panneau>
      ) : null}

      <Panneau>
        <EnTeteDeSection eyebrow="Situation" titre="Ce qui a ete etabli" />
        <ul className="mb-4 flex flex-col gap-2">
          {arbitrage.constats.map((constat) => (
            <li key={constat} className="text-sm leading-relaxed text-encre">
              {constat}
            </li>
          ))}
        </ul>

        {arbitrage.justification ? (
          <p className="rounded-[var(--radius-carte)] bg-sourd p-4 text-sm leading-relaxed">
            {arbitrage.justification}
          </p>
        ) : null}
      </Panneau>

      {arbitrage.leviers.length > 0 ? (
        <Panneau>
          <EnTeteDeSection
            eyebrow="Aucune solution directe"
            titre="Ce que vous pouvez concéder"
            action={<Pastille nature="attente">{arbitrage.leviers.length}</Pastille>}
          />
          <p className="mb-4 max-w-2xl text-sm leading-relaxed text-service">
            Aucune chambre ne satisfait toutes les contraintes. Relacher l'une
            d'elles ouvrirait une solution.
          </p>
          <div className="grid gap-2 sm:grid-cols-2 sm:gap-3 xl:grid-cols-3">
            {arbitrage.leviers.map((levier) => (
              <Carte key={levier.enonce}>
                <p className="text-sm leading-relaxed">{levier.enonce}</p>
                {levier.chambres_ainsi_ouvertes > 0 ? (
                  <p className="mt-1.5 text-sm text-service">
                    {levier.chambres_ainsi_ouvertes} chambres deviendraient
                    admissibles
                  </p>
                ) : null}
              </Carte>
            ))}
          </div>
        </Panneau>
      ) : null}
    </>
  );
}

function Consequences({
  consequences,
}: {
  consequences: ConsequencesRestituees;
}) {
  return (
    <>
      <Panneau ton={consequences.immobilise_la_chambre ? "encre" : "sourd"}>
        <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] opacity-60">
          Chambre {consequences.chambre}
        </p>
        <p
          className={[
            "font-display text-xl leading-tight sm:text-2xl lg:text-3xl",
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
  const plusieurs = relogement.options.length > 1;

  return (
    <Carte retenue={relogement.a_trouve_une_chambre}>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-4">
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

        {!relogement.a_trouve_une_chambre ? (
          <Pastille nature="attente">A traiter manuellement</Pastille>
        ) : plusieurs ? (
          <Pastille nature="accent">
            {relogement.options.length} possibilites
          </Pastille>
        ) : null}
      </div>

      {relogement.options.length > 0 ? (
        <>
          {relogement.options_equivalentes ? (
            <p className="mb-2 text-sm text-service">
              Ces chambres conviennent également. Aucun critère ne les
              départage.
            </p>
          ) : null}

          <ul className="grid grid-cols-2 gap-2 md:grid-cols-3">
            {relogement.options.map((option) => (
              <OptionRetenue key={option.chambre} option={option} />
            ))}
          </ul>
        </>
      ) : null}

      {!relogement.a_trouve_une_chambre &&
      relogement.motifs_dominants.length > 0 ? (
        <ul className="mt-1 flex flex-col gap-1">
          {relogement.motifs_dominants.map((motif) => {
            const [code = "", compte] = motif.split(": ");
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
          className={
            detaille
              ? "rotate-180 transition-transform"
              : "transition-transform"
          }
        />
        {detaille ? "Masquer le detail" : "Comment ces propositions ont ete etablies"}
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

function OptionRetenue({ option }: { option: OptionProposee }) {
  return (
    <li
      className={[
        "min-w-0 rounded-[var(--radius-carte)] px-3 py-2.5 sm:px-4 sm:py-3",
        option.rang === 1 ? "bg-accent-sourd" : "bg-sourd",
      ].join(" ")}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p
          className={[
            "font-display text-lg leading-none sm:text-xl",
            option.rang === 1 ? "text-accent" : "text-encre",
          ].join(" ")}
        >
          {option.chambre}
        </p>
        {option.convoitee ? (
          <span className="text-xs text-attente">
            egalement proposee a un autre client
          </span>
        ) : null}
      </div>

      {option.avantages.length > 0 || option.contreparties.length > 0 ? (
        <ul className="mt-2 flex flex-col gap-1">
          {option.avantages.map((avantage) => (
            <li key={avantage} className="text-xs leading-snug text-succes sm:text-sm">
              {avantage}
            </li>
          ))}
          {option.contreparties.map((contrepartie) => (
            <li
              key={contrepartie}
              className="text-xs leading-snug text-service sm:text-sm"
            >
              {contrepartie}
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function Decision({
  enCours,
  anomalie,
  surDecision,
  surReprise,
}: {
  enCours: boolean;
  anomalie: unknown;
  surDecision: (issue: IssueDeDecision, motif: string) => void;
  surReprise: () => void;
}) {
  const [motif, setMotif] = useState("");
  const [demandee, setDemandee] = useState<IssueDeDecision | null>(null);

  const engager = (issue: IssueDeDecision) => {
    if (issue === "validee") {
      surDecision(issue, motif);
      return;
    }
    if (demandee === issue && motif.trim()) {
      surDecision(issue, motif.trim());
      return;
    }
    setDemandee(issue);
  };

  return (
    <Panneau>
      <EnTeteDeSection eyebrow="Decision" titre="Que faites-vous ?" />
      <p className="mb-4 hidden max-w-2xl text-sm leading-relaxed text-service sm:block">
        Rien n'est applique. Votre decision est consignee au journal avec le
        raisonnement qui l'a produite.
      </p>

      {demandee ? (
        <div className="mb-4">
          <label htmlFor="motif" className="mb-2 block text-sm text-service">
            {demandee === "corrigee"
              ? "Quelle decision retenez-vous ?"
              : "Pourquoi ecartez-vous cette proposition ?"}
          </label>
          <input
            id="motif"
            type="text"
            value={motif}
            onChange={(evenement) => setMotif(evenement.target.value)}
            onKeyDown={(evenement) => {
              if (evenement.key === "Enter") {
                engager(demandee);
              }
            }}
            autoFocus
            className="w-full rounded-[var(--radius-carte)] border border-bordure bg-creme px-4 py-3 text-sm outline-none focus:border-encre"
          />
        </div>
      ) : null}

      {anomalie ? (
        <p className="mb-4 rounded-[var(--radius-carte)] bg-accent-sourd p-4 text-sm text-accent">
          La decision n'a pas pu etre consignee.
        </p>
      ) : null}

      <div className="grid grid-cols-3 gap-2 sm:flex sm:flex-wrap sm:gap-3">
        <button
          type="button"
          onClick={() => engager("validee")}
          disabled={enCours}
          className="inline-flex items-center justify-center gap-2 rounded-[var(--radius-pastille)] bg-accent px-3 py-3 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40 sm:px-6"
        >
          <Check size={16} />
          Valider
        </button>
        <button
          type="button"
          onClick={() => engager("corrigee")}
          disabled={enCours}
          className="inline-flex items-center justify-center gap-2 rounded-[var(--radius-pastille)] bg-sourd px-3 py-3 text-sm font-medium text-encre transition-colors hover:bg-bordure disabled:opacity-40 sm:px-5"
        >
          <PenLine size={16} />
          {demandee === "corrigee" ? (
            <>
              <span className="sm:hidden">Consigner</span>
              <span className="hidden sm:inline">Consigner la correction</span>
            </>
          ) : (
            "Corriger"
          )}
        </button>
        <button
          type="button"
          onClick={() => engager("refusee")}
          disabled={enCours}
          className="inline-flex items-center justify-center gap-2 rounded-[var(--radius-pastille)] bg-sourd px-3 py-3 text-sm font-medium text-encre transition-colors hover:bg-bordure disabled:opacity-40 sm:px-5"
        >
          <X size={16} />
          {demandee === "refusee" ? (
            <>
              <span className="sm:hidden">Consigner</span>
              <span className="hidden sm:inline">Consigner le refus</span>
            </>
          ) : (
            "Refuser"
          )}
        </button>
        <button
          type="button"
          onClick={surReprise}
          className="col-span-3 py-1 text-sm text-service hover:text-encre sm:py-0"
        >
          Abandonner
        </button>
      </div>
    </Panneau>
  );
}

function _resumerLaProposition(reponse: ReponseRestituee): string {
  if (reponse.consequences) {
    const propositions = reponse.consequences.sejours_a_reloger
      .filter((relogement) => relogement.chambre_proposee)
      .map(
        (relogement) =>
          `${relogement.reservation} en ${relogement.chambre_proposee}`,
      );
    const sans = reponse.consequences.sejours_sans_solution;
    return [
      `Chambre ${reponse.consequences.chambre} indisponible`,
      ...propositions,
      sans > 0 ? `${sans} sans solution` : "",
    ]
      .filter(Boolean)
      .join(" · ");
  }

  if (reponse.arbitrage) {
    return reponse.arbitrage.chambre_proposee
      ? `${reponse.arbitrage.sejour_a_reloger} en ${reponse.arbitrage.chambre_proposee}`
      : `${reponse.arbitrage.sejour_a_reloger} sans solution`;
  }

  return "aucune proposition";
}

function _rassemblerLaJustification(reponse: ReponseRestituee): string {
  if (reponse.consequences) {
    return reponse.consequences.justification.join(" ");
  }
  if (reponse.arbitrage) {
    return [reponse.arbitrage.motif, ...reponse.arbitrage.constats].join(" ");
  }
  return "";
}
