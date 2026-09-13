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

  const avecIncidents = Boolean(incidents.data && incidents.data.length > 0);
  const avecArrivees = Boolean(arrivees.data && arrivees.data.length > 0);

  return (
    <div className="flex flex-col gap-3 sm:gap-5">
      <Panneau ton="encre">
        <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-creme/60">
              Journee du {enJourLisible(jour)}
            </p>
            <div className="flex items-end gap-3 md:block">
              <p className="font-display text-[var(--text-enorme)] leading-none text-accent">
                {aTraiter}
              </p>
              <p className="pb-1 font-display text-base leading-snug text-creme sm:text-xl md:mt-2 md:pb-0 lg:text-2xl">
                {aTraiter === 0
                  ? "Rien ne demande votre decision"
                  : aTraiter === 1
                    ? "situation demande votre decision"
                    : "situations demandent votre decision"}
              </p>
            </div>
          </div>

          <Link
            to="/traiter"
            className="inline-flex w-full items-center justify-center gap-2 rounded-[var(--radius-pastille)] bg-accent px-5 py-3 text-sm font-medium text-white transition-opacity hover:opacity-90 md:w-auto md:px-6"
          >
            <Sparkles size={16} />
            Decrire une situation
          </Link>
        </div>

        {etat.data ? (
          <div className="mt-4 grid grid-cols-3 gap-2 border-t border-white/10 pt-4 sm:max-w-xl sm:gap-4">
            <Indicateur
              valeur={etat.data.disponibles}
              libelle={`libres sur ${etat.data.chambres}`}
            />
            <Indicateur
              valeur={etat.data.agents_affectables}
              libelle="agents en service"
            />
            <Indicateur
              valeur={etat.data.taches_a_planifier}
              libelle="taches en attente"
            />
          </div>
        ) : null}
      </Panneau>

      {avecIncidents || avecArrivees ? (
        <div
          className={[
            "grid items-start gap-3 sm:gap-5",
            avecIncidents && avecArrivees
              ? "lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]"
              : "",
          ].join(" ")}
        >
          {incidents.data && avecIncidents ? (
            <Panneau ton="sourd">
              <EnTeteDeSection
                eyebrow="Incidents"
                titre="Chambres immobilisees"
                action={
                  <Pastille nature="attente">{incidents.data.length}</Pastille>
                }
              />
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3 lg:grid-cols-2">
                {incidents.data.slice(0, 6).map((incident) => (
                  <Carte key={incident.identifiant}>
                    <div className="flex items-start gap-2 sm:gap-3">
                      <TriangleAlert
                        size={15}
                        className="mt-0.5 shrink-0 text-accent"
                      />
                      <div className="min-w-0">
                        <p className="font-display text-base leading-tight sm:text-lg">
                          {incident.chambre}
                        </p>
                        <p className="text-xs text-service sm:text-sm">
                          {incident.type_incident.replace(/_/g, " ")}
                        </p>
                      </div>
                    </div>
                  </Carte>
                ))}
              </div>
            </Panneau>
          ) : null}

          {arrivees.data && avecArrivees ? (
            <Panneau>
              <EnTeteDeSection
                eyebrow="Arrivees"
                titre="Clients sans chambre attribuee"
                action={
                  <Pastille nature="accent">{arrivees.data.length}</Pastille>
                }
              />
              <div className="grid grid-cols-2 gap-2 sm:gap-3 xl:grid-cols-3">
                {arrivees.data.map((sejour) => (
                  <Carte key={sejour.identifiant} className="flex flex-col">
                    <div className="mb-2 flex items-start gap-2 sm:gap-3">
                      <BedDouble
                        size={15}
                        className="mt-0.5 hidden shrink-0 text-service sm:block"
                      />
                      <div className="min-w-0">
                        <p className="truncate font-display text-base leading-snug sm:text-lg">
                          {sejour.identifiant}
                        </p>
                        <p className="text-xs text-service sm:text-sm">
                          {sejour.nombre_personnes} pers. ·{" "}
                          {enHeureLisible(sejour.heure_arrivee_prevue)}
                          {sejour.arrivee_anticipee ? " · anticipee" : ""}
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
                      className="mt-auto inline-flex items-center gap-1.5 pt-3 text-xs font-medium text-accent hover:underline sm:text-sm"
                    >
                      Trouver une chambre
                      <ArrowRight size={14} />
                    </Link>
                  </Carte>
                ))}
              </div>
            </Panneau>
          ) : null}
        </div>
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

function Indicateur({ valeur, libelle }: { valeur: number; libelle: string }) {
  return (
    <div className="min-w-0">
      <p className="font-display text-xl leading-none tabular-nums text-creme sm:text-2xl">
        {valeur}
      </p>
      <p className="mt-1 text-xs leading-snug text-creme/60">{libelle}</p>
    </div>
  );
}