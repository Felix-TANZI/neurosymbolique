/**
 * Consultation de la base de connaissances.
 *
 * Les regles et les gabarits residents hors du code source: un administrateur
 * habilite les modifie sans recompilation. L'ecran expose leur organisation.
 */

import { FileCode, MessageSquareText } from "lucide-react";
import { Carte, EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";

interface Fichier {
  nom: string;
  role: string;
  nature: "regles" | "gabarits";
}

const FICHIERS: Fichier[] = [
  {
    nom: "diagnostic_chambres.lp",
    role: "Etablit les chambres admissibles et le motif de rejet des autres.",
    nature: "regles",
  },
  {
    nom: "decision_chambres.lp",
    role: "Applique les contraintes dures et ordonne selon les preferences.",
    nature: "regles",
  },
  {
    nom: "diagnostic_housekeeping.lp",
    role: "Etablit les paires tache-agent admissibles et leurs motifs de rejet.",
    nature: "regles",
  },
  {
    nom: "gabarits_chambres.toml",
    role: "Formulations des decisions et des rejets du service des chambres.",
    nature: "gabarits",
  },
  {
    nom: "gabarits_housekeeping.toml",
    role: "Formulations des plannings et des taches demeurees en attente.",
    nature: "gabarits",
  },
];

export function Administration() {
  return (
    <div className="flex flex-col gap-5">
      <Panneau ton="sourd">
        <EnTeteDeSection
          eyebrow="Base de connaissances"
          titre="Regles et formulations"
          action={<Pastille nature="neutre">Acces habilite</Pastille>}
        />
        <p className="max-w-2xl text-sm leading-relaxed text-service">
          Les regles et les formulations resident hors du code source. Leur
          modification change le comportement du systeme sans recompilation ni
          redeploiement. Une contrainte dure ne peut etre modifiee que depuis
          cet ecran, jamais par apprentissage.
        </p>
      </Panneau>

      <div className="grid gap-3 md:grid-cols-2">
        {FICHIERS.map((fichier) => (
          <Carte key={fichier.nom}>
            <div className="mb-2 flex items-center gap-2">
              {fichier.nature === "regles" ? (
                <FileCode size={16} className="text-accent" />
              ) : (
                <MessageSquareText size={16} className="text-accent" />
              )}
              <p className="font-mono text-sm">{fichier.nom}</p>
            </div>
            <p className="text-sm leading-relaxed text-service">
              {fichier.role}
            </p>
          </Carte>
        ))}
      </div>
    </div>
  );
}