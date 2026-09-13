/**
 * Simulateur du systeme de gestion de l'etablissement.
 *
 * Cet ecran ne fait pas partie du systeme d'aide a la decision. Il tient le
 * role que le logiciel de gestion hoteliere occuperait dans une installation
 * reelle, afin qu'une modification de l'etat puisse etre observee dans les
 * reponses du systeme.
 *
 * La separation est maintenue visible: qui emploie cet ecran doit savoir qu'il
 * agit sur l'exploitation, non sur le raisonnement.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Trash2, TriangleAlert } from "lucide-react";
import {
  consulterAgents,
  consulterChambres,
  consulterLesTechniciens,
  inscrireUnAgent,
  modifierUnTechnicien,
  modifierUneChambre,
  retirerUnAgent,
} from "@/api/client";
import type { EtatTechnique } from "@/api/contrat";
import { EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";

const ETATS_TECHNIQUES: { valeur: EtatTechnique; libelle: string }[] = [
  { valeur: "operationnelle", libelle: "Opérationnelle" },
  { valeur: "degradee", libelle: "Dégradée" },
  { valeur: "bloquee", libelle: "Bloquée" },
];

export function Simulation() {
  const cache = useQueryClient();
  const rafraichir = () => {
    cache.invalidateQueries();
  };

  return (
    <div className="flex flex-col gap-3 sm:gap-5">
      <Panneau ton="sourd">
        <div className="flex items-start gap-3">
          <TriangleAlert size={18} className="mt-0.5 shrink-0 text-accent" />
          <div>
            <p className="font-display text-base leading-snug sm:text-xl">
              Simulateur du système de gestion
            </p>
            <p className="mt-2 max-w-3xl text-xs leading-relaxed text-service sm:text-sm">
              Cet écran ne fait pas partie du système d'aide à la décision.
              <span className="hidden sm:inline">
                {" "}
                Il tient le rôle du logiciel de gestion hôtelière, afin que
                vous puissiez modifier l'état de l'établissement et observer
                comment les réponses du système en tiennent compte.
              </span>
            </p>
          </div>
        </div>
      </Panneau>

      <EtatDesChambres surModification={rafraichir} />
      <div className="grid items-start gap-3 sm:gap-5 xl:grid-cols-2">
        <EffectifDEtage surModification={rafraichir} />
        <EffectifTechnique surModification={rafraichir} />
      </div>
    </div>
  );
}

function EtatDesChambres({
  surModification,
}: {
  surModification: () => void;
}) {
  const [numero, setNumero] = useState("");

  const chambres = useQuery({
    queryKey: ["chambres"],
    queryFn: () => consulterChambres(),
  });

  const modification = useMutation({
    mutationFn: ({
      chambre,
      etat,
    }: {
      chambre: string;
      etat: EtatTechnique;
    }) => modifierUneChambre(chambre, { etat_technique: etat }),
    onSuccess: surModification,
  });

  const bloquees = (chambres.data ?? []).filter(
    (chambre) => chambre.etat_technique !== "operationnelle",
  );

  return (
    <Panneau>
      <EnTeteDeSection
        eyebrow="Chambres"
        titre="Modifier l'état d'une chambre"
        action={
          bloquees.length > 0 ? (
            <Pastille nature="attente">{bloquees.length} hors service</Pastille>
          ) : null
        }
      />

      <div className="mb-4 grid grid-cols-3 gap-2 sm:flex sm:flex-wrap">
        <input
          type="text"
          value={numero}
          onChange={(evenement) => setNumero(evenement.target.value)}
          placeholder="numero de chambre"
          className="col-span-3 rounded-[var(--radius-carte)] border border-bordure bg-creme px-4 py-2.5 text-sm outline-none focus:border-encre sm:w-48"
        />
        {ETATS_TECHNIQUES.map((etat) => (
          <button
            key={etat.valeur}
            type="button"
            disabled={!numero.trim() || modification.isPending}
            onClick={() =>
              modification.mutate({ chambre: numero.trim(), etat: etat.valeur })
            }
            className="rounded-[var(--radius-pastille)] bg-sourd px-2 py-2.5 text-sm text-encre transition-colors hover:bg-bordure disabled:opacity-40 sm:px-4"
          >
            {etat.libelle}
          </button>
        ))}
      </div>

      {modification.isSuccess ? (
        <p className="rounded-[var(--radius-carte)] bg-accent-sourd px-4 py-2.5 text-sm">
          {modification.data.objet} : {modification.data.modification}
        </p>
      ) : null}

      {modification.isError ? (
        <p className="rounded-[var(--radius-carte)] bg-accent-sourd px-4 py-2.5 text-sm text-accent">
          Cette chambre n'existe pas.
        </p>
      ) : null}

      {bloquees.length > 0 ? (
        <div className="mt-4 border-t border-bordure pt-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-service">
            Actuellement hors service
          </p>
          <div className="grid grid-cols-2 gap-2 min-[480px]:grid-cols-3 sm:flex sm:flex-wrap">
            {bloquees.map((chambre) => (
              <button
                key={chambre.numero}
                type="button"
                onClick={() =>
                  modification.mutate({
                    chambre: chambre.numero,
                    etat: "operationnelle",
                  })
                }
                className="rounded-[var(--radius-pastille)] bg-accent-sourd px-3 py-1.5 text-xs transition-colors hover:bg-bordure sm:text-sm"
              >
                {chambre.numero}
                <span className="hidden sm:inline"> · remettre en service</span>
                <span className="sm:hidden"> · rétablir</span>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </Panneau>
  );
}

function EffectifDEtage({
  surModification,
}: {
  surModification: () => void;
}) {
  const [identifiant, setIdentifiant] = useState("");
  const [secteur, setSecteur] = useState("etage_1");

  const agents = useQuery({
    queryKey: ["agents"],
    queryFn: () => consulterAgents(),
  });

  const inscription = useMutation({
    mutationFn: () =>
      inscrireUnAgent({ identifiant: identifiant.trim(), secteur }),
    onSuccess: () => {
      setIdentifiant("");
      surModification();
    },
  });

  const retrait = useMutation({
    mutationFn: (reference: string) => retirerUnAgent(reference),
    onSuccess: surModification,
  });

  const secteurs = [
    ...new Set((agents.data ?? []).map((agent) => agent.secteur)),
  ].sort();

  return (
    <Panneau>
      <EnTeteDeSection
        eyebrow="Housekeeping"
        titre="Effectif d'étage"
        action={<Pastille nature="neutre">{agents.data?.length ?? 0}</Pastille>}
      />

      <div className="mb-4 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
        <input
          type="text"
          value={identifiant}
          onChange={(evenement) => setIdentifiant(evenement.target.value)}
          placeholder="A-0013"
          className="min-w-0 rounded-[var(--radius-carte)] border border-bordure bg-creme px-3 py-2.5 text-sm outline-none focus:border-encre sm:w-36 sm:px-4"
        />
        <select
          value={secteur}
          onChange={(evenement) => setSecteur(evenement.target.value)}
          className="min-w-0 rounded-[var(--radius-carte)] border border-bordure bg-creme px-3 py-2.5 text-sm outline-none focus:border-encre sm:px-4"
        >
          {secteurs.map((nom) => (
            <option key={nom} value={nom}>
              {nom.replace(/_/g, " ")}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={!identifiant.trim() || inscription.isPending}
          onClick={() => inscription.mutate()}
          className="col-span-2 rounded-[var(--radius-pastille)] bg-encre px-5 py-2.5 text-sm font-medium text-creme transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          Inscrire
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2 min-[480px]:grid-cols-3 lg:grid-cols-4 xl:grid-cols-3">
        {(agents.data ?? []).map((agent) => (
          <div
            key={agent.identifiant}
            className="flex min-w-0 items-center justify-between gap-1 rounded-[var(--radius-carte)] bg-sourd py-2 pl-3 pr-1 sm:gap-2 sm:py-2.5"
          >
            <div className="min-w-0">
              <p className="font-display text-base leading-none">
                {agent.identifiant}
              </p>
              <p className="mt-1 text-xs text-service">
                {agent.secteur.replace(/_/g, " ")}
              </p>
            </div>
            <button
              type="button"
              onClick={() => retrait.mutate(agent.identifiant)}
              disabled={retrait.isPending}
              aria-label={`Retirer ${agent.identifiant}`}
              className="shrink-0 rounded-[var(--radius-pastille)] p-2 text-service transition-colors hover:bg-accent-sourd hover:text-accent"
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>
    </Panneau>
  );
}

function EffectifTechnique({
  surModification,
}: {
  surModification: () => void;
}) {
  const techniciens = useQuery({
    queryKey: ["techniciens"],
    queryFn: consulterLesTechniciens,
  });

  const bascule = useMutation({
    mutationFn: ({
      reference,
      disponible,
    }: {
      reference: string;
      disponible: boolean;
    }) => modifierUnTechnicien(reference, disponible),
    onSuccess: surModification,
  });

  return (
    <Panneau>
      <EnTeteDeSection
        eyebrow="Maintenance"
        titre="Disponibilité des techniciens"
        action={
          <Pastille nature="neutre">
            {(techniciens.data ?? []).filter((t) => t.disponible).length}{" "}
            disponibles
          </Pastille>
        }
      />

      <div className="grid grid-cols-2 gap-2">
        {(techniciens.data ?? []).map((technicien) => (
          <div
            key={technicien.identifiant}
            className={[
              "flex min-w-0 flex-col items-stretch justify-between gap-2 rounded-[var(--radius-carte)] px-3 py-2.5 sm:flex-row sm:items-center sm:gap-3 sm:px-4 sm:py-3",
              technicien.disponible ? "bg-sourd" : "bg-accent-sourd",
            ].join(" ")}
          >
            <div className="min-w-0">
              <p className="font-display text-base leading-none">
                {technicien.identifiant}
              </p>
              <p className="mt-1 text-xs text-service">
                {technicien.competences.join(", ")}
              </p>
            </div>
            <button
              type="button"
              onClick={() =>
                bascule.mutate({
                  reference: technicien.identifiant,
                  disponible: !technicien.disponible,
                })
              }
              disabled={bascule.isPending}
              className="shrink-0 rounded-[var(--radius-pastille)] bg-creme px-3 py-1.5 text-xs transition-opacity hover:opacity-80 disabled:opacity-40 sm:text-sm"
            >
              {technicien.disponible ? "Rendre absent" : "Rendre présent"}
            </button>
          </div>
        ))}
      </div>

      {bascule.isPending ? (
        <p className="mt-3 inline-flex items-center gap-2 text-sm text-service">
          <RefreshCw size={14} className="animate-spin" />
          Modification en cours
        </p>
      ) : null}
    </Panneau>
  );
}
