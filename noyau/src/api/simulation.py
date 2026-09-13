"""Routes du simulateur du systeme de gestion.

Ces routes modifient l'etat de l'etablissement. Elles ne relevent pas du
systeme d'aide a la decision, qui demeure en lecture seule, mais simulent le
logiciel de gestion hoteliere dont il tire ses donnees.

Le prefixe les distingue dans la documentation de l'interface applicative:
qui la consulte voit immediatement ce qui gouverne l'etat et ce qui se borne a
le lire.
"""

import logging
from dataclasses import replace
from datetime import time

from fastapi import APIRouter, status

from src.api.dependances import SessionDeBase
from src.api.schemas_simulation import (
    AgentAjoute,
    DisponibiliteModifiee,
    EtatDeChambreModifie,
    ModificationConfirmee,
    TechnicienAjoute,
)
from src.domaine import (
    AgentEtage,
    DisponibiliteAgent,
    IdentifiantAgent,
    NumeroChambre,
    PlageDeService,
    Secteur,
)
from src.domaine.maintenance import IdentifiantTechnicien, Technicien
from src.donnees import (
    DepotAgents,
    DepotChambres,
    DepotTechniciens,
    EntiteIntrouvableError,
)

logger = logging.getLogger(__name__)

routeur = APIRouter(prefix="/simulation", tags=["simulation"])


@routeur.patch(
    "/chambres/{numero}",
    response_model=ModificationConfirmee,
    summary="Modifier l'etat d'une chambre",
)
def modifier_une_chambre(
    numero: str,
    modification: EtatDeChambreModifie,
    session: SessionDeBase,
) -> ModificationConfirmee:
    """Modifie l'etat d'une chambre, comme le ferait le logiciel de gestion."""
    depot = DepotChambres(session)

    try:
        chambre = depot.retrouver(NumeroChambre(numero))
    except EntiteIntrouvableError as erreur:
        raise _absente(f"chambre introuvable: {numero}") from erreur

    modifiee = replace(
        chambre,
        etat_proprete=modification.etat_proprete or chambre.etat_proprete,
        etat_technique=modification.etat_technique or chambre.etat_technique,
        etat_occupation=modification.etat_occupation or chambre.etat_occupation,
    )

    depot.enregistrer(modifiee, depot.secteur_de(chambre.numero))
    session.commit()

    logger.info("etat de la chambre %s modifie", numero)

    return ModificationConfirmee(
        objet=f"chambre {numero}",
        modification="etat modifie",
        etat_courant={
            "proprete": modifiee.etat_proprete.value,
            "technique": modifiee.etat_technique.value,
            "occupation": modifiee.etat_occupation.value,
        },
    )


@routeur.post(
    "/agents",
    response_model=ModificationConfirmee,
    status_code=status.HTTP_201_CREATED,
    summary="Inscrire un agent d'etage",
)
def inscrire_un_agent(
    ajout: AgentAjoute,
    session: SessionDeBase,
) -> ModificationConfirmee:
    """Inscrit un agent d'etage dans l'effectif."""
    DepotAgents(session).enregistrer(
        AgentEtage(
            identifiant=IdentifiantAgent(ajout.identifiant),
            secteur=Secteur(ajout.secteur),
            plage=PlageDeService(debut=time(8, 0), fin=time(16, 0)),
            disponibilite=(
                DisponibiliteAgent.PRESENT
                if ajout.disponible
                else DisponibiliteAgent.ABSENT
            ),
        )
    )
    session.commit()

    logger.info("agent %s inscrit", ajout.identifiant)

    return ModificationConfirmee(
        objet=f"agent {ajout.identifiant}",
        modification="inscrit",
        etat_courant={"secteur": ajout.secteur},
    )


@routeur.delete(
    "/agents/{identifiant}",
    response_model=ModificationConfirmee,
    summary="Retirer un agent de l'effectif",
)
def retirer_un_agent(
    identifiant: str,
    session: SessionDeBase,
) -> ModificationConfirmee:
    """Retire un agent de l'effectif."""
    depot = DepotAgents(session)

    try:
        depot.supprimer(IdentifiantAgent(identifiant))
    except EntiteIntrouvableError as erreur:
        raise _absente(f"agent introuvable: {identifiant}") from erreur

    session.commit()
    logger.info("agent %s retire", identifiant)

    return ModificationConfirmee(
        objet=f"agent {identifiant}", modification="retire"
    )


@routeur.post(
    "/techniciens",
    response_model=ModificationConfirmee,
    status_code=status.HTTP_201_CREATED,
    summary="Inscrire un technicien de maintenance",
)
def inscrire_un_technicien(
    ajout: TechnicienAjoute,
    session: SessionDeBase,
) -> ModificationConfirmee:
    """Inscrit un technicien avec ses qualifications."""
    DepotTechniciens(session).enregistrer(
        Technicien(
            identifiant=IdentifiantTechnicien(ajout.identifiant),
            competences=frozenset(ajout.competences),
            disponible=ajout.disponible,
            charge_en_cours=ajout.charge_en_cours,
        )
    )
    session.commit()

    logger.info("technicien %s inscrit", ajout.identifiant)

    return ModificationConfirmee(
        objet=f"technicien {ajout.identifiant}",
        modification="inscrit",
        etat_courant={
            "competences": ", ".join(
                competence.value for competence in ajout.competences
            )
        },
    )


@routeur.patch(
    "/techniciens/{identifiant}",
    response_model=ModificationConfirmee,
    summary="Modifier la disponibilite d'un technicien",
)
def modifier_un_technicien(
    identifiant: str,
    modification: DisponibiliteModifiee,
    session: SessionDeBase,
) -> ModificationConfirmee:
    """Rend un technicien disponible ou indisponible."""
    depot = DepotTechniciens(session)

    try:
        technicien = depot.retrouver(identifiant)
    except EntiteIntrouvableError as erreur:
        raise _absente(f"technicien introuvable: {identifiant}") from erreur

    depot.enregistrer(replace(technicien, disponible=modification.disponible))
    session.commit()

    logger.info(
        "technicien %s rendu %s",
        identifiant,
        "disponible" if modification.disponible else "indisponible",
    )

    return ModificationConfirmee(
        objet=f"technicien {identifiant}",
        modification=(
            "rendu disponible" if modification.disponible else "rendu indisponible"
        ),
    )


def _absente(message: str) -> Exception:
    """Constitue l'anomalie signalant une reference introuvable."""
    from fastapi import HTTPException

    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
