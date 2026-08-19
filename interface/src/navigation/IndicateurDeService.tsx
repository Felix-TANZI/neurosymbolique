/**
 * Indicateur de disponibilite du noyau de raisonnement.
 *
 * L'indicateur distingue l'attente d'une reponse d'une indisponibilite
 * averee: un systeme d'aide a la decision ne doit jamais laisser croire qu'il
 * raisonne alors qu'il ne repond pas.
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
    return <Pastille nature="attente">Noyau injoignable</Pastille>;
  }

  if (isSuccess && !isFetching) {
    return <Pastille nature="conforme">Noyau disponible</Pastille>;
  }

  return <Pastille nature="neutre">Verification du noyau</Pastille>;
}