/**
 * Description d'une situation operationnelle.
 *
 * La saisie est libre: le responsable formule ce qui se passe comme il le
 * dirait a un collegue. Le systeme etablit ce qu'il a compris et le soumet a
 * confirmation avant d'engager quoi que ce soit.
 */

import { useState } from "react";
import { CornerDownLeft, RefreshCw } from "lucide-react";
import { ErreurDeNoyau } from "@/api/client";
import { EnTeteDeSection, Panneau } from "@/composants/Panneau";

const EXEMPLES: string[] = [
  "quelles chambres sont disponibles",
  "il y a une fuite dans la 319",
  "quel est l'etat de la 312",
];

interface Proprietes {
  enCours: boolean;
  anomalie: unknown;
  surSoumission: (enonce: string) => void;
}

export function Decrire({ enCours, anomalie, surSoumission }: Proprietes) {
  const [enonce, setEnonce] = useState("");

  const soumettre = () => {
    const texte = enonce.trim();
    if (texte) {
      surSoumission(texte);
    }
  };

  return (
    <Panneau>
      <EnTeteDeSection
        eyebrow="Etape 1"
        titre="Que se passe-t-il ?"
      />

      <p className="mb-4 max-w-2xl text-sm leading-relaxed text-service">
        Ecrivez la situation comme vous la diriez a un collegue. Le systeme
        etablit ce qu'elle implique et vous soumet une proposition. Rien n'est
        engage sans votre accord.
      </p>

      <div className="flex flex-col gap-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={enonce}
            onChange={(evenement) => setEnonce(evenement.target.value)}
            onKeyDown={(evenement) => {
              if (evenement.key === "Enter") {
                soumettre();
              }
            }}
            placeholder="il y a une fuite dans la 319"
            disabled={enCours}
            aria-label="Description de la situation"
            className="flex-1 rounded-[var(--radius-carte)] border border-bordure bg-creme px-4 py-3.5 text-base outline-none placeholder:text-service/50 focus:border-encre disabled:opacity-60"
          />
          <button
            type="button"
            onClick={soumettre}
            disabled={enCours || !enonce.trim()}
            className="inline-flex items-center gap-2 rounded-[var(--radius-pastille)] bg-encre px-6 py-3.5 text-sm font-medium text-creme transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {enCours ? (
              <>
                <RefreshCw size={16} className="animate-spin" />
                Lecture
              </>
            ) : (
              <>
                Soumettre
                <CornerDownLeft size={16} />
              </>
            )}
          </button>
        </div>

        {!enCours ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-service">Par exemple :</span>
            {EXEMPLES.map((exemple) => (
              <button
                key={exemple}
                type="button"
                onClick={() => {
                  setEnonce(exemple);
                  surSoumission(exemple);
                }}
                className="rounded-[var(--radius-pastille)] bg-sourd px-3 py-1.5 text-sm text-encre transition-colors hover:bg-bordure"
              >
                {exemple}
              </button>
            ))}
          </div>
        ) : null}

        {anomalie ? <Anomalie erreur={anomalie} /> : null}
      </div>
    </Panneau>
  );
}

function Anomalie({ erreur }: { erreur: unknown }) {
  const connue = erreur instanceof ErreurDeNoyau;
  const message = connue ? erreur.message : "Le systeme n'a pas repondu.";
  const conduite =
    connue && erreur.statut === 503
      ? "Le systeme n'est pas entierement demarre. Reessayez dans un instant."
      : connue && erreur.statut === 404
        ? "La chambre ou le sejour mentionne n'existe pas dans l'etablissement."
        : "Reformulez la situation, puis soumettez a nouveau.";

  return (
    <div className="rounded-[var(--radius-carte)] bg-accent-sourd p-4">
      <p className="text-sm font-medium text-accent">{message}</p>
      <p className="mt-1 text-sm text-service">{conduite}</p>
    </div>
  );
}
