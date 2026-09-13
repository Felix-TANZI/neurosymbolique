/**
 * Indicateur de disponibilite du noyau de raisonnement.
 *
 * L'indicateur distingue l'attente d'une reponse d'une indisponibilite
 * averee: un systeme d'aide a la decision ne doit jamais laisser croire qu'il
 * raisonne alors qu'il ne repond pas.
 *
 * Sur telephone, seule la pastille de couleur demeure: l'etat reste lisible
 * d'un coup d'oeil, et son libelle reste accessible aux lecteurs d'ecran.
 */

import { useQuery } from "@tanstack/react-query";
import { verifierDisponibilite } from "@/api/client";
import { Pastille } from "@/composants/Pastille";

export function IndicateurDeService() {
  const { isSuccess, isError, isFetching } = useQuery({
    queryKey: ["sante"],
    queryFn: verifierDisponibilite,
    refetchInterval: 10_000,
    refetchOnWindowFocus: true,
    refetchOnMount: "always",
    retry: false,
    staleTime: 0,
    gcTime: 0,
  });

  if (isError) {
    return (
      <Pastille nature="attente">
        <Etat couleur="bg-attente" libelle="Noyau injoignable" />
      </Pastille>
    );
  }

  if (isSuccess && !isFetching) {
    return (
      <Pastille nature="conforme">
        <Etat couleur="bg-succes" libelle="Noyau disponible" />
      </Pastille>
    );
  }

  return (
    <Pastille nature="neutre">
      <Etat couleur="bg-service" libelle="Verification du noyau" />
    </Pastille>
  );
}

function Etat({ couleur, libelle }: { couleur: string; libelle: string }) {
  return (
    <span className="inline-flex items-center gap-1.5" title={libelle}>
      <span aria-hidden="true" className={`size-2 rounded-full ${couleur}`} />
      <span className="sr-only sm:not-sr-only">{libelle}</span>
    </span>
  );
}
