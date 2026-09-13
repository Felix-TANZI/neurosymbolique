"""Affectation des interventions de maintenance aux techniciens.

Le service repond a trois decisions distinctes. Il qualifie la portee d'une
defaillance sur l'exploitation, ce qui determine l'urgence de sa reparation.
Il ordonne les interventions en attente selon cette portee. Il affecte enfin
chaque intervention a un technicien qualifie et disponible.

L'affectation n'est pas une simple mise en correspondance: un technicien
polyvalent conviendrait partout, mais l'employer sur une intervention qu'un
specialiste pourrait conduire priverait les interventions qui n'ont que lui.
L'arbitrage porte donc sur l'ensemble, non sur chaque intervention prise
isolement.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from src.domaine.maintenance import (
    Competence,
    Criticite,
    Intervention,
    Technicien,
)

logger = logging.getLogger(__name__)

CHARGE_MAXIMALE = 4


@dataclass(frozen=True, slots=True)
class InterventionAffectee:
    """Intervention et technicien retenu pour la conduire."""

    intervention: Intervention
    technicien: Technicien
    rang: int
    motif: str = ""

    @property
    def reference(self) -> str:
        return self.intervention.identifiant


@dataclass(frozen=True, slots=True)
class InterventionEnAttente:
    """Intervention qu'aucun technicien ne peut conduire."""

    intervention: Intervention
    cause: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class PlanDIntervention:
    """Ordonnancement etabli pour les interventions en attente."""

    affectees: tuple[InterventionAffectee, ...] = ()
    en_attente: tuple[InterventionEnAttente, ...] = ()
    justification: tuple[str, ...] = ()

    @property
    def est_complet(self) -> bool:
        return not self.en_attente

    @property
    def nombre_traite(self) -> int:
        return len(self.affectees)

    def par_technicien(self) -> dict[str, tuple[str, ...]]:
        """Restitue les interventions confiees a chaque technicien."""
        repartition: dict[str, list[str]] = {}
        for affectee in self.affectees:
            reference = str(affectee.technicien.identifiant)
            repartition.setdefault(reference, []).append(affectee.reference)
        return {
            technicien: tuple(references)
            for technicien, references in sorted(repartition.items())
        }


