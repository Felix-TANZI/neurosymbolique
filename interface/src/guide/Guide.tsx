/**
 * Guide de prise en main.
 *
 * Le guide tient en cinq temps courts: ce que fait l'application, ou trouver
 * chaque chose, ce que l'on peut lui demander, ce qu'elle ne fait pas, et
 * comment lire ce qu'elle repond. Il montre plutot qu'il n'explique: chaque
 * exemple de demande peut etre essaye, ce qui fait comprendre l'application
 * en la faisant fonctionner.
 *
 * Ce qu'il annonce doit rester exact. Une situation reconnue mais pas encore
 * prise en charge figure parmi les limites, non parmi les possibilites: un
 * guide qui promettrait davantage que le systeme ne tient serait pire que
 * l'absence de guide.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { ComponentType, ReactNode, TouchEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Ban,
  Building2,
  Check,
  CircleAlert,
  CircleCheck,
  CircleHelp,
  FileText,
  FlaskConical,
  Hash,
  LayoutGrid,
  MessageSquareText,
  PenLine,
  Play,
  Scale,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  X,
} from "lucide-react";
import { Logo } from "@/composants/Logo";
import { enJourLisible, jourParDefaut } from "@/etat/jour";

type Icone = ComponentType<{ size?: number; className?: string }>;

interface Proprietes {
  surFermeture: () => void;
}

const TITRES = [
  "Bienvenue",
  "Les écrans",
  "Ce que vous pouvez demander",
  "Ce que Neuro ne fait pas",
  "Lire une réponse",
] as const;

export function Guide({ surFermeture }: Proprietes) {
  const [etape, setEtape] = useState(0);
  const naviguer = useNavigate();
  const boite = useRef<HTMLDivElement>(null);
  const toucher = useRef<number | null>(null);
  const derniere = TITRES.length - 1;

  const avancer = useCallback(
    () => setEtape((courante) => Math.min(courante + 1, derniere)),
    [derniere],
  );
  const reculer = useCallback(
    () => setEtape((courante) => Math.max(courante - 1, 0)),
    [],
  );

  const essayer = (enonce: string) => {
    surFermeture();
    naviguer("/traiter", { state: { enonce } });
  };

  useEffect(() => {
    const precedent = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    boite.current?.focus();
    return () => {
      document.body.style.overflow = precedent;
    };
  }, []);

  useEffect(() => {
    const surTouche = (evenement: KeyboardEvent) => {
      if (evenement.key === "Escape") surFermeture();
      if (evenement.key === "ArrowRight") avancer();
      if (evenement.key === "ArrowLeft") reculer();
    };
    window.addEventListener("keydown", surTouche);
    return () => window.removeEventListener("keydown", surTouche);
  }, [surFermeture, avancer, reculer]);

  useEffect(() => {
    boite.current?.querySelector("[data-defilement]")?.scrollTo({ top: 0 });
  }, [etape]);

  const debutDuGeste = (evenement: TouchEvent) => {
    toucher.current = evenement.touches[0]?.clientX ?? null;
  };
  const finDuGeste = (evenement: TouchEvent) => {
    const depart = toucher.current;
    const arrivee = evenement.changedTouches[0]?.clientX;
    toucher.current = null;
    if (depart === null || arrivee === undefined) return;
    if (arrivee - depart < -60) avancer();
    if (arrivee - depart > 60) reculer();
  };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-center bg-encre/55 backdrop-blur-[2px] sm:items-center sm:p-6"
      onClick={surFermeture}
    >
      <div
        ref={boite}
        role="dialog"
        aria-modal="true"
        aria-labelledby="titre-du-guide"
        tabIndex={-1}
        onClick={(evenement) => evenement.stopPropagation()}
        onTouchStart={debutDuGeste}
        onTouchEnd={finDuGeste}
        className="flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-[var(--radius-panneau)] bg-panneau shadow-2xl outline-none sm:max-h-[86vh] sm:max-w-3xl sm:rounded-[var(--radius-panneau)]"
      >
        <header className="flex items-center justify-between gap-3 border-b border-bordure px-4 py-3 sm:px-6">
          <div className="flex min-w-0 items-center gap-2.5">
            <Logo taille={26} />
            <p className="truncate text-xs font-medium uppercase tracking-[0.14em] text-service">
              Guide · {etape + 1}/{TITRES.length}
            </p>
          </div>
          <button
            type="button"
            onClick={surFermeture}
            aria-label="Fermer le guide"
            className="rounded-full p-2 text-service transition-colors hover:bg-sourd hover:text-encre"
          >
            <X size={18} />
          </button>
        </header>

        <div
          data-defilement
          className="flex-1 overflow-y-auto px-4 py-5 sm:px-6 sm:py-6"
        >
          <h2
            id="titre-du-guide"
            className="mb-4 font-display text-xl leading-tight sm:text-2xl"
          >
            {TITRES[etape]}
          </h2>

          {etape === 0 ? <Principe /> : null}
          {etape === 1 ? <Ecrans /> : null}
          {etape === 2 ? <Demandes surEssai={essayer} /> : null}
          {etape === 3 ? <Limites /> : null}
          {etape === 4 ? <Lecture /> : null}
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-bordure px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 sm:px-6 sm:pb-4">
          {etape === 0 ? (
            <button
              type="button"
              onClick={surFermeture}
              className="px-2 py-2 text-sm text-service hover:text-encre"
            >
              Passer
            </button>
          ) : (
            <button
              type="button"
              onClick={reculer}
              className="inline-flex items-center gap-1.5 rounded-[var(--radius-pastille)] px-3 py-2 text-sm text-encre transition-colors hover:bg-sourd"
            >
              <ArrowLeft size={15} />
              <span className="hidden min-[400px]:inline">Précédent</span>
            </button>
          )}

          <ol className="flex items-center gap-1.5" aria-label="Progression">
            {TITRES.map((titre, rang) => (
              <li key={titre}>
                <button
                  type="button"
                  onClick={() => setEtape(rang)}
                  aria-label={`Aller à : ${titre}`}
                  aria-current={rang === etape ? "step" : undefined}
                  className={[
                    "block h-2 rounded-full transition-all",
                    rang === etape
                      ? "w-6 bg-accent"
                      : "w-2 bg-bordure hover:bg-service",
                  ].join(" ")}
                />
              </li>
            ))}
          </ol>

          {etape < derniere ? (
            <button
              type="button"
              onClick={avancer}
              className="inline-flex items-center gap-1.5 rounded-[var(--radius-pastille)] bg-encre px-4 py-2 text-sm font-medium text-creme transition-opacity hover:opacity-90"
            >
              Suivant
              <ArrowRight size={15} />
            </button>
          ) : (
            <button
              type="button"
              onClick={surFermeture}
              className="inline-flex items-center gap-1.5 rounded-[var(--radius-pastille)] bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
            >
              <Check size={15} />
              Commencer
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}

/* Etape 1: le principe */

