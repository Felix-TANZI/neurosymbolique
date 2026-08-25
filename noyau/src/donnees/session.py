"""Configuration de l'acces a la base et gestion des sessions.

Le dialecte est determine par une variable d'environnement. Un fichier local
est employe par defaut, ce qui permet d'executer et de demontrer le systeme
sans installation prealable; un serveur peut lui etre substitue en
deploiement sans modification du code.
"""

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .modeles import Base

logger = logging.getLogger(__name__)

VARIABLE_ADRESSE = "NEURO_BASE_DE_DONNEES"
RACINE_LOCALE = Path(__file__).resolve().parents[2] / "donnees_locales"
FICHIER_PAR_DEFAUT = RACINE_LOCALE / "operations.sqlite3"


class BaseIndisponibleError(RuntimeError):
    """Signale l'impossibilite d'etablir une connexion a la base."""


def adresse_configuree() -> str:
    """Restitue l'adresse de la base, celle du fichier local a defaut."""
    declaree = os.environ.get(VARIABLE_ADRESSE)
    if declaree:
        return declaree
    RACINE_LOCALE.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{FICHIER_PAR_DEFAUT}"


def _preparer_emplacement(adresse: str) -> None:
    """Cree le dossier d'accueil d'une base sur fichier.

    L'absence du dossier produirait une erreur d'ouverture peu explicite,
    survenant a la premiere connexion plutot qu'a la configuration.
    """
    if not adresse.startswith("sqlite:///") or adresse.endswith(":memory:"):
        return
    fichier = Path(adresse.removeprefix("sqlite:///"))
    fichier.parent.mkdir(parents=True, exist_ok=True)


def creer_moteur(adresse: str | None = None, tracer: bool = False) -> Engine:
    """Construit le moteur de connexion et applique ses reglages.

    Les cles etrangeres ne sont pas verifiees par defaut sur un fichier local:
    leur activation explicite garantit la meme integrite referentielle qu'un
    serveur, et evite qu'une incoherence ne se revele qu'au deploiement.
    """
    cible = adresse or adresse_configuree()
    _preparer_emplacement(cible)
    try:
        moteur = create_engine(cible, echo=tracer, future=True)
    except Exception as erreur:
        raise BaseIndisponibleError(
            f"adresse de base inexploitable: {cible}"
        ) from erreur

    if cible.startswith("sqlite"):

        @event.listens_for(moteur, "connect")
        def _activer_integrite(connexion: object, _: object) -> None:
            curseur = connexion.cursor()  # type: ignore[attr-defined]
            curseur.execute("PRAGMA foreign_keys=ON")
            curseur.execute("PRAGMA journal_mode=WAL")
            curseur.close()

    logger.info("moteur de base etabli sur %s", cible)
    return moteur


def creer_fabrique_de_sessions(moteur: Engine) -> sessionmaker[Session]:
    """Construit la fabrique de sessions associee a un moteur."""
    return sessionmaker(bind=moteur, expire_on_commit=False, future=True)


def initialiser_schema(moteur: Engine) -> None:
    """Cree les tables absentes de la base."""
    Base.metadata.create_all(moteur)
    logger.info("schema de persistance initialise")


def reinitialiser_schema(moteur: Engine) -> None:
    """Supprime puis recree l'integralite des tables.

    L'operation detruit les donnees existantes: elle est reservee a la
    constitution d'un etablissement de reference et aux tests.
    """
    Base.metadata.drop_all(moteur)
    Base.metadata.create_all(moteur)
    logger.warning("schema de persistance reinitialise, donnees effacees")


@contextmanager
def session_de_travail(fabrique: sessionmaker[Session]) -> Iterator[Session]:
    """Ouvre une session, valide en sortie et annule en cas de defaillance.

    L'annulation est systematique en cas d'erreur: une ecriture partielle
    laisserait l'etat operationnel incoherent, ce qui fausserait tout
    raisonnement ulterieur.
    """
    session = fabrique()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("session annulee a la suite d'une defaillance")
        raise
    finally:
        session.close()
