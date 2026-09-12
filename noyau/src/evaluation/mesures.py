"""Mesures etablies sur les conduites observees.

Les mesures portent sur ce qui est verifiable. La justesse d'intention se
constate par comparaison a l'annotation. Le respect des contraintes se verifie
sur l'etat de l'etablissement. L'abstention se mesure par la coincidence entre
les situations ou le systeme se retient et celles ou il le devait.

Une mesure agregee masquerait ce que la comparaison doit reveler: les resultats
sont donc etablis par epreuve, afin d'etablir non seulement si une approche
reussit, mais ou elle echoue.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from .approches import Conduite
from .scenarios import Scenario


@dataclass(frozen=True, slots=True)
class ResultatParEpreuve:
    """Resultat d'une approche sur une epreuve donnee."""

    epreuve: str
    reussites: int
    total: int

    @property
    def taux(self) -> float:
        return self.reussites / self.total if self.total else 0.0


@dataclass(frozen=True, slots=True)
class Mesure:
    """Ensemble des resultats d'une approche."""

    approche: str
    conduites_exactes: int = 0
    intentions_exactes: int = 0
    intentions_evaluables: int = 0
    entites_exactes: int = 0
    entites_attendues: int = 0
    references_inexistantes_detectees: int = 0
    references_inexistantes: int = 0
    abstentions_justes: int = 0
    abstentions_attendues: int = 0
    abstentions_abusives: int = 0
    total: int = 0
    duree_moyenne: float = 0.0
    par_epreuve: tuple[ResultatParEpreuve, ...] = ()

    @property
    def justesse_de_conduite(self) -> float:
        return self.conduites_exactes / self.total if self.total else 0.0

    @property
    def justesse_d_intention(self) -> float:
        return (
            self.intentions_exactes / self.intentions_evaluables
            if self.intentions_evaluables
            else 0.0
        )

    @property
    def justesse_des_entites(self) -> float:
        return (
            self.entites_exactes / self.entites_attendues
            if self.entites_attendues
            else 0.0
        )

    @property
    def detection_des_references(self) -> float:
        """Part des references inexistantes effectivement signalees."""
        return (
            self.references_inexistantes_detectees / self.references_inexistantes
            if self.references_inexistantes
            else 0.0
        )

    @property
    def justesse_de_l_abstention(self) -> float:
        """Part des situations ou le systeme se retient a bon escient."""
        return (
            self.abstentions_justes / self.abstentions_attendues
            if self.abstentions_attendues
            else 0.0
        )


def mesurer(
    approche: str, scenarios: Sequence[Scenario], conduites: Sequence[Conduite]
) -> Mesure:
    """Confronte les conduites observees aux conduites attendues."""
    par_identifiant = {conduite.scenario: conduite for conduite in conduites}

    conduites_exactes = 0
    intentions_exactes = 0
    intentions_evaluables = 0
    entites_exactes = 0
    entites_attendues = 0
    references_detectees = 0
    references = 0
    abstentions_justes = 0
    abstentions_attendues = 0
    abstentions_abusives = 0
    durees: list[float] = []
    reussites_par_epreuve: dict[str, list[int]] = {}

    for scenario in scenarios:
        conduite = par_identifiant.get(scenario.identifiant)
        if conduite is None:
            continue

        durees.append(conduite.duree_millisecondes)
        exacte = conduite.conduite == scenario.conduite
        conduites_exactes += int(exacte)
        reussites_par_epreuve.setdefault(scenario.epreuve, []).append(int(exacte))

        if scenario.intention_attendue:
            intentions_evaluables += 1
            intentions_exactes += int(
                conduite.intention == scenario.intention_attendue
            )

        for type_attendu, valeur_attendue in scenario.entites_attendues.items():
            entites_attendues += 1
            entites_exactes += int(
                conduite.entites.get(type_attendu) == valeur_attendue
            )

        if scenario.conduite == "signaler_inexistant":
            references += 1
            references_detectees += int(exacte)

        if scenario.conduite in {"refuser_hors_perimetre", "demander_confirmation"}:
            abstentions_attendues += 1
            abstentions_justes += int(exacte)
        elif conduite.conduite in {
            "refuser_hors_perimetre",
            "demander_confirmation",
        }:
            abstentions_abusives += 1

    return Mesure(
        approche=approche,
        conduites_exactes=conduites_exactes,
        intentions_exactes=intentions_exactes,
        intentions_evaluables=intentions_evaluables,
        entites_exactes=entites_exactes,
        entites_attendues=entites_attendues,
        references_inexistantes_detectees=references_detectees,
        references_inexistantes=references,
        abstentions_justes=abstentions_justes,
        abstentions_attendues=abstentions_attendues,
        abstentions_abusives=abstentions_abusives,
        total=len(scenarios),
        duree_moyenne=sum(durees) / len(durees) if durees else 0.0,
        par_epreuve=tuple(
            ResultatParEpreuve(
                epreuve=epreuve,
                reussites=sum(resultats),
                total=len(resultats),
            )
            for epreuve, resultats in sorted(reussites_par_epreuve.items())
        ),
    )
