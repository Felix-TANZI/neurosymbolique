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
import {
  Check,
  ChevronDown,
  CircleAlert,
  Info,
  PenLine,
  RotateCcw,
  TriangleAlert,
  X,
} from "lucide-react";
import type {
  ArbitrageRestitue,
  ConsequencesRestituees,
  EtatRestitue,
  LectureRestituee,
  RelogementPropose,
  ReponseRestituee,
} from "@/api/contrat";
import { Carte, EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";
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
  reponse: ReponseRestituee;
  surReprise: () => void;
}

export function Restitution({ reponse, surReprise }: Proprietes) {
  const [decidee, setDecidee] = useState(false);

  if (reponse.nature === "consultation" && reponse.etat) {
    return <Consultation etat={reponse.etat} surReprise={surReprise} />;
  }

  if (reponse.nature === "hors_perimetre") {
    return (
      <HorsPerimetre message={reponse.message} surReprise={surReprise} />
    );
  }

  if (reponse.nature === "confirmation_requise") {
    return (
      <ConfirmationRequise
        lecture={reponse.lecture}
        message={reponse.message}
        surReprise={surReprise}
      />
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {reponse.arbitrage ? <Arbitrage arbitrage={reponse.arbitrage} /> : null}
      {reponse.consequences ? (
        <Consequences consequences={reponse.consequences} />
      ) : null}

      {decidee ? (
        <Panneau ton="sourd">
          <p className="mb-4 text-sm leading-relaxed text-service">
            La decision, la situation et la trace du raisonnement sont
            consignees.
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
          surDecision={() => setDecidee(true)}
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
        <p className="font-display text-2xl leading-snug">{etat.enonce}</p>
      </div>

      {etat.elements.length > 0 ? (
        <ul className="mb-4 grid gap-2 md:grid-cols-2">
          {etat.elements.map((element) => (
            <li
              key={element}
              className="rounded-[var(--radius-carte)] bg-sourd px-4 py-2.5 text-sm"
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
        <p className="font-display text-3xl leading-tight text-creme">
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
          <div className="flex flex-col gap-3">
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
            const [code, compte] = motif.split(": ");
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
            detaille ? "rotate-180 transition-transform" : "transition-transform"
          }
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

function ConfirmationRequise({
  lecture,
  message,
  surReprise,
}: {
  lecture: LectureRestituee;
  message: string;
  surReprise: () => void;
}) {
  return (
    <Panneau>
      <div className="mb-4 flex items-start gap-3">
        <CircleAlert size={18} className="mt-1 shrink-0 text-attente" />
        <div>
          <p className="font-display text-2xl leading-snug">
            Cette lecture demande verification
          </p>
          <p className="mt-1 text-sm text-service">{message}</p>
        </div>
      </div>

      <div className="mb-4 rounded-[var(--radius-carte)] bg-accent-sourd p-4">
        <ul className="flex flex-col gap-2">
          {lecture.reserves.map((reserve) => (
            <li
              key={`${reserve.motif}-${reserve.detail}`}
              className="text-sm leading-relaxed text-encre"
            >
              {reserve.motif === "entite_inexistante"
                ? `${reserve.detail} n'existe pas dans l'etablissement.`
                : reserve.motif === "confiance_insuffisante"
                  ? "Je ne suis pas assure d'avoir compris la situation."
                  : reserve.motif === "entite_manquante"
                    ? `Il manque un element indispensable: ${reserve.detail}.`
                    : reserve.motif}
            </li>
          ))}
        </ul>
      </div>

      <button
        type="button"
        onClick={surReprise}
        className="inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-accent px-5 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
      >
        <RotateCcw size={16} />
        Reformuler
      </button>
    </Panneau>
  );
}

function HorsPerimetre({
  message,
  surReprise,
}: {
  message: string;
  surReprise: () => void;
}) {
  return (
    <Panneau ton="sourd">
      <p className="mb-3 text-sm leading-relaxed text-encre">{message}</p>
      <button
        type="button"
        onClick={surReprise}
        className="inline-flex items-center gap-2 text-sm font-medium text-accent hover:underline"
      >
        <RotateCcw size={14} />
        Reformuler
      </button>
    </Panneau>
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
      <EnTeteDeSection eyebrow="Decision" titre="Que faites-vous ?" />
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
