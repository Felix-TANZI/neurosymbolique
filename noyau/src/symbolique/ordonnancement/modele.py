"""Ordonnancement des taches de nettoyage par programmation par contraintes.

Le module recoit les paires tache-agent declarees admissibles par le moteur
logique et calcule un ordonnancement effectif: heure de debut, heure de fin et
agent pour chaque tache planifiee.

La division du travail est celle retenue a la conception: le moteur logique
etablit ce qui est permis et en conserve la trace; le solveur d'ordonnancement
choisit parmi le permis. Une paire ecartee par le moteur logique n'entre pas
dans le modele et ne peut donc etre retenue, quelle que soit la ponderation.

Le modele emploie des variables d'intervalle et la contrainte de
non-recouvrement, dont le propagateur traite les conflits temporels plus
efficacement qu'une decomposition en contraintes deux a deux.
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ortools.sat.python import cp_model

logger = logging.getLogger(__name__)

TEMPS_DE_CALCUL_PAR_DEFAUT = 10.0

POIDS_PAR_DEFAUT: dict[str, int] = {
    "tache_non_planifiee": 1000,
    "priorite_urgente": 500,
    "priorite_elevee": 100,
    "hors_secteur": 20,
    "duree_de_service": 1,
}


class OrdonnancementImpossibleError(RuntimeError):
    """Signale une defaillance du solveur d'ordonnancement."""


@dataclass(frozen=True, slots=True)
class TacheAOrdonnancer:
    """Tache soumise a l'ordonnancement, avec ses agents admissibles."""

    identifiant: str
    duree_minutes: int
    agents_admissibles: frozenset[str]
    echeance_minutes: int | None = None
    priorite: int = 1
    secteur: str = ""

    def __post_init__(self) -> None:
        if self.duree_minutes <= 0:
            raise ValueError(f"duree invalide pour la tache {self.identifiant}")


@dataclass(frozen=True, slots=True)
class AgentDisponible:
    """Agent pouvant recevoir des taches sur une plage de service."""

    identifiant: str
    debut_minutes: int
    fin_minutes: int
    secteur: str = ""

    def __post_init__(self) -> None:
        if self.fin_minutes <= self.debut_minutes:
            raise ValueError(f"plage invalide pour l'agent {self.identifiant}")

    @property
    def capacite_minutes(self) -> int:
        return self.fin_minutes - self.debut_minutes


@dataclass(frozen=True, slots=True)
class TachePlanifiee:
    """Tache effectivement ordonnancee, avec son agent et ses horaires."""

    tache: str
    agent: str
    debut_minutes: int
    fin_minutes: int

    @property
    def duree_minutes(self) -> int:
        return self.fin_minutes - self.debut_minutes


@dataclass(frozen=True, slots=True)
class Ordonnancement:
    """Issue d'un ordonnancement, planifie ou partiellement planifie."""

    planifiees: tuple[TachePlanifiee, ...] = ()
    non_planifiees: frozenset[str] = field(default_factory=frozenset)
    cout: int = 0
    optimal: bool = False
    interrompu: bool = False

    @property
    def est_complet(self) -> bool:
        return not self.non_planifiees

    @property
    def charge_par_agent(self) -> dict[str, int]:
        """Restitue le total de minutes affectees a chaque agent."""
        charges: dict[str, int] = {}
        for planifiee in self.planifiees:
            charges[planifiee.agent] = (
                charges.get(planifiee.agent, 0) + planifiee.duree_minutes
            )
        return charges

    def taches_de(self, agent: str) -> tuple[TachePlanifiee, ...]:
        """Restitue les taches confiees a un agent, dans l'ordre chronologique."""
        return tuple(
            sorted(
                (p for p in self.planifiees if p.agent == agent),
                key=lambda p: p.debut_minutes,
            )
        )