const TEMPS: { Icone: Icone; titre: string; detail: string }[] = [
  {
    Icone: MessageSquareText,
    titre: "Vous décrivez",
    detail: "la situation, en français, comme à un collègue",
  },
  {
    Icone: Scale,
    titre: "Neuro raisonne",
    detail: "vérifie les références et applique les règles de l'hôtel",
  },
  {
    Icone: CircleCheck,
    titre: "Vous décidez",
    detail: "valider, corriger ou refuser sa proposition",
  },
];

function Principe() {
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm leading-relaxed text-service sm:text-base">
        Un assistant pour les décisions du quotidien à l'hôtel : reloger des
        clients, organiser le ménage, ordonner les réparations.
      </p>

      <ol className="grid grid-cols-3 gap-2 sm:gap-3">
        {TEMPS.map(({ Icone, titre, detail }, rang) => (
          <li
            key={titre}
            className="relative flex flex-col items-center rounded-[var(--radius-carte)] bg-sourd px-2 py-3 text-center sm:px-4 sm:py-4"
          >
            <span className="mb-2 flex size-9 items-center justify-center rounded-full bg-panneau text-encre sm:size-10">
              <Icone size={18} />
            </span>
            <p className="font-display text-sm leading-tight sm:text-base">
              {rang + 1}. {titre}
            </p>
            <p className="mt-1 text-xs leading-snug text-service">{detail}</p>
          </li>
        ))}
      </ol>

      <Encadre Icone={ShieldCheck} ton="accent">
        <strong className="font-medium text-encre">
          Rien n'est appliqué sans votre accord.
        </strong>{" "}
        Neuro ne bloque aucune chambre et ne déplace aucun client : il
        propose, vous tranchez.
      </Encadre>

      <p className="text-xs text-service">
        Démonstration : établissement simulé, journée du{" "}
        {enJourLisible(jourParDefaut())}.
      </p>
    </div>
  );
}

/* Etape 2: les ecrans */

const ECRANS: { Icone: Icone; nom: string; role: string }[] = [
  {
    Icone: LayoutGrid,
    nom: "Aujourd'hui",
    role: "Ce qui attend votre décision : clients sans chambre, chambres immobilisées.",
  },
  {
    Icone: Sparkles,
    nom: "Traiter",
    role: "Décrivez une situation, recevez une proposition justifiée.",
  },
  {
    Icone: Building2,
    nom: "Établissement",
    role: "Consultez les chambres, le personnel et les réparations.",
  },
  {
    Icone: FileText,
    nom: "Historique",
    role: "Retrouvez vos décisions et celles qui s'écartent de la proposition.",
  },
  {
    Icone: FlaskConical,
    nom: "Simulation",
    role: "Modifiez l'état de l'hôtel pour observer l'effet sur les réponses.",
  },
];

