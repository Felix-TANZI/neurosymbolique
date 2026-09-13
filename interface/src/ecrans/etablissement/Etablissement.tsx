/**
 * Consultation de l'etat de l'etablissement.
 *
 * L'ecran restitue ce que le systeme connait: le parc, les effectifs, les
 * sejours et les interventions. Il ne permet aucune modification: l'etat de
 * l'exploitation est tenu ailleurs, et le systeme l'interroge sans le
 * gouverner.
 *
 * Sa fonction est de rendre le reste intelligible. Un responsable qui ignore
 * quelles chambres existent ne peut formuler une demande portant sur elles,
 * ni apprecier une proposition qui les mentionne.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BedDouble, Users, Wrench } from "lucide-react";
import {
  consulterAgents,
  consulterChambres,
  consulterEtablissement,
  consulterLesInterventions,
  consulterLesTechniciens,
} from "@/api/client";
import type {
  AgentConsulte,
  ChambreConsultee,
  InterventionConsultee,
  TechnicienConsulte,
} from "@/api/contrat";
import { EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { ListeDePastilles, Pastille } from "@/composants/Pastille";
import { jourParDefaut } from "@/etat/jour";

type Onglet = "chambres" | "personnel" | "maintenance";

const ONGLETS: { valeur: Onglet; libelle: string }[] = [
  { valeur: "chambres", libelle: "Chambres" },
  { valeur: "personnel", libelle: "Personnel" },
  { valeur: "maintenance", libelle: "Maintenance" },
];

const ETATS: Record<string, string> = {
  prete: "prête",
  sale: "sale",
  en_nettoyage: "en nettoyage",
  a_controler: "à contrôler",
  operationnelle: "opérationnelle",
  degradee: "dégradée",
  bloquee: "bloquée",
  libre: "libre",
  occupee: "occupée",
  attribuee: "attribuée",
};

const CRITICITES: Record<number, string> = {
  1: "différée",
  2: "courante",
  3: "prioritaire",
  4: "immédiate",
};

export function Etablissement() {
  const [onglet, setOnglet] = useState<Onglet>("chambres");
  const jour = jourParDefaut();

  const etat = useQuery({
    queryKey: ["etablissement", jour],
    queryFn: () => consulterEtablissement(jour),
  });

  return (
    <div className="flex flex-col gap-3 sm:gap-5">
      <Panneau ton="encre">
        <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-creme/60">
          Etablissement
        </p>
        <p className="font-display text-xl leading-tight text-creme sm:text-2xl lg:text-3xl">
          Ce que le système connaît
        </p>
        {etat.data ? (
          <div className="mt-4 grid grid-cols-4 gap-2 sm:mt-5 sm:gap-5">
            <Grandeur valeur={etat.data.chambres} libelle="chambres" />
            <Grandeur
              valeur={etat.data.disponibles}
              libelle="libres et prêtes"
              accentuee
            />
            <Grandeur valeur={etat.data.agents_affectables} libelle="agents" />
            <Grandeur
              valeur={etat.data.taches_a_planifier}
              libelle="tâches en attente"
            />
          </div>
        ) : null}
      </Panneau>

      <div className="grid grid-cols-3 gap-2 sm:flex sm:flex-wrap">
        {ONGLETS.map((candidat) => (
          <button
            key={candidat.valeur}
            type="button"
            onClick={() => setOnglet(candidat.valeur)}
            className={[
              "rounded-[var(--radius-pastille)] px-2 py-2.5 text-sm font-medium transition-colors sm:px-5",
              onglet === candidat.valeur
                ? "bg-encre text-creme"
                : "bg-sourd text-encre hover:bg-bordure",
            ].join(" ")}
          >
            {candidat.libelle}
          </button>
        ))}
      </div>

      {onglet === "chambres" ? <Chambres /> : null}
      {onglet === "personnel" ? <Personnel /> : null}
      {onglet === "maintenance" ? <Maintenance /> : null}
    </div>
  );
}

function Grandeur({
  valeur,
  libelle,
  accentuee = false,
}: {
  valeur: number;
  libelle: string;
  accentuee?: boolean;
}) {
  return (
    <div className="min-w-0">
      <p
        className={[
          "font-display text-2xl leading-none tabular-nums sm:text-3xl lg:text-4xl",
          accentuee ? "text-accent" : "text-creme",
        ].join(" ")}
      >
        {valeur}
      </p>
      <p className="mt-1 text-xs leading-snug text-creme/60 sm:text-sm">
        {libelle}
      </p>
    </div>
  );
}

function Chambres() {
  const [categorie, setCategorie] = useState<string | null>(null);

  const chambres = useQuery({
    queryKey: ["chambres"],
    queryFn: () => consulterChambres(),
  });

  const parc = chambres.data ?? [];
  const categories = [
    ...new Set(parc.map((chambre) => chambre.categorie_libelle)),
  ].sort();
  const retenues = categorie
    ? parc.filter((chambre) => chambre.categorie_libelle === categorie)
    : parc;

  return (
    <Panneau>
      <EnTeteDeSection
        eyebrow="Parc"
        titre="Chambres"
        action={<Pastille nature="neutre">{retenues.length}</Pastille>}
      />

      <div className="-mx-1 mb-4 flex gap-2 overflow-x-auto px-1 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0">
        <button
          type="button"
          onClick={() => setCategorie(null)}
          className={filtre(categorie === null)}
        >
          Toutes
        </button>
        {categories.map((nom) => (
          <button
            key={nom}
            type="button"
            onClick={() => setCategorie(nom)}
            className={filtre(categorie === nom)}
          >
            {nom.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {chambres.isPending ? (
        <p className="text-sm text-service">Consultation du parc...</p>
      ) : (
        <div className="grid grid-cols-2 gap-2 min-[480px]:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
          {retenues.map((chambre) => (
            <CarteDeChambre key={chambre.numero} chambre={chambre} />
          ))}
        </div>
      )}
    </Panneau>
  );
}

function CarteDeChambre({ chambre }: { chambre: ChambreConsultee }) {
  const attribuable =
    chambre.etat_proprete === "prete" &&
    chambre.etat_technique === "operationnelle" &&
    chambre.etat_occupation === "libre";

  return (
    <div
      className={[
        "min-w-0 rounded-[var(--radius-carte)] p-2.5 sm:p-3",
        attribuable ? "bg-accent-sourd" : "bg-sourd",
      ].join(" ")}
    >
      <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-2">
        <p className="font-display text-base leading-none sm:text-lg">
          {chambre.numero}
        </p>
        <span className="truncate text-xs text-service">
          {chambre.categorie_libelle.replace(/_/g, " ")}
        </span>
      </div>
      <p className="text-xs leading-relaxed text-service">
        {ETATS[chambre.etat_occupation] ?? chambre.etat_occupation} ·{" "}
        {ETATS[chambre.etat_proprete] ?? chambre.etat_proprete}
        {chambre.etat_technique !== "operationnelle"
          ? ` · ${ETATS[chambre.etat_technique] ?? chambre.etat_technique}`
          : ""}
      </p>
    </div>
  );
}

function Personnel() {
  const agents = useQuery({
    queryKey: ["agents"],
    queryFn: () => consulterAgents(),
  });
  const techniciens = useQuery({
    queryKey: ["techniciens"],
    queryFn: consulterLesTechniciens,
  });

  return (
    <div className="grid items-start gap-3 sm:gap-5 xl:grid-cols-3">
      <Panneau className="xl:col-span-2">
        <EnTeteDeSection
          eyebrow="Housekeeping"
          titre="Agents d'étage"
          action={
            <Pastille nature="neutre">{agents.data?.length ?? 0}</Pastille>
          }
        />
        <div className="grid grid-cols-2 gap-2 min-[480px]:grid-cols-3 lg:grid-cols-4 xl:grid-cols-3">
          {(agents.data ?? []).map((agent) => (
            <CarteDAgent key={agent.identifiant} agent={agent} />
          ))}
        </div>
      </Panneau>

      <Panneau>
        <EnTeteDeSection
          eyebrow="Maintenance"
          titre="Techniciens"
          action={
            <Pastille nature="neutre">{techniciens.data?.length ?? 0}</Pastille>
          }
        />
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-3 xl:grid-cols-1">
          {(techniciens.data ?? []).map((technicien) => (
            <CarteDeTechnicien
              key={technicien.identifiant}
              technicien={technicien}
            />
          ))}
        </div>
      </Panneau>
    </div>
  );
}

function CarteDAgent({ agent }: { agent: AgentConsulte }) {
  return (
    <div className="min-w-0 rounded-[var(--radius-carte)] bg-sourd p-2.5 sm:p-3">
      <div className="flex items-start gap-2.5">
        <Users size={15} className="mt-0.5 hidden shrink-0 text-service sm:block" />
        <div className="min-w-0">
          <p className="font-display text-base leading-none">
            {agent.identifiant}
          </p>
          <p className="mt-1 text-xs text-service">
            secteur {agent.secteur.replace(/_/g, " ")}
          </p>
        </div>
      </div>
    </div>
  );
}

function CarteDeTechnicien({
  technicien,
}: {
  technicien: TechnicienConsulte;
}) {
  return (
    <div
      className={[
        "min-w-0 rounded-[var(--radius-carte)] p-2.5 sm:p-3",
        technicien.disponible ? "bg-sourd" : "bg-accent-sourd",
      ].join(" ")}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-2.5">
          <Wrench size={15} className="mt-0.5 hidden shrink-0 text-service sm:block" />
          <div className="min-w-0">
            <p className="font-display text-base leading-none">
              {technicien.identifiant}
            </p>
            <p className="mt-1 text-xs text-service">
              {technicien.disponible ? "disponible" : "indisponible"} · charge{" "}
              {technicien.charge_en_cours}
            </p>
          </div>
        </div>
      </div>
      <ListeDePastilles>
        {technicien.competences.map((competence) => (
          <Pastille key={competence} nature="neutre">
            {competence}
          </Pastille>
        ))}
      </ListeDePastilles>
    </div>
  );
}

function Maintenance() {
  const interventions = useQuery({
    queryKey: ["interventions"],
    queryFn: consulterLesInterventions,
  });

  const liste = interventions.data ?? [];
  const enAttente = liste.filter(
    (intervention) => intervention.statut === "a_planifier",
  );

  return (
    <Panneau>
      <EnTeteDeSection
        eyebrow="Interventions"
        titre="Réparations enregistrées"
        action={
          enAttente.length > 0 ? (
            <Pastille nature="attente">{enAttente.length} en attente</Pastille>
          ) : (
            <Pastille nature="conforme">Toutes affectées</Pastille>
          )
        }
      />

      {interventions.isPending ? (
        <p className="text-sm text-service">Consultation des interventions...</p>
      ) : liste.length === 0 ? (
        <p className="text-sm leading-relaxed text-service">
          Aucune intervention n'est enregistrée.
        </p>
      ) : (
        <div className="grid gap-2 lg:grid-cols-2">
          {liste.map((intervention) => (
            <LigneDIntervention
              key={intervention.identifiant}
              intervention={intervention}
            />
          ))}
        </div>
      )}
    </Panneau>
  );
}

function LigneDIntervention({
  intervention,
}: {
  intervention: InterventionConsultee;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[var(--radius-carte)] bg-sourd px-3 py-2.5 sm:px-4 sm:py-3">
      <div className="flex min-w-0 items-center gap-2.5">
        <BedDouble size={15} className="hidden shrink-0 text-service sm:block" />
        <div className="min-w-0">
          <p className="font-display text-base leading-none">
            {intervention.objet}
          </p>
          <p className="mt-1 text-xs text-service">
            {intervention.competence === "polyvalent"
              ? "sans spécialité requise"
              : intervention.competence}{" "}
            · {intervention.duree_minutes} min
          </p>
        </div>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1 sm:flex-row sm:items-center sm:gap-2">
        <Pastille
          nature={intervention.criticite >= 3 ? "attente" : "neutre"}
        >
          {CRITICITES[intervention.criticite] ?? "courante"}
        </Pastille>
        {intervention.technicien ? (
          <span className="text-xs text-service">
            {intervention.technicien}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function filtre(actif: boolean): string {
  return [
    "shrink-0 whitespace-nowrap rounded-[var(--radius-pastille)] px-3 py-1.5 text-sm transition-colors sm:px-4",
    actif ? "bg-accent text-white" : "bg-sourd text-encre hover:bg-bordure",
  ].join(" ");
}
