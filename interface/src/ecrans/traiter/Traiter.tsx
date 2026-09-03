/**
 * Traitement d'une situation, de sa description a la decision.
 *
 * L'ecran suit un fil unique: le responsable decrit ce qui se passe, le
 * systeme etablit ce que cela implique, le responsable decide. Les trois
 * etapes se succedent sur le meme ecran, ce qui evite qu'une proposition ne
 * soit perdue de vue au moment de la valider.
 */

import { useState } from "react";
import { useLocation } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { interpreterEnonce, recommanderPourReservation, signalerUnIncident } from "@/api/client";
import type {
  ConsequencesRestituees,
  LectureRestituee,
  Recommandation,
  TypeIncident,
} from "@/api/contrat";
import { Panneau } from "@/composants/Panneau";
import { jourParDefaut } from "@/etat/jour";
import { useSession } from "@/etat/situation";
import { Decrire } from "./Decrire";
import { Proposition } from "./Proposition";
import { Progression } from "./Progression";

const INCIDENTS: readonly TypeIncident[] = [
  "degat_des_eaux",
  "panne_electrique",
  "panne_climatisation",
  "panne_plomberie",
  "defaut_serrure",
  "mobilier_endommage",
  "nuisance_sonore",
  "risque_securite",
];

export function Traiter() {
  const { traitement, definir, reinitialiser } = useSession();
  const emplacement = useLocation();
  const referenceInitiale =
    (emplacement.state as { reference?: string } | null)?.reference ?? null;

  const [enCours, setEnCours] = useState(false);

  const interpretation = useMutation({
    mutationFn: (texte: string) => interpreterEnonce(texte),
    onSuccess: (lecture) => definir({ lecture }),
  });

  const traitementDIncident = useMutation({
    mutationFn: (lecture: LectureRestituee) => {
      const chambre = lecture.entites.find(
        (entite) => entite.type_d_entite === "chambre",
      );
      return signalerUnIncident({
        chambre: chambre?.valeur ?? "",
        type_incident: lecture.intention as TypeIncident,
        jour: jourParDefaut(),
        temps_maximal: 20,
      });
    },
    onSuccess: (consequences: ConsequencesRestituees) => {
      definir({
        etape: "proposition",
        consequences,
        recommandation: null,
        etabliLe: new Date(),
      });
      setEnCours(false);
    },
    onError: () => setEnCours(false),
  });

  const affectation = useMutation({
    mutationFn: (reference: string) => recommanderPourReservation(reference),
    onSuccess: (recommandation: Recommandation, reference) => {
      definir({
        etape: "proposition",
        recommandation,
        consequences: null,
        reference,
        etabliLe: new Date(),
      });
      setEnCours(false);
    },
    onError: () => setEnCours(false),
  });

  const engager = (lecture: LectureRestituee) => {
    setEnCours(true);

    if (INCIDENTS.includes(lecture.intention as TypeIncident)) {
      traitementDIncident.mutate(lecture);
      return;
    }

    const reservation = lecture.entites.find(
      (entite) => entite.type_d_entite === "reservation",
    );
    if (reservation) {
      affectation.mutate(reservation.valeur);
      return;
    }

    setEnCours(false);
  };

  const recommencer = () => {
    reinitialiser();
    interpretation.reset();
    traitementDIncident.reset();
    affectation.reset();
  };

  return (
    <div className="flex flex-col gap-5">
      <Progression etape={traitement.etape} />

      {traitement.etape === "description" ? (
        <Decrire
          referenceInitiale={referenceInitiale}
          lecture={traitement.lecture}
          enLecture={interpretation.isPending}
          enTraitement={enCours}
          anomalie={
            interpretation.error ??
            traitementDIncident.error ??
            affectation.error
          }
          surSoumission={(texte) => interpretation.mutate(texte)}
          surConfirmation={engager}
          surAbandon={() => {
            definir({ lecture: null });
            interpretation.reset();
          }}
          surReference={(reference) => {
            setEnCours(true);
            affectation.mutate(reference);
          }}
        />
      ) : (
        <Proposition
          traitement={traitement}
          surDecision={() => definir({ etape: "consignee" })}
          surReprise={recommencer}
        />
      )}

      {traitement.etape === "consignee" ? (
        <Panneau ton="sourd">
          <p className="text-sm leading-relaxed text-service">
            La decision, la situation et la trace du raisonnement sont
            consignees. Vous pouvez la retrouver dans l'historique.
          </p>
        </Panneau>
      ) : null}
    </div>
  );
}