class AffecterLesInterventions:
    """Ordonne les interventions et les confie aux techniciens qualifies."""

    def executer(
        self,
        interventions: list[Intervention],
        techniciens: list[Technicien],
        maintenant: datetime | None = None,
    ) -> PlanDIntervention:
        """Etablit le plan d'intervention.

        Les interventions sont traitees par criticite decroissante: celle qui
        immobilise le plus est confiee la premiere, quand bien meme une autre
        serait plus rapide a conduire. Privilegier la rapidite laisserait une
        defaillance majeure sans reponse au profit de plusieurs mineures.
        """
        del maintenant

        a_traiter = [
            intervention
            for intervention in interventions
            if not intervention.est_achevee
        ]
        if not a_traiter:
            return PlanDIntervention(
                justification=("Aucune intervention n'est en attente.",)
            )

        disponibles = [
            technicien for technicien in techniciens if technicien.est_affectable
        ]
        if not disponibles:
            return PlanDIntervention(
                en_attente=tuple(
                    InterventionEnAttente(
                        intervention=intervention,
                        cause="aucun_technicien_disponible",
                    )
                    for intervention in a_traiter
                ),
                justification=(
                    "Aucun technicien n'est disponible: "
                    f"{len(a_traiter)} interventions demeurent en attente.",
                ),
            )

        ordonnees = sorted(
            a_traiter,
            key=lambda intervention: (
                -intervention.criticite,
                intervention.signalee_le,
            ),
        )

        charges: dict[str, int] = {
            str(technicien.identifiant): technicien.charge_en_cours
            for technicien in disponibles
        }

        affectees: list[InterventionAffectee] = []
        en_attente: list[InterventionEnAttente] = []

        for rang, intervention in enumerate(ordonnees, start=1):
            retenu = self._choisir(intervention, disponibles, charges)

            if retenu is None:
                en_attente.append(self._expliquer(intervention, disponibles))
                continue

            charges[str(retenu.identifiant)] += 1
            affectees.append(
                InterventionAffectee(
                    intervention=intervention.avec_technicien(retenu.identifiant),
                    technicien=retenu,
                    rang=rang,
                    motif=self._motiver(intervention, retenu),
                )
            )

        plan = PlanDIntervention(
            affectees=tuple(affectees),
            en_attente=tuple(en_attente),
            justification=self._justifier(affectees, en_attente),
        )
        logger.info(
            "plan etabli: %d affectees, %d en attente",
            len(affectees),
            len(en_attente),
        )
        return plan

    @staticmethod
    def _choisir(
        intervention: Intervention,
        techniciens: list[Technicien],
        charges: dict[str, int],
    ) -> Technicien | None:
        """Retient le technicien le mieux place pour une intervention.

        Un specialiste est prefere a un polyvalent: reserver la polyvalence
        aux interventions qu'aucun specialiste ne couvre evite de la consommer
        la ou elle n'est pas necessaire. A qualification egale, le technicien
        le moins charge est retenu.
        """
        competence = Competence(intervention.competence)

        qualifies = [
            technicien
            for technicien in techniciens
            if technicien.maitrise(competence)
            and charges[str(technicien.identifiant)] < CHARGE_MAXIMALE
        ]
        if not qualifies:
            return None

        return min(
            qualifies,
            key=lambda technicien: (
                0 if competence in technicien.competences else 1,
                charges[str(technicien.identifiant)],
                str(technicien.identifiant),
            ),
        )

    @staticmethod
    def _expliquer(
        intervention: Intervention, techniciens: list[Technicien]
    ) -> InterventionEnAttente:
        """Etablit pourquoi aucune affectation n'est possible."""
        competence = Competence(intervention.competence)
        qualifies = [
            technicien
            for technicien in techniciens
            if technicien.maitrise(competence)
        ]

        if not qualifies:
            return InterventionEnAttente(
                intervention=intervention,
                cause="competence_absente",
                detail=competence.value,
            )

        return InterventionEnAttente(
            intervention=intervention,
            cause="charge_saturee",
            detail=f"{len(qualifies)} techniciens qualifies, tous a pleine charge",
        )

    @staticmethod
    def _motiver(intervention: Intervention, technicien: Technicien) -> str:
        """Formule le motif d'une affectation.

        Le motif distingue trois situations: l'intervention n'exige aucune
        specialite, le technicien la possede, ou il intervient au titre de sa
        polyvalence. Les confondre laisserait croire a une qualification que le
        technicien n'a pas.
        """
        competence = Competence(intervention.competence)
        criticite = Criticite(intervention.criticite).name.lower()

        if competence is Competence.POLYVALENT:
            return (
                f"{technicien.identifiant} est disponible et l'intervention "
                f"n'exige aucune specialite, criticite {criticite}."
            )

        if competence in technicien.competences:
            return (
                f"{technicien.identifiant} est qualifie en {competence.value}, "
                f"criticite {criticite}."
            )

        return (
            f"{technicien.identifiant} intervient au titre de sa polyvalence, "
            f"aucun specialiste en {competence.value} n'etant disponible, "
            f"criticite {criticite}."
        )

    @staticmethod
    def _justifier(
        affectees: list[InterventionAffectee],
        en_attente: list[InterventionEnAttente],
    ) -> tuple[str, ...]:
        """Formule les consequences etablies."""
        enonces: list[str] = []

        if affectees:
            immediates = sum(
                1
                for affectee in affectees
                if affectee.intervention.criticite >= Criticite.PRIORITAIRE
            )
            enonces.append(
                f"{len(affectees)} interventions sont affectees, "
                f"dont {immediates} prioritaires ou immediates."
            )

        for manquee in en_attente:
            if manquee.cause == "competence_absente":
                enonces.append(
                    f"{manquee.intervention.identifiant} demeure en attente: "
                    f"aucun technicien n'est qualifie en {manquee.detail}."
                )
            elif manquee.cause == "charge_saturee":
                enonces.append(
                    f"{manquee.intervention.identifiant} demeure en attente: "
                    f"{manquee.detail}."
                )
            else:
                enonces.append(
                    f"{manquee.intervention.identifiant} demeure en attente."
                )

        return tuple(enonces)
