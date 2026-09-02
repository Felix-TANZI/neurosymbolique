/**
 * Saisie libre d'une situation operationnelle.
 *
 * L'enonce est interprete par le noyau, qui en etablit l'intention et les
 * elements. Aucune action n'en decoule directement: la lecture est presentee
 * au responsable, qui la confirme ou la corrige.
 *
 * La confirmation demeure requise meme lorsque la lecture est recevable. Une
 * decision critique fondee sur une interpretation non verifiee reporterait
 * sur la machine une responsabilite qui revient a l'exploitant.
 */

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { CornerDownLeft, RefreshCw } from "lucide-react";
import { ErreurDeNoyau, interpreterEnonce } from "@/api/client";
import type { LectureRestituee } from "@/api/contrat";
import { EnTeteDeSection, Panneau } from "@/composants/Panneau";
import { Pastille } from "@/composants/Pastille";
import { LectureProposee } from "./LectureProposee";

interface Proprietes {
  surConfirmation: (lecture: LectureRestituee) => void;
}

export function SaisieLibre({ surConfirmation }: Proprietes) {
  const [enonce, setEnonce] = useState("");

  const interpretation = useMutation({
    mutationFn: (texte: string) => interpreterEnonce(texte),
  });

  const soumettre = () => {
    const texte = enonce.trim();
    if (texte) {
      interpretation.mutate(texte);
    }
  };

  const lecture = interpretation.data;

  return (
    <Panneau>
      <EnTeteDeSection
        eyebrow="Saisie libre"
        titre="Decrire la situation"
        action={
          <Pastille nature="neutre">Confirmation requise</Pastille>
        }
      />

      <div className="flex flex-col gap-3">
        <label htmlFor="enonce" className="text-sm text-service">
          Formulez la situation comme vous la diriez a un collegue.
        </label>

        <div className="flex gap-2">
          <input
            id="enonce"
            type="text"
            value={enonce}
            onChange={(evenement) => setEnonce(evenement.target.value)}
            onKeyDown={(evenement) => {
              if (evenement.key === "Enter") {
                soumettre();
              }
            }}
            placeholder="il y a une fuite dans la 407"
            disabled={interpretation.isPending}
            className="flex-1 rounded-[var(--radius-carte)] border border-bordure bg-creme px-4 py-3 text-sm outline-none placeholder:text-service/50 focus:border-encre disabled:opacity-60"
          />
          <button
            type="button"
            onClick={soumettre}
            disabled={interpretation.isPending || !enonce.trim()}
            className="inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-encre px-5 py-3 text-sm font-medium text-creme transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {interpretation.isPending ? (
              <>
                <RefreshCw size={16} className="animate-spin" />
                Lecture
              </>
            ) : (
              <>
                Interpreter
                <CornerDownLeft size={16} />
              </>
            )}
          </button>
        </div>

        {interpretation.isError ? (
          <AnomalieDeLecture erreur={interpretation.error} />
        ) : null}

        {lecture ? (
          <LectureProposee
            lecture={lecture}
            surConfirmation={() => surConfirmation(lecture)}
            surAbandon={() => interpretation.reset()}
          />
        ) : null}
      </div>
    </Panneau>
  );
}

function AnomalieDeLecture({ erreur }: { erreur: unknown }) {
  const connue = erreur instanceof ErreurDeNoyau;
  const message = connue
    ? erreur.message
    : "Le noyau d'interpretation n'a pas repondu.";
  const conduite =
    connue && erreur.statut === 503
      ? "Le modele d'interpretation n'est pas disponible. Executez le script de specialisation."
      : "Reformulez la situation, puis soumettez a nouveau.";

  return (
    <div className="rounded-[var(--radius-carte)] bg-accent-sourd p-4">
      <p className="text-sm font-medium text-accent">{message}</p>
      <p className="mt-1 text-sm text-service">{conduite}</p>
    </div>
  );
}
