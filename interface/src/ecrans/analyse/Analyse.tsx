/**
 * Ecran de designation de la situation a traiter.
 *
 * L'ecran presente l'etat courant de l'etablissement et les situations qui
 * appellent une decision. Le responsable designe celle qui le concerne; la
 * situation complete est composee par le noyau depuis l'etat persiste.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import {
  ErreurDeNoyau,
  consulterArriveesATraiter,
  consulterEtablissement,
  planifierLeService,
  recommanderPourReservation,
} from "@/api/client";
import { EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";
import { jourParDefaut } from "@/etat/jour";
import { useSession, type Service } from "@/etat/situation";
import { ArriveesATraiter } from "./ArriveesATraiter";
import { EtatDuJour } from "./EtatDuJour";
import { ServicesDEtage } from "./ServicesDEtage";

const SERVICES: { valeur: Service; libelle: string }[] = [
  { valeur: "chambres", libelle: "Gestion des chambres" },
  { valeur: "housekeeping", libelle: "Housekeeping" },
];

export function Analyse() {
  const [service, setService] = useState<Service>("chambres");
  const jour = jourParDefaut();
  const { definir } = useSession();
  const naviguer = useNavigate();

  const etat = useQuery({
    queryKey: ["etablissement", jour],
    queryFn: () => consulterEtablissement(jour),
  });

  const arrivees = useQuery({
    queryKey: ["arrivees", jour],
    queryFn: () => consulterArriveesATraiter(jour),
    enabled: service === "chambres",
  });

  const affectation = useMutation({
    mutationFn: (reference: string) => recommanderPourReservation(reference),
    onSuccess: (recommandation, reference) => {
      definir({
        service: "chambres",
        reference,
        secteur: null,
        recommandation,
        planification: null,
        etabliLe: new Date(),
      });
      naviguer("/recommandations");
    },
  });

  const planification = useMutation({
    mutationFn: (secteur: string) =>
      planifierLeService(secteur, { temps_maximal: 15 }),
    onSuccess: (resultat, secteur) => {
      definir({
        service: "housekeeping",
        reference: null,
        secteur,
        planification: resultat,
        recommandation: null,
        etabliLe: new Date(),
      });
      naviguer("/recommandations");
    },
  });

  const enCours = affectation.isPending || planification.isPending;
  const anomalie = affectation.error ?? planification.error;

  return (
    <div className="flex flex-col gap-5">
      <EtatDuJour etat={etat.data} enChargement={etat.isPending} jour={jour} />

      <Panneau>
        <EnTeteDeSection
          eyebrow="Etape 1"
          titre="Designer la situation a traiter"
          action={
            enCours ? (
              <Pastille nature="accent">
                <RefreshCw size={13} className="mr-1.5 animate-spin" />
                Raisonnement en cours
              </Pastille>
            ) : null
          }
        />

        <div
          role="radiogroup"
          aria-label="Service concerne"
          className="mb-5 flex flex-wrap gap-2"
        >
          {SERVICES.map(({ valeur, libelle }) => {
            const retenu = service === valeur;
            return (
              <button
                key={valeur}
                type="button"
                role="radio"
                aria-checked={retenu}
                onClick={() => setService(valeur)}
                className={[
                  "rounded-[var(--radius-pastille)] px-5 py-2.5 text-sm font-medium transition-colors",
                  retenu
                    ? "bg-accent text-white"
                    : "bg-sourd text-encre hover:bg-bordure",
                ].join(" ")}
              >
                {libelle}
              </button>
            );
          })}
        </div>

        <p className="max-w-2xl text-sm leading-relaxed text-service">
          {service === "chambres"
            ? "Les sejours ci-dessous arrivent aujourd'hui sans chambre affectee. Le noyau etablit le parc, les occupations concurrentes et les exigences depuis l'etat de l'etablissement."
            : "Choisissez un secteur pour organiser son service. Le noyau etablit les taches en attente, les agents en service et leurs qualifications."}
        </p>

        {anomalie ? <AnomalieDeSoumission erreur={anomalie} /> : null}
      </Panneau>

      {service === "chambres" ? (
        <ArriveesATraiter
          arrivees={arrivees.data ?? []}
          enChargement={arrivees.isPending}
          enCours={affectation.isPending}
          referenceEnCours={affectation.variables ?? null}
          surChoix={(reference) => affectation.mutate(reference)}
        />
      ) : (
        <ServicesDEtage
          enCours={planification.isPending}
          secteurEnCours={planification.variables ?? null}
          surChoix={(secteur) => planification.mutate(secteur)}
        />
      )}
    </div>
  );
}

function AnomalieDeSoumission({ erreur }: { erreur: unknown }) {
  const connue = erreur instanceof ErreurDeNoyau;
  const message = connue
    ? erreur.message
    : "Le noyau de raisonnement n'a pas repondu.";
  const conduite = !connue
    ? "Verifiez que le noyau est demarre, puis recommencez."
    : erreur.statut === 404
      ? "Constituez l'etablissement avec le script de constitution, puis recommencez."
      : "Verifiez l'etat de l'etablissement, puis recommencez.";

  return (
    <div className="mt-4 rounded-[var(--radius-carte)] bg-accent-sourd p-4">
      <p className="text-sm font-medium text-accent">{message}</p>
      <p className="mt-1 text-sm text-service">{conduite}</p>
    </div>
  );
}
