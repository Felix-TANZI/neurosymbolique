/**
 * Ecran de soumission d'une situation operationnelle.
 *
 * L'ecran etablit la situation puis la soumet au noyau. Il ne produit aucune
 * decision: il transmet et oriente vers la restitution.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, RefreshCw } from "lucide-react";
import { planifierNettoyage, recommanderChambre } from "@/api/client";
import { ErreurDeNoyau } from "@/api/client";
import { EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { ListeDePastilles, Pastille } from "@/composants/Pastille";
import { useSession } from "@/etat/situation";
import type {
  DemandeAffectation,
  DemandePlanification,
  Planification,
  Recommandation,
} from "@/api/contrat";
import {
  AFFECTATION_APRES_INCIDENT,
  AFFECTATION_SANS_ISSUE,
  SERVICE_ETAGE,
  SERVICE_SATURE,
} from "./scenarios";
import { SelecteurDeScenario, type Scenario } from "./SelecteurDeScenario";

const SCENARIOS: Scenario[] = [
  {
    reference: "affectation_incident",
    service: "chambres",
    titre: "Degat des eaux en chambre 312",
    resume:
      "Une chambre devient indisponible en cours de sejour. Le systeme cherche une chambre de remplacement parmi le parc.",
    attendu: "Deux chambres admissibles sur cinq examinees.",
  },
  {
    reference: "affectation_impasse",
    service: "chambres",
    titre: "Parc entierement immobilise",
    resume:
      "Toutes les chambres sont bloquees par une intervention technique. Aucune affectation n'est possible.",
    attendu: "Aucune solution, cinq motifs de rejet restitues.",
  },
  {
    reference: "service_etage",
    service: "housekeeping",
    titre: "Service d'etage avec agent absent",
    resume:
      "Quatre chambres a traiter, un agent absent, une chambre en secteur reserve exigeant une qualification.",
    attendu: "Trois taches planifiees, une sans agent admissible.",
  },
  {
    reference: "service_sature",
    service: "housekeeping",
    titre: "Charge superieure a la capacite",
    resume:
      "Neuf remises en etat pour un seul agent. La charge excede le temps de service disponible.",
    attendu: "Planification partielle, taches restantes signalees.",
  },
];

export function Analyse() {
  const [choisi, setChoisi] = useState<string>(SCENARIOS[0]!.reference);
  const { definir } = useSession();
  const naviguer = useNavigate();

  const scenario = SCENARIOS.find((candidat) => candidat.reference === choisi)!;

  type IssueChambres = {
    service: "chambres";
    demande: DemandeAffectation;
    resultat: Recommandation;
  };

  type IssueHousekeeping = {
    service: "housekeeping";
    demande: DemandePlanification;
    resultat: Planification;
  };

  type Issue = IssueChambres | IssueHousekeeping;

  const soumission = useMutation<Issue, unknown, string>({
    mutationFn: async (reference) => {
      switch (reference) {
        case "affectation_incident":
          return {
            service: "chambres",
            demande: AFFECTATION_APRES_INCIDENT,
            resultat: await recommanderChambre(AFFECTATION_APRES_INCIDENT),
          };
        case "affectation_impasse":
          return {
            service: "chambres",
            demande: AFFECTATION_SANS_ISSUE,
            resultat: await recommanderChambre(AFFECTATION_SANS_ISSUE),
          };
        case "service_etage":
          return {
            service: "housekeeping",
            demande: SERVICE_ETAGE,
            resultat: await planifierNettoyage(SERVICE_ETAGE),
          };
        default:
          return {
            service: "housekeeping",
            demande: SERVICE_SATURE,
            resultat: await planifierNettoyage(SERVICE_SATURE),
          };
      }
    },
    onSuccess: (issue) => {
      if (issue.service === "chambres") {
        definir({
          service: "chambres",
          demandeChambres: issue.demande,
          recommandation: issue.resultat,
          demandeHousekeeping: null,
          planification: null,
          etabliLe: new Date(),
        });
      } else {
        definir({
          service: "housekeeping",
          demandeHousekeeping: issue.demande,
          planification: issue.resultat,
          demandeChambres: null,
          recommandation: null,
          etabliLe: new Date(),
        });
      }
      naviguer("/recommandations");
    },
  });

  return (
    <div className="flex flex-col gap-5">
      <Panneau>
        <EnTeteDeSection
          eyebrow="Etape 1"
          titre="Decrire la situation"
          action={
            <Pastille nature="neutre">
              {SCENARIOS.length} situations de reference
            </Pastille>
          }
        />
        <p className="max-w-2xl text-sm leading-relaxed text-service">
          Chaque situation reproduit un cas d'exploitation reel. Le noyau
          etablit les options admissibles au regard des contraintes, ordonne
          celles qui restent, et conserve le motif de rejet de chaque option
          ecartee.
        </p>
      </Panneau>

      <SelecteurDeScenario
        scenarios={SCENARIOS}
        choisi={choisi}
        surChoix={setChoisi}
      />

      <Panneau ton="encre" className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-creme/60">
              Situation retenue
            </p>
            <h2 className="font-display text-2xl text-creme">
              {scenario.titre}
            </h2>
          </div>
          <button
            type="button"
            onClick={() => soumission.mutate(choisi)}
            disabled={soumission.isPending}
            className="inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-accent px-6 py-3 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-60"
          >
            {soumission.isPending ? (
              <>
                <RefreshCw size={16} className="animate-spin" />
                Raisonnement en cours
              </>
            ) : (
              <>
                Soumettre au raisonnement
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </div>

        <ListeDePastilles>
          <Pastille nature="accent">
            {scenario.service === "chambres"
              ? "Gestion des chambres"
              : "Housekeeping"}
          </Pastille>
          <Pastille nature="neutre">{scenario.attendu}</Pastille>
        </ListeDePastilles>

        {soumission.isError ? (
          <AnomalieDeSoumission erreur={soumission.error} />
        ) : null}
      </Panneau>
    </div>
  );
}

function AnomalieDeSoumission({ erreur }: { erreur: unknown }) {
  const estConnue = erreur instanceof ErreurDeNoyau;
  const message = estConnue
    ? erreur.message
    : "Le noyau de raisonnement n'a pas repondu.";
  const conduite =
    estConnue && erreur.estIndisponibilite
      ? "Verifiez que le noyau est demarre, puis soumettez a nouveau."
      : "Verifiez la situation soumise, puis soumettez a nouveau.";

  return (
    <div className="rounded-[var(--radius-carte)] bg-white/10 p-4">
      <p className="text-sm font-medium text-creme">{message}</p>
      <p className="mt-1 text-sm text-creme/70">{conduite}</p>
    </div>
  );
}