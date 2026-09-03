/**
 * Vue des situations appelant une decision.
 *
 * L'ecran presente ce qu'un responsable a effectivement a traiter, exprime
 * dans les termes de son metier. Les grandeurs du systeme ne figurent pas:
 * un compte de taches en attente n'appelle aucune action, un client sans
 * chambre en appelle une.
 */

import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BedDouble, Sparkles, TriangleAlert } from "lucide-react";
import {
  consulterArriveesATraiter,
  consulterEtablissement,
  consulterIncidents,
} from "@/api/client";
import { Carte, EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { ListeDePastilles, Pastille } from "@/composants/Pastille";
import { enHeureLisible, enJourLisible, jourParDefaut } from "@/etat/jour";

export function Aujourdhui() {
  const jour = jourParDefaut();

  const etat = useQuery({
    queryKey: ["etablissement", jour],
    queryFn: () => consulterEtablissement(jour),
  });

  const arrivees = useQuery({
    queryKey: ["arrivees", jour],
    queryFn: () => consulterArriveesATraiter(jour),
  });

  const incidents = useQuery({
    queryKey: ["incidents"],
    queryFn: consulterIncidents,
  });

  const aTraiter =
    (arrivees.data?.length ?? 0) + (incidents.data?.length ?? 0);

  return (
    <div className="flex flex-col gap-5">
      <Panneau ton="encre">
        <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-creme/60">
          Journee du {enJourLisible(jour)}
        </p>
        <p className="font-display text-[var(--text-enorme)] leading-none text-accent">
          {aTraiter}
        </p>
        <p className="mt-2 font-display text-2xl text-creme">
          {aTraiter === 0
            ? "Rien ne demande votre decision"
            : aTraiter === 1
              ? "situation demande votre decision"
              : "situations demandent votre decision"}
        </p>

        {etat.data ? (
          <p className="mt-4 max-w-2xl text-sm leading-relaxed text-creme/70">
            {etat.data.disponibles} chambres sont libres et pretes sur les{" "}
            {etat.data.chambres} de l'etablissement.{" "}
            {etat.data.agents_affectables} agents sont en service.
          </p>
        ) : null}

        <Link
          to="/traiter"
          className="mt-5 inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-accent px-6 py-3 text-sm font-medium text-white transition-opacity hover:opacity-90"
        >
          <Sparkles size={16} />
          Decrire une situation
        </Link>
      </Panneau>

      {incidents.data && incidents.data.length > 0 ? (
        <Panneau ton="sourd">
          <EnTeteDeSection
            eyebrow="Incidents"
            titre="Chambres immobilisees"
            action={
              <Pastille nature="attente">{incidents.data.length}</Pastille>
            }
          />
          <div className="grid gap-3 md:grid-cols-2">
            {incidents.data.slice(0, 6).map((incident) => (
              <Carte key={incident.identifiant}>
                <div className="flex items-start gap-3">
                  <TriangleAlert size={16} className="mt-1 shrink-0 text-accent" />
                  <div>
                    <p className="font-display text-lg">
                      Chambre {incident.chambre}
                    </p>
                    <p className="text-sm text-service">
                      {incident.type_incident.replace(/_/g, " ")}
                    </p>
                  </div>
                </div>
              </Carte>
            ))}
          </div>
        </Panneau>
      ) : null}

      {arrivees.data && arrivees.data.length > 0 ? (
        <Panneau>
          <EnTeteDeSection
            eyebrow="Arrivees"
            titre="Clients sans chambre attribuee"
            action={<Pastille nature="accent">{arrivees.data.length}</Pastille>}
          />
          <div className="grid gap-3 md:grid-cols-2">
            {arrivees.data.map((sejour) => (
              <Carte key={sejour.identifiant}>
                <div className="mb-2 flex items-start gap-3">
                  <BedDouble size={16} className="mt-1 shrink-0 text-service" />
                  <div>
                    <p className="font-display text-lg leading-snug">
                      {sejour.identifiant}
                    </p>
                    <p className="text-sm text-service">
                      {sejour.nombre_personnes} personne
                      {sejour.nombre_personnes > 1 ? "s" : ""}, arrivee{" "}
                      {enHeureLisible(sejour.heure_arrivee_prevue)}
                      {sejour.arrivee_anticipee ? ", avant l'heure garantie" : ""}
                    </p>
                  </div>
                </div>

                {sejour.exigences_obligatoires.length > 0 ? (
                  <ListeDePastilles>
                    {sejour.exigences_obligatoires.map((equipement) => (
                      <Pastille key={equipement} nature="accent">
                        {equipement.replace(/_/g, " ")}
                      </Pastille>
                    ))}
                  </ListeDePastilles>
                ) : null}

                <Link
                  to="/traiter"
                  state={{ reference: sejour.identifiant }}
                  className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline"
                >
                  Trouver une chambre
                  <ArrowRight size={14} />
                </Link>
              </Carte>
            ))}
          </div>
        </Panneau>
      ) : null}

      {aTraiter === 0 && !arrivees.isPending ? (
        <Panneau ton="sourd">
          <p className="text-sm leading-relaxed text-service">
            Tous les clients attendus disposent d'une chambre et aucune
            immobilisation n'est en cours. Vous pouvez neanmoins decrire une
            situation qui surviendrait.
          </p>
        </Panneau>
      ) : null}
    </div>
  );
}