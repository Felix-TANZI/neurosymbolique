/**
 * Vue d'ensemble des services couverts.
 *
 * Le tableau de bord expose l'etendue du perimetre traite et la situation
 * courante, sans se substituer aux ecrans de decision.
 */

import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { Carte, EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { ListeDePastilles, Pastille } from "@/composants/Pastille";
import { useSession } from "@/etat/situation";

interface ServiceCouvert {
  nom: string;
  decisions: string[];
  moteur: string;
}

const SERVICES: ServiceCouvert[] = [
  {
    nom: "Gestion des chambres",
    decisions: ["Affectation", "Reaffectation", "Indisponibilite"],
    moteur: "Filtrage logique et ordonnancement des preferences",
  },
  {
    nom: "Housekeeping",
    decisions: ["Priorisation", "Chambre urgente", "Reaffectation d'agent"],
    moteur: "Filtrage logique et ordonnancement sous contraintes de temps",
  },
];

export function TableauDeBord() {
  const { session } = useSession();

  return (
    <div className="flex flex-col gap-5">
      <Panneau ton="accent">
        <p className="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-white/70">
          Principe de fonctionnement
        </p>
        <p className="max-w-3xl font-display text-3xl leading-tight text-white">
          La couche neuronale propose, la couche symbolique dispose
        </p>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-white/85">
          Aucune recommandation n'est restituee sans avoir ete etablie par un
          raisonnement verifiable, ni appliquee sans validation humaine.
        </p>
      </Panneau>

      <div className="grid gap-4 md:grid-cols-2">
        {SERVICES.map((service) => (
          <Carte key={service.nom}>
            <h3 className="mb-2 font-display text-xl">{service.nom}</h3>
            <p className="mb-3 text-sm leading-relaxed text-service">
              {service.moteur}
            </p>
            <ListeDePastilles>
              {service.decisions.map((decision) => (
                <Pastille key={decision}>{decision}</Pastille>
              ))}
            </ListeDePastilles>
          </Carte>
        ))}
      </div>

      <Panneau>
        <EnTeteDeSection
          eyebrow="Session courante"
          titre={
            session.etabliLe
              ? session.service === "chambres"
                ? `Sejour ${session.reference} analyse`
                : `Secteur ${session.secteur?.replace(/_/g, " ")} analyse`
              : "Aucune situation analysee"
          }
          action={
            <Link
              to="/analyse"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline"
            >
              Designer une situation
              <ArrowUpRight size={15} />
            </Link>
          }
        />
        <p className="max-w-2xl text-sm leading-relaxed text-service">
          {session.etabliLe
            ? `Situation soumise a ${session.etabliLe.toLocaleTimeString("fr-FR")}, en attente de decision.`
            : "Le systeme consulte l'etat de l'etablissement et compose lui-meme la situation a partir de l'entite designee."}
        </p>
      </Panneau>
    </div>
  );
}