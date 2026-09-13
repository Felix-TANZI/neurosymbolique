"""Essai de l'affectation des interventions de maintenance.

Le script soumet les interventions en attente aux techniciens disponibles et
restitue le plan etabli, avec ce qui le motive et ce qui demeure sans solution.

Emploi:
    python -m scripts.essayer_maintenance
"""

import logging
import sys

from src.domaine.maintenance import Criticite
from src.donnees import (
    DepotInterventions,
    DepotTechniciens,
    creer_fabrique_de_sessions,
    creer_moteur,
    session_de_travail,
)
from src.orchestration.maintenance import AffecterLesInterventions


def main() -> int:
    """Etablit le plan d'intervention et le restitue."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stdout)

    moteur = creer_moteur()
    fabrique = creer_fabrique_de_sessions(moteur)

    try:
        with session_de_travail(fabrique) as session:
            interventions = list(DepotInterventions(session).lister())
            techniciens = list(DepotTechniciens(session).lister())
    finally:
        moteur.dispose()

    print(f"\n  {len(interventions)} interventions, {len(techniciens)} techniciens")

    for technicien in techniciens:
        competences = ", ".join(
            sorted(competence.value for competence in technicien.competences)
        )
        etat = "disponible" if technicien.disponible else "indisponible"
        print(
            f"    {technicien.identifiant}  {etat:<13} charge "
            f"{technicien.charge_en_cours}  {competences}"
        )

    plan = AffecterLesInterventions().executer(interventions, techniciens)

    print()
    for enonce in plan.justification:
        print(f"  {enonce}")

    if plan.affectees:
        print("\n  Affectations:")
        for affectee in plan.affectees:
            intervention = affectee.intervention
            print(
                f"    {affectee.rang}. {intervention.identifiant} sur "
                f"{intervention.objet} "
                f"({Criticite(intervention.criticite).name.lower()})"
            )
            print(f"       {affectee.motif}")

    if plan.en_attente:
        print("\n  En attente:")
        for manquee in plan.en_attente:
            print(
                f"    {manquee.intervention.identifiant}: {manquee.cause}"
                + (f" ({manquee.detail})" if manquee.detail else "")
            )

    repartition = plan.par_technicien()
    if repartition:
        print("\n  Repartition:")
        for reference, interventions_confiees in repartition.items():
            print(f"    {reference}: {', '.join(interventions_confiees)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
