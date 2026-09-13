/**
 * Traitement d'une demande, de sa formulation a la reponse.
 *
 * Le noyau etablit lui-meme la nature de la demande et conduit le traitement
 * appele. L'ecran presente la reponse selon cette nature: une consultation
 * s'affiche immediatement, une proposition de decision appelle une validation.
 *
 * Un enonce peut lui etre transmis depuis un autre ecran, le guide notamment:
 * il est alors soumis d'emblee, et la demande reste lisible dans le champ.
 */

import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { soumettreUneDemande } from "@/api/client";
import { jourParDefaut } from "@/etat/jour";
import { Decrire } from "./Decrire";
import { Restitution } from "./Restitution";

export function Traiter() {
  const location = useLocation();
  const dejaSoumis = useRef<string | null>(null);

  const transmis = (location.state as { enonce?: unknown } | null)?.enonce;
  const enonceTransmis =
    typeof transmis === "string" && transmis.trim() ? transmis : undefined;

  const demande = useMutation({
    mutationFn: (enonce: string) =>
      soumettreUneDemande(enonce, jourParDefaut()),
  });
  const { mutate } = demande;

  useEffect(() => {
    if (!enonceTransmis || dejaSoumis.current === location.key) return;
    dejaSoumis.current = location.key;
    mutate(enonceTransmis);
  }, [enonceTransmis, location.key, mutate]);

  return (
    <div className="flex flex-col gap-3 sm:gap-5">
      <Decrire
        key={location.key}
        enCours={demande.isPending}
        anomalie={demande.error}
        enonceInitial={enonceTransmis}
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