class _ModeleOrdonnancement:
    """Construction du modele de contraintes et lecture de sa solution."""

    def __init__(
        self,
        taches: Sequence[TacheAOrdonnancer],
        agents: Sequence[AgentDisponible],
        poids: Mapping[str, int],
    ) -> None:
        self._taches = taches
        self._agents = {agent.identifiant: agent for agent in agents}
        self._poids = poids
        self._modele: Any = cp_model.CpModel()
        self._planifiee: dict[str, Any] = {}
        self._affectation: dict[tuple[str, str], Any] = {}
        self._intervalles: dict[tuple[str, str], Any] = {}
        self._debuts: dict[str, Any] = {}
        self._fins: dict[str, Any] = {}
        self._achevement: Any = None

    def construire(self) -> Any:
        """Declare les variables, les contraintes et la fonction d'evaluation."""
        self._declarer_variables()
        self._contraindre_affectation_unique()
        self._contraindre_non_recouvrement()
        self._contraindre_echeances()
        self._contraindre_achevement()
        self._evaluer()
        return self._modele

    def _declarer_variables(self) -> None:
        """Cree une variable d'intervalle par paire tache-agent admissible.

        L'intervalle est optionnel: il n'occupe la ressource que si la paire
        correspondante est retenue.
        """
        horizon = max((agent.fin_minutes for agent in self._agents.values()), default=0)
        self._achevement = self._modele.NewIntVar(0, horizon, "achevement_du_service")
        for tache in self._taches:
            self._planifiee[tache.identifiant] = self._modele.NewBoolVar(
                f"planifiee_{tache.identifiant}"
            )
            self._debuts[tache.identifiant] = self._modele.NewIntVar(
                0, horizon, f"debut_{tache.identifiant}"
            )
            self._fins[tache.identifiant] = self._modele.NewIntVar(
                0, horizon, f"fin_{tache.identifiant}"
            )

            for identifiant_agent in sorted(tache.agents_admissibles):
                agent = self._agents.get(identifiant_agent)
                if agent is None:
                    continue
                cle = (tache.identifiant, identifiant_agent)
                self._affectation[cle] = self._modele.NewBoolVar(f"affecte_{cle}")
                self._intervalles[cle] = self._modele.NewOptionalIntervalVar(
                    self._debuts[tache.identifiant],
                    tache.duree_minutes,
                    self._fins[tache.identifiant],
                    self._affectation[cle],
                    f"intervalle_{cle}",
                )
                self._modele.Add(
                    self._debuts[tache.identifiant] >= agent.debut_minutes
                ).OnlyEnforceIf(self._affectation[cle])
                self._modele.Add(
                    self._fins[tache.identifiant] <= agent.fin_minutes
                ).OnlyEnforceIf(self._affectation[cle])

    def _contraindre_affectation_unique(self) -> None:
        """Une tache planifiee est confiee a exactement un agent admissible."""
        for tache in self._taches:
            candidates = [
                self._affectation[(tache.identifiant, identifiant)]
                for identifiant in sorted(tache.agents_admissibles)
                if (tache.identifiant, identifiant) in self._affectation
            ]
            if not candidates:
                self._modele.Add(self._planifiee[tache.identifiant] == 0)
                continue
            self._modele.Add(sum(candidates) == self._planifiee[tache.identifiant])

    def _contraindre_non_recouvrement(self) -> None:
        """Un agent ne traite qu'une tache a la fois.

        La contrainte de non-recouvrement est appliquee a l'ensemble des
        intervalles d'un meme agent, son propagateur traitant les conflits
        temporels globalement.
        """
        for identifiant_agent in self._agents:
            intervalles = [
                intervalle
                for (_, agent), intervalle in self._intervalles.items()
                if agent == identifiant_agent
            ]
            if intervalles:
                self._modele.AddNoOverlap(intervalles)

    def _contraindre_achevement(self) -> None:
        """Borne l'instant d'achevement du service par la fin de chaque tache.

        Un critere unique d'achevement evite qu'une somme d'heures de fin, dont
        l'echelle est celle des minutes, n'ecrase les preferences exprimees en
        points.
        """
        for tache in self._taches:
            self._modele.Add(
                self._achevement >= self._fins[tache.identifiant]
            ).OnlyEnforceIf(self._planifiee[tache.identifiant])

    def _contraindre_echeances(self) -> None:
        """Une tache sous echeance planifiee doit s'achever avant celle-ci."""
        for tache in self._taches:
            if tache.echeance_minutes is None:
                continue
            self._modele.Add(
                self._fins[tache.identifiant] <= tache.echeance_minutes
            ).OnlyEnforceIf(self._planifiee[tache.identifiant])

    def _evaluer(self) -> None:
        """Declare la fonction d'evaluation ponderant les preferences souples."""
        termes: list[Any] = []

        for tache in self._taches:
            penalite = self._poids.get("tache_non_planifiee", 1000)
            penalite += self._penalite_de_priorite(tache.priorite)
            termes.append(penalite * (1 - self._planifiee[tache.identifiant]))

            for identifiant_agent in sorted(tache.agents_admissibles):
                cle = (tache.identifiant, identifiant_agent)
                agent = self._agents.get(identifiant_agent)
                if agent is None or cle not in self._affectation:
                    continue
                if tache.secteur and agent.secteur and tache.secteur != agent.secteur:
                    termes.append(
                        self._poids.get("hors_secteur", 20) * self._affectation[cle]
                    )

        termes.append(self._poids.get("duree_de_service", 1) * self._achevement)

        self._modele.Minimize(sum(termes))

    def _penalite_de_priorite(self, priorite: int) -> int:
        if priorite >= 3:
            return self._poids.get("priorite_urgente", 500)
        if priorite == 2:
            return self._poids.get("priorite_elevee", 100)
        return 0

    def lire(self, solveur: Any) -> tuple[list[TachePlanifiee], set[str]]:
        """Extrait l'ordonnancement retenu de la solution du solveur."""
        planifiees: list[TachePlanifiee] = []
        non_planifiees: set[str] = set()

        for tache in self._taches:
            if not solveur.Value(self._planifiee[tache.identifiant]):
                non_planifiees.add(tache.identifiant)
                continue
            for identifiant_agent in sorted(tache.agents_admissibles):
                cle = (tache.identifiant, identifiant_agent)
                if cle not in self._affectation:
                    continue
                if solveur.Value(self._affectation[cle]):
                    planifiees.append(
                        TachePlanifiee(
                            tache=tache.identifiant,
                            agent=identifiant_agent,
                            debut_minutes=solveur.Value(self._debuts[tache.identifiant]),
                            fin_minutes=solveur.Value(self._fins[tache.identifiant]),
                        )
                    )
                    break

        return planifiees, non_planifiees


