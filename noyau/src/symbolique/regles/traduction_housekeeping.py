"""Traduction du service housekeeping vers les moteurs de raisonnement.

La traduction opere en deux temps, conformement a la division du travail
retenue: elle produit d'abord les faits soumis au moteur logique, qui etablit
les paires tache-agent admissibles, puis convertit ces paires en entrees pour
le solveur d'ordonnancement.

Une paire ecartee par le moteur logique n'est pas transmise au solveur et ne
peut donc etre retenue, quelle que soit la ponderation.
"""

from collections.abc import Iterable, Mapping
from datetime import time

from src.domaine import (
    AgentEtage,
    Equipement,
    ServiceEtage,
    TacheNettoyage,
)
from src.symbolique.ordonnancement import AgentDisponible, TacheAOrdonnancer

from .execution import ConstatDePaires
from .traduction import TraductionImpossibleError

PREFIXE_TACHE = "t"
PREFIXE_AGENT = "a"

POIDS_ORDONNANCEMENT_PAR_DEFAUT: dict[str, int] = {
    "tache_non_planifiee": 1000,
    "priorite_urgente": 500,
    "priorite_elevee": 100,
    "hors_secteur": 20,
    "duree_de_service": 1,
}


def _normaliser(valeur: str) -> str:
    """Convertit une valeur du domaine en constante logique valide."""
    normalisee = valeur.strip().lower().replace("-", "_").replace(" ", "_")
    if not normalisee:
        raise TraductionImpossibleError("valeur vide, aucune constante productible")
    return normalisee


def _en_minutes(instant: time) -> int:
    """Exprime un instant de la journee en minutes depuis minuit."""
    return instant.hour * 60 + instant.minute


def identifiant_tache(tache: TacheNettoyage) -> str:
    """Produit l'identifiant logique d'une tache de nettoyage."""
    return f"{PREFIXE_TACHE}{_normaliser(tache.identifiant)}"


def identifiant_agent(agent: AgentEtage) -> str:
    """Produit l'identifiant logique d'un agent d'etage."""
    return f"{PREFIXE_AGENT}{_normaliser(str(agent.identifiant))}"


def traduire_agent(agent: AgentEtage) -> list[str]:
    """Produit les faits decrivant un agent d'etage."""
    reference = identifiant_agent(agent)
    return [
        f"agent({reference}).",
        f"disponibilite({reference}, {agent.disponibilite.value}).",
        f"minutes_restantes({reference}, {agent.minutes_restantes}).",
        f"secteur_agent({reference}, {_normaliser(str(agent.secteur))}).",
        f"debut_service({reference}, {_en_minutes(agent.plage.debut)}).",
        f"fin_service({reference}, {_en_minutes(agent.plage.fin)}).",
    ]


def traduire_tache(tache: TacheNettoyage) -> list[str]:
    """Produit les faits decrivant une tache de nettoyage."""
    reference = identifiant_tache(tache)
    faits = [
        f"tache({reference}).",
        f"prestation({reference}, {tache.prestation.value}).",
        f"duree({reference}, {tache.duree_effective}).",
        f"secteur_tache({reference}, {_normaliser(str(tache.secteur))}).",
        f"priorite({reference}, {tache.priorite.value}).",
        f"chambre_de({reference}, {_normaliser(str(tache.chambre))}).",
    ]
    if tache.echeance is not None:
        faits.append(f"echeance({reference}, {_en_minutes(tache.echeance)}).")
    return faits


def traduire_competences(
    competences_par_agent: Mapping[str, Iterable[str]],
) -> list[str]:
    """Produit les faits de competence des agents."""
    return [
        f"competence({PREFIXE_AGENT}{_normaliser(agent)}, {_normaliser(competence)})."
        for agent, competences in sorted(competences_par_agent.items())
        for competence in sorted(competences)
    ]


def traduire_competences_requises(
    exigences_par_tache: Mapping[str, Iterable[str]],
) -> list[str]:
    """Produit les faits de competence exigee par les taches."""
    return [
        f"competence_requise({PREFIXE_TACHE}{_normaliser(tache)}, "
        f"{_normaliser(competence)})."
        for tache, competences in sorted(exigences_par_tache.items())
        for competence in sorted(competences)
    ]


def traduire_secteurs_reserves(secteurs: Iterable[str]) -> list[str]:
    """Produit les faits designant les secteurs a acces restreint."""
    return [f"secteur_reserve({_normaliser(secteur)})." for secteur in sorted(secteurs)]


def traduire_service(
    service: ServiceEtage,
    competences_par_agent: Mapping[str, Iterable[str]] | None = None,
    exigences_par_tache: Mapping[str, Iterable[str]] | None = None,
    secteurs_reserves: Iterable[str] = (),
) -> str:
    """Assemble le programme logique decrivant une journee de service."""
    lignes: list[str] = []

    for agent in sorted(service.agents, key=lambda a: str(a.identifiant)):
        lignes.extend(traduire_agent(agent))

    for tache in sorted(service.taches_a_planifier, key=lambda t: t.identifiant):
        lignes.extend(traduire_tache(tache))

    lignes.extend(traduire_competences(competences_par_agent or {}))
    lignes.extend(traduire_competences_requises(exigences_par_tache or {}))
    lignes.extend(traduire_secteurs_reserves(secteurs_reserves))

    return "\n".join(lignes)


def vers_taches_a_ordonnancer(
    service: ServiceEtage, constat: ConstatDePaires
) -> list[TacheAOrdonnancer]:
    """Convertit les taches et leurs agents admissibles en entrees du solveur.

    Seules les paires declarees admissibles par le moteur logique sont
    transmises: le solveur ne peut donc retenir une paire ecartee.
    """
    return [
        TacheAOrdonnancer(
            identifiant=identifiant_tache(tache),
            duree_minutes=tache.duree_effective,
            agents_admissibles=constat.ressources_admissibles(identifiant_tache(tache)),
            echeance_minutes=(
                _en_minutes(tache.echeance) if tache.echeance is not None else None
            ),
            priorite=tache.priorite.value,
            secteur=_normaliser(str(tache.secteur)),
        )
        for tache in sorted(service.taches_a_planifier, key=lambda t: t.identifiant)
    ]


def vers_agents_disponibles(service: ServiceEtage) -> list[AgentDisponible]:
    """Convertit les agents en service en ressources du solveur.

    La plage retenue debute a l'issue de la charge deja affectee, afin que les
    horaires calcules tiennent compte du travail en cours.
    """
    ressources: list[AgentDisponible] = []
    for agent in sorted(service.agents_affectables, key=lambda a: str(a.identifiant)):
        debut = _en_minutes(agent.plage.debut) + agent.minutes_deja_affectees
        fin = _en_minutes(agent.plage.fin)
        if debut >= fin:
            continue
        ressources.append(
            AgentDisponible(
                identifiant=identifiant_agent(agent),
                debut_minutes=debut,
                fin_minutes=fin,
                secteur=_normaliser(str(agent.secteur)),
            )
        )
    return ressources


def equipements_en_competences(equipements: Iterable[Equipement]) -> list[str]:
    """Derive des competences a partir des equipements d'une chambre.

    Certains equipements imposent une qualification particuliere pour la
    remise en etat, ce que la base de connaissances exploite par les regles de
    competence requise.
    """
    return sorted(equipement.value for equipement in equipements)
