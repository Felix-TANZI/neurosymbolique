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


class OptionProposee(BaseModel):
    """Chambre possible, avec son cout et ce qui la distingue."""

    rang: int
    chambre: str
    cout: int
    avantages: list[str]
    contreparties: list[str]
    convoitee: bool = Field(
        default=False,
        description="Egalement proposee a un autre sejour deplace",
    )


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
    """Sejour prive de sa chambre et options qui lui sont ouvertes."""

    reservation: str
    client: str
    arrivee: date
    depart: date
    nombre_personnes: int
    chambre_proposee: str | None
    a_trouve_une_chambre: bool
    options: list[OptionProposee]
    options_equivalentes: bool = Field(
        description="Aucun critere ne departage les options proposees"
    )
    justification: str
    chambres_examinees: int
    chambres_admissibles: int
    motifs_dominants: list[str]

    @classmethod
    def depuis(cls, relogement: SejourARelogerr) -> "RelogementPropose":
        sejour = relogement.reservation
        eventail = relogement.eventail
        partagees = set(relogement.options_partagees)
        preferee = eventail.preferee

        dominants = [
            f"{motif}: {compte} chambres"
            for motif, compte in eventail.motifs_dominants[:3]
        ]

        return cls(
            reservation=str(sejour.identifiant),
            client=sejour.client.identifiant,
            arrivee=sejour.periode.arrivee,
            depart=sejour.periode.depart,
            nombre_personnes=sejour.nombre_personnes,
            chambre_proposee=relogement.chambre_proposee,
            a_trouve_une_chambre=relogement.a_trouve_une_chambre,
            options=[
                OptionProposee(
                    rang=option.rang,
                    chambre=option.chambre,
                    cout=option.cout,
                    avantages=list(option.avantages),
                    contreparties=list(option.contreparties),
                    convoitee=option.chambre in partagees,
                )
                for option in eventail.options
            ],
            options_equivalentes=eventail.sont_equivalentes,
            justification=(
                preferee.justification if preferee else eventail.resumer()
            ),
            chambres_examinees=eventail.examinees,
            chambres_admissibles=eventail.admissibles,
            motifs_dominants=dominants,
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
