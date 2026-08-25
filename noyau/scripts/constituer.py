"""Constitution d'un etablissement de reference dans la base.

Le script lit un profil, engendre l'etablissement correspondant et le persiste.
Il constitue un outil d'administration et non un composant du systeme: le
noyau de raisonnement demeure ignorant de son existence.

Emploi:
    python -m scripts.constituer --profil urbain
    python -m scripts.constituer --profil tendu --jour 2026-08-12
    python -m scripts.constituer --lister
    python -m scripts.constituer --profil resort --simuler
"""

import argparse
import logging
import sys
import tomllib
from datetime import date, time
from pathlib import Path
from typing import Any

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from src.donnees import (
    BaseIndisponibleError,
    DepotAgents,
    DepotChambres,
    DepotIncidents,
    DepotReservations,
    DepotSecteurs,
    DepotTaches,
    Etablissement,
    ProfilDEtablissement,
    ValeurDeProfilInvalideError,
    adresse_configuree,
    creer_fabrique_de_sessions,
    creer_moteur,
    engendrer_etablissement,
    reinitialiser_schema,
    session_de_travail,
)

RACINE_PROFILS = Path(__file__).resolve().parents[2] / "simulation" / "profils"

logger = logging.getLogger("constitution")


class ProfilIntrouvableError(FileNotFoundError):
    """Signale l'absence du profil demande."""


def lister_profils() -> list[str]:
    """Restitue les profils disponibles, par ordre alphabetique."""
    if not RACINE_PROFILS.is_dir():
        return []
    return sorted(chemin.stem for chemin in RACINE_PROFILS.glob("*.toml"))


def charger_profil(reference: str) -> ProfilDEtablissement:
    """Lit un profil et le convertit en parametres de generation."""
    chemin = RACINE_PROFILS / f"{reference}.toml"
    if not chemin.is_file():
        disponibles = ", ".join(lister_profils()) or "aucun"
        raise ProfilIntrouvableError(
            f"profil introuvable: {reference}. Profils disponibles: {disponibles}"
        )

    contenu: dict[str, Any] = tomllib.loads(chemin.read_text(encoding="utf-8"))
    parametres: dict[str, Any] = {
        cle: valeur
        for cle, valeur in contenu.items()
        if cle not in ("description", "heure_de_reference")
    }

    heure = contenu.get("heure_de_reference")
    if isinstance(heure, str):
        heures, minutes = heure.split(":")
        parametres["heure_de_reference"] = time(int(heures), int(minutes))

    try:
        return ProfilDEtablissement(**parametres)
    except (TypeError, ValeurDeProfilInvalideError) as erreur:
        raise ValeurDeProfilInvalideError(
            f"profil {reference} inexploitable: {erreur}"
        ) from erreur


def persister(etablissement: Etablissement, moteur: Engine) -> dict[str, int]:
    """Enregistre un etablissement complet et restitue le denombrement.

    Les chambres sont enregistrees en premier: les sejours, incidents et taches
    y font reference, et l'integrite referentielle rejetterait un ordre
    different.
    """
    reinitialiser_schema(moteur)
    fabrique = creer_fabrique_de_sessions(moteur)

    with session_de_travail(fabrique) as session:
        DepotChambres(session).enregistrer_plusieurs(etablissement.parc)
        session.flush()

        depot_reservations = DepotReservations(session)
        for reservation in etablissement.reservations:
            depot_reservations.enregistrer(reservation)
        session.flush()

        DepotIncidents(session).enregistrer_plusieurs(etablissement.incidents)
        DepotAgents(session).enregistrer_plusieurs(etablissement.agents)
        session.flush()
        DepotTaches(session).enregistrer_plusieurs(etablissement.taches)
        DepotSecteurs(session).declarer_reserves(etablissement.secteurs_reserves)

    with session_de_travail(fabrique) as session:
        return {
            "chambres": DepotChambres(session).denombrer(),
            "reservations": DepotReservations(session).denombrer(),
            "agents": len(DepotAgents(session).lister()),
            "taches": len(DepotTaches(session).lister_a_planifier()),
            "incidents": len(DepotIncidents(session).lister_ouverts()),
        }


def restituer(titre: str, mesures: dict[str, int]) -> None:
    """Affiche un denombrement sous forme lisible."""
    print(f"\n{titre}")
    largeur = max(len(cle) for cle in mesures)
    for cle, valeur in mesures.items():
        print(f"  {cle.ljust(largeur)}  {valeur:>6}")


def construire_analyseur() -> argparse.ArgumentParser:
    """Declare les options acceptees par le script."""
    analyseur = argparse.ArgumentParser(
        prog="constituer",
        description="Constitue un etablissement de reference dans la base.",
    )
    analyseur.add_argument(
        "--profil",
        help="Reference du profil a employer, sans extension.",
    )
    analyseur.add_argument(
        "--jour",
        help="Jour de reference au format AAAA-MM-JJ. Aujourd'hui par defaut.",
    )
    analyseur.add_argument(
        "--base",
        help="Adresse de la base. Celle configuree par defaut.",
    )
    analyseur.add_argument(
        "--lister",
        action="store_true",
        help="Affiche les profils disponibles et s'arrete.",
    )
    analyseur.add_argument(
        "--simuler",
        action="store_true",
        help="Engendre l'etablissement et affiche son resume sans rien persister.",
    )
    return analyseur


def executer(arguments: argparse.Namespace) -> int:
    """Execute l'action demandee et restitue le code de sortie."""
    if arguments.lister:
        profils = lister_profils()
        if not profils:
            print(f"Aucun profil sous {RACINE_PROFILS}.")
            return 1
        print("Profils disponibles:")
        for reference in profils:
            print(f"  {reference}")
        return 0

    if not arguments.profil:
        print("Precisez un profil avec --profil, ou employez --lister.")
        return 1

    try:
        profil = charger_profil(arguments.profil)
    except (ProfilIntrouvableError, ValeurDeProfilInvalideError) as erreur:
        print(f"Erreur: {erreur}")
        return 1

    jour = date.fromisoformat(arguments.jour) if arguments.jour else date.today()
    etablissement = engendrer_etablissement(profil, jour)

    if arguments.simuler:
        restituer(
            f"Etablissement engendre: {profil.nom} (non persiste)",
            etablissement.resumer(),
        )
        return 0

    adresse = arguments.base or adresse_configuree()
    try:
        moteur = creer_moteur(adresse)
    except BaseIndisponibleError as erreur:
        print(f"Erreur: {erreur}")
        return 1

    try:
        mesures = persister(etablissement, moteur)
    except SQLAlchemyError as erreur:
        print(f"Erreur: la base {adresse} n'a pu etre constituee.")
        logger.debug("defaillance de persistance", exc_info=erreur)
        return 1
    finally:
        moteur.dispose()

    restituer(f"Etablissement constitue: {profil.nom}", mesures)
    print(f"\nBase: {adresse}")
    print(f"Jour de reference: {jour.isoformat()}")
    return 0


def main() -> int:
    """Point d'entree du script."""
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s"
    )
    return executer(construire_analyseur().parse_args())


if __name__ == "__main__":
    sys.exit(main())