def ordonnancer(
    taches: Sequence[TacheAOrdonnancer],
    agents: Sequence[AgentDisponible],
    poids: Mapping[str, int] | None = None,
    temps_maximal: float = TEMPS_DE_CALCUL_PAR_DEFAUT,
) -> Ordonnancement:
    """Calcule un ordonnancement des taches sur les agents disponibles.

    Le temps de calcul est borne. En cas de depassement, la meilleure solution
    etablie a cet instant est restituee, l'optimalite n'etant alors pas
    garantie.
    """
    if not taches:
        return Ordonnancement(optimal=True)

    construction = _ModeleOrdonnancement(taches, agents, poids or POIDS_PAR_DEFAUT)
    modele = construction.construire()

    solveur: Any = cp_model.CpSolver()
    solveur.parameters.max_time_in_seconds = temps_maximal
    solveur.parameters.num_search_workers = 4

    statut = solveur.Solve(modele)

    if statut not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        if statut == cp_model.INFEASIBLE:
            logger.info("aucun ordonnancement admissible pour la situation soumise")
            return Ordonnancement(
                non_planifiees=frozenset(tache.identifiant for tache in taches)
            )
        raise OrdonnancementImpossibleError(
            f"le solveur d'ordonnancement a echoue: statut {statut}"
        )

    planifiees, non_planifiees = construction.lire(solveur)
    interrompu = statut == cp_model.FEASIBLE

    if interrompu:
        logger.warning(
            "temps de calcul depasse apres %.1f s, optimalite non garantie",
            temps_maximal,
        )

    logger.debug(
        "ordonnancement acheve: %d planifiees, %d non planifiees",
        len(planifiees),
        len(non_planifiees),
    )
    return Ordonnancement(
        planifiees=tuple(sorted(planifiees, key=lambda p: (p.agent, p.debut_minutes))),
        non_planifiees=frozenset(non_planifiees),
        cout=int(solveur.ObjectiveValue()),
        optimal=statut == cp_model.OPTIMAL,
        interrompu=interrompu,
    )
