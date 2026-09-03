"""Schemas d'echange du traitement d'incident.

Les schemas exposent les consequences etablies pour un incident signale:
immobilisation eventuelle de la chambre, sejours prives d'hebergement et
proposition faite a chacun.

Rien n'est applique. L'ensemble constitue une proposition, que le responsable
valide, corrige ou refuse: une immobilisation et un relogement engagent
l'exploitation et ne sauraient resulter d'une inference.
"""

from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field

from src.domaine import Gravite, TypeIncident
from src.orchestration import ConsequencesDUnIncident, SejourARelogerr

Reference = Annotated[str, Field(min_length=1, max_length=64)]


class IncidentSignale(BaseModel):
    """Incident constate sur une chambre de l'etablissement."""

    chambre: Reference = Field(examples=["319"])
    type_incident: TypeIncident = Field(examples=[TypeIncident.DEGAT_DES_EAUX])
    gravite: Gravite = Field(
        default=Gravite.MAJEURE,
        description=(
            "La gravite determine l'immobilisation: une panne mineure degrade "
            "le confort, une panne majeure interdit l'occupation."
        ),
    )
    description: str = Field(default="", max_length=512)
    jour: date | None = Field(
        default=None,
        description="Jour du constat. Le jour courant a defaut.",
    )
    temps_maximal: float | None = Field(default=None, gt=0, le=60)


class RelogementPropose(BaseModel):
    """Sejour prive de sa chambre et proposition qui lui est faite."""

    reservation: str
    client: str
    arrivee: date
    depart: date
    nombre_personnes: int
    chambre_proposee: str | None
    a_trouve_une_chambre: bool
    justification: str
    chambres_examinees: int
    chambres_admissibles: int
    motifs_dominants: list[str] = Field(
        description=(
            "Motifs ayant ecarte le plus de chambres, restitues lorsqu'aucune "
            "solution n'existe."
        )
    )

    @classmethod
    def depuis(cls, relogement: SejourARelogerr) -> "RelogementPropose":
        sejour = relogement.reservation
        recommandation = relogement.recommandation

        comptes: dict[str, int] = {}
        for option in recommandation.options_ecartees:
            for motif in option.motifs:
                comptes[motif.motif] = comptes.get(motif.motif, 0) + 1

        dominants = [
            f"{motif}: {compte} chambres"
            for motif, compte in sorted(comptes.items(), key=lambda paire: -paire[1])[:3]
        ]

        return cls(
            reservation=str(sejour.identifiant),
            client=sejour.client.identifiant,
            arrivee=sejour.periode.arrivee,
            depart=sejour.periode.depart,
            nombre_personnes=sejour.nombre_personnes,
            chambre_proposee=relogement.chambre_proposee,
            a_trouve_une_chambre=relogement.a_trouve_une_chambre,
            justification=recommandation.justification.decision.texte,
            chambres_examinees=recommandation.nombre_examinees,
            chambres_admissibles=len(recommandation.resultat.admissibles),
            motifs_dominants=[] if relogement.a_trouve_une_chambre else dominants,
        )


class ConsequencesRestituees(BaseModel):
    """Ensemble des consequences etablies pour un incident signale."""

    chambre: str
    immobilise_la_chambre: bool
    justification: list[str]
    sejours_a_reloger: list[RelogementPropose]
    nombre_de_sejours: int
    sejours_sans_solution: int
    est_entierement_resolu: bool
    demande_une_intervention: bool = Field(
        description="Un sejour demeure sans solution automatique"
    )

    @classmethod
    def depuis(
        cls, consequences: ConsequencesDUnIncident
    ) -> "ConsequencesRestituees":
        return cls(
            chambre=consequences.chambre,
            immobilise_la_chambre=consequences.immobilise_la_chambre,
            justification=list(consequences.justification),
            sejours_a_reloger=[
                RelogementPropose.depuis(relogement)
                for relogement in consequences.sejours_a_reloger
            ],
            nombre_de_sejours=consequences.nombre_de_sejours,
            sejours_sans_solution=len(consequences.sejours_sans_solution),
            est_entierement_resolu=consequences.est_entierement_resolu,
            demande_une_intervention=consequences.demande_une_intervention,
        )