function Ecrans() {
  return (
    <div className="flex flex-col gap-4">
      <ul className="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-3">
        {ECRANS.map(({ Icone, nom, role }, rang) => (
          <li
            key={nom}
            className={[
              "rounded-[var(--radius-carte)] border border-bordure p-3 sm:p-4",
              rang === ECRANS.length - 1 ? "col-span-2 lg:col-span-1" : "",
            ].join(" ")}
          >
            <div className="mb-1.5 flex items-center gap-2">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-encre text-creme">
                <Icone size={14} />
              </span>
              <p className="font-display text-base leading-none">{nom}</p>
            </div>
            <p className="text-xs leading-snug text-service sm:text-sm">
              {role}
            </p>
          </li>
        ))}
      </ul>

      <p className="text-xs leading-relaxed text-service">
        La barre de navigation reste en bas de l'écran. La pastille en haut à
        droite indique si le moteur de raisonnement répond.
      </p>
    </div>
  );
}

/* Etape 3: les demandes */

const DEMANDES: { sujet: string; effet: string; exemple: string }[] = [
  {
    sujet: "Un incident",
    effet: "Neuro immobilise la chambre et propose un relogement à chaque client.",
    exemple: "il y a une fuite dans la 319",
  },
  {
    sujet: "Avec une préférence",
    effet: "La proximité ou l'étage souhaité ordonnent les chambres proposées.",
    exemple: "la 319 a un souci, il me faut une chambre a cote de la 406",
  },
  {
    sujet: "Un conflit",
    effet: "Neuro établit qui garder, qui reloger, ou constate qu'il n'y a pas de conflit.",
    exemple: "deux clients ont reserve la 309",
  },
  {
    sujet: "Une question",
    effet: "Chambres libres, arrivées, agents, tâches, une chambre ou un séjour précis.",
    exemple: "quelles chambres sont disponibles",
  },
  {
    sujet: "Le ménage",
    effet: "Répartition d'une charge entre des agents, avec la durée du service.",
    exemple: "j'ai 12 chambres a faire et 3 agents, comment repartir",
  },
  {
    sujet: "La maintenance",
    effet: "Ordre des réparations et technicien retenu pour chacune.",
    exemple: "par quoi commencer aujourd'hui",
  },
];

function Demandes({ surEssai }: { surEssai: (enonce: string) => void }) {
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm leading-relaxed text-service">
        Écrivez librement dans l'écran Traiter. Touchez un exemple pour
        l'essayer.
      </p>

      <ul className="grid gap-2 min-[480px]:grid-cols-2 sm:gap-3">
        {DEMANDES.map(({ sujet, effet, exemple }) => (
          <li
            key={sujet}
            className="flex flex-col rounded-[var(--radius-carte)] bg-sourd p-3"
          >
            <p className="font-display text-base leading-tight">{sujet}</p>
            <p className="mb-2.5 mt-0.5 text-xs leading-snug text-service">
              {effet}
            </p>
            <button
              type="button"
              onClick={() => surEssai(exemple)}
              className="group mt-auto flex items-center justify-between gap-2 rounded-[var(--radius-carte)] bg-panneau px-3 py-2 text-left text-sm leading-snug text-encre transition-colors hover:bg-accent-sourd"
            >
              <span className="min-w-0">« {exemple} »</span>
              <Play
                size={14}
                className="shrink-0 text-accent transition-transform group-hover:translate-x-0.5"
              />
            </button>
          </li>
        ))}
      </ul>

      <Encadre Icone={Hash} ton="sourd">
        Citez les références telles qu'elles existent : un numéro de chambre
        (319), un séjour (R-00017), un secteur (etage 3).
      </Encadre>
    </div>
  );
}

/* Etape 4: les limites */

const LIMITES: { Icone: Icone; titre: string; detail: string }[] = [
  {
    Icone: Ban,
    titre: "Il n'applique rien",
    detail:
      "Votre décision est consignée au journal ; l'état de l'hôtel reste inchangé.",
  },
  {
    Icone: CircleHelp,
    titre: "Il ne devine pas",
    detail:
      "S'il n'est pas sûr d'avoir compris, ou si une référence n'existe pas, il vous demande de préciser.",
  },
  {
    Icone: Hash,
    titre: "Il veut des nombres qualifiés",
    detail: "« 12 chambres et 3 agents » est compris ; « 12 et 3 » ne l'est pas.",
  },
  {
    Icone: TriangleAlert,
    titre: "Il ne traite pas encore tout",
    detail:
      "Attribuer une chambre à un client précis ou signaler une panne d'ascenseur sont reconnus, pas encore pris en charge : il vous le signale.",
  },
  {
    Icone: X,
    titre: "Il reste dans son domaine",
    detail:
      "Chambres, ménage et maintenance. La météo ou une question générale restent sans réponse.",
  },
];

