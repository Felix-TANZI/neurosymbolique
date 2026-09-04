/**
 * Traitement d'une demande, de sa formulation a la reponse.
 *
 * Le noyau etablit lui-meme la nature de la demande et conduit le traitement
 * appele. L'ecran presente la reponse selon cette nature: une consultation
 * s'affiche immediatement, une proposition de decision appelle une validation.
 */

import { useMutation } from "@tanstack/react-query";
import { soumettreUneDemande } from "@/api/client";
import { jourParDefaut } from "@/etat/jour";
import { Decrire } from "./Decrire";
import { Restitution } from "./Restitution";

export function Traiter() {
  const demande = useMutation({
    mutationFn: (enonce: string) =>
      soumettreUneDemande(enonce, jourParDefaut()),
  });

  return (
    <div className="flex flex-col gap-5">
      <Decrire
        enCours={demande.isPending}
        anomalie={demande.error}
        surSoumission={(enonce) => demande.mutate(enonce)}
      />

      {demande.data ? (
        <Restitution
          reponse={demande.data}
          surReprise={() => demande.reset()}
        />
      ) : null}
    </div>
  );
}