function Limites() {
  return (
    <ul className="grid gap-2 sm:grid-cols-2 sm:gap-3">
      {LIMITES.map(({ Icone, titre, detail }, rang) => (
        <li
          key={titre}
          className={[
            "flex items-start gap-3 rounded-[var(--radius-carte)] border border-bordure p-3",
            rang === LIMITES.length - 1 ? "sm:col-span-2" : "",
          ].join(" ")}
        >
          <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-accent-sourd text-accent">
            <Icone size={14} />
          </span>
          <div className="min-w-0">
            <p className="font-display text-base leading-tight">{titre}</p>
            <p className="mt-0.5 text-xs leading-snug text-service sm:text-sm">
              {detail}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

/* Etape 5: la lecture d'une reponse */

const PRUDENCES: { Icone: Icone; classe: string; nom: string; sens: string }[] = [
  {
    Icone: CircleCheck,
    classe: "text-succes",
    nom: "Mesuré",
    sens: "Lecture sûre, situation ordinaire.",
  },
  {
    Icone: CircleAlert,
    classe: "text-encre",
    nom: "Modéré",
    sens: "Lecture sûre, mais l'exploitation est engagée.",
  },
  {
    Icone: TriangleAlert,
    classe: "text-attente",
    nom: "Élevé",
    sens: "Lecture incertaine : vérifiez avant d'agir.",
  },
  {
    Icone: CircleHelp,
    classe: "text-accent",
    nom: "Indéterminé",
    sens: "Neuro s'abstient et dit ce qui lui manque.",
  },
];

const DECISIONS: { Icone: Icone; nom: string; sens: string }[] = [
  { Icone: Check, nom: "Valider", sens: "Vous retenez la proposition." },
  {
    Icone: PenLine,
    nom: "Corriger",
    sens: "Vous indiquez ce que vous retenez à la place.",
  },
  { Icone: X, nom: "Refuser", sens: "Vous dites pourquoi vous l'écartez." },
];

function Lecture() {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Bloc titre="Le niveau de prudence">
          <ul className="flex flex-col gap-2">
            {PRUDENCES.map(({ Icone, classe, nom, sens }) => (
              <li key={nom} className="flex items-start gap-2.5">
                <Icone size={16} className={`mt-0.5 shrink-0 ${classe}`} />
                <p className="text-xs leading-snug sm:text-sm">
                  <span className={`font-medium ${classe}`}>{nom}</span>
                  <span className="text-service"> — {sens}</span>
                </p>
              </li>
            ))}
          </ul>
        </Bloc>

        <Bloc titre="Votre décision">
          <ul className="flex flex-col gap-2">
            {DECISIONS.map(({ Icone, nom, sens }) => (
              <li key={nom} className="flex items-start gap-2.5">
                <Icone size={16} className="mt-0.5 shrink-0 text-encre" />
                <p className="text-xs leading-snug sm:text-sm">
                  <span className="font-medium">{nom}</span>
                  <span className="text-service"> — {sens}</span>
                </p>
              </li>
            ))}
          </ul>
          <p className="mt-3 border-t border-bordure pt-2 text-xs leading-snug text-service">
            Chaque décision rejoint l'Historique, avec la situation et le
            raisonnement qui l'a produite.
          </p>
        </Bloc>
      </div>

      <Encadre Icone={CircleHelp} ton="sourd">
        Ce guide reste accessible à tout moment par le bouton{" "}
        <span className="inline-flex size-5 items-center justify-center rounded-full bg-encre align-middle text-[0.65rem] font-semibold text-creme">
          ?
        </span>{" "}
        en haut de l'écran.
      </Encadre>
    </div>
  );
}

/* Elements communs */

function Bloc({ titre, children }: { titre: string; children: ReactNode }) {
  return (
    <section className="rounded-[var(--radius-carte)] bg-sourd p-3 sm:p-4">
      <p className="mb-2.5 text-xs font-medium uppercase tracking-[0.14em] text-service">
        {titre}
      </p>
      {children}
    </section>
  );
}

function Encadre({
  Icone,
  ton,
  children,
}: {
  Icone: Icone;
  ton: "accent" | "sourd";
  children: ReactNode;
}) {
  return (
    <div
      className={[
        "flex items-start gap-2.5 rounded-[var(--radius-carte)] px-3 py-2.5 text-xs leading-relaxed sm:text-sm",
        ton === "accent" ? "bg-accent-sourd text-service" : "bg-sourd text-service",
      ].join(" ")}
    >
      <Icone
        size={16}
        className={`mt-0.5 shrink-0 ${ton === "accent" ? "text-accent" : "text-encre"}`}
      />
      <p className="min-w-0">{children}</p>
    </div>
  );
}
