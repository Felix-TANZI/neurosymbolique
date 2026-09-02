"""Interpretation d'un enonce et verification de ses elements.

Le module realise le principe directeur du systeme sur la couche neuronale: le
modele propose une interpretation, la verification symbolique en etablit la
recevabilite. Une entite extraite qui ne correspond a rien de reel est
signalee plutot qu'employee: raisonner sur une reference inexistante
produirait une conclusion sans fondement, alors meme qu'elle paraitrait
etablie.

Aucune interpretation n'est appliquee directement. Celles dont la confiance
est insuffisante ou dont une entite demeure incertaine sont soumises a
confirmation, conformement au principe qu'une decision critique ne repose
jamais sur une inference non verifiee.
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum, unique

import torch
from torch import Tensor

from .modele import InterpreteDEnonces
from .taxonomie import (
    ENTITES_ATTENDUES,
    ETIQUETTE_HORS_ENTITE,
    Intention,
    TypeDEntite,
    etiquettes_bio,
)
from .tokeniseur import Tokeniseur, segmenter

logger = logging.getLogger(__name__)

CONFIANCE_MINIMALE = 0.70
CONFIANCE_ELEVEE = 0.90


@unique
class Recevabilite(StrEnum):
    """Suite reservee a une interpretation."""

    RECEVABLE = "recevable"
    A_CONFIRMER = "a_confirmer"
    IRRECEVABLE = "irrecevable"


@unique
class MotifDeReserve(StrEnum):
    """Raison pour laquelle une interpretation n'est pas directement recevable."""

    CONFIANCE_INSUFFISANTE = "confiance_insuffisante"
    ENTITE_INEXISTANTE = "entite_inexistante"
    ENTITE_MANQUANTE = "entite_manquante"
    HORS_PERIMETRE = "hors_perimetre"


@dataclass(frozen=True, slots=True)
class EntiteExtraite:
    """Element reconnu dans un enonce, avec sa confiance et son existence."""

    type_d_entite: str
    valeur: str
    confiance: float
    debut: int
    fin: int
    existe: bool | None = None

    @property
    def est_verifiee(self) -> bool:
        """Indique que l'entite a ete confrontee a l'etat de l'etablissement."""
        return self.existe is not None

    def __str__(self) -> str:
        return f"{self.type_d_entite}={self.valeur}"


@dataclass(frozen=True, slots=True)
class Reserve:
    """Motif pour lequel une interpretation appelle une confirmation."""

    motif: str
    detail: str = ""

    def __str__(self) -> str:
        return f"{self.motif}({self.detail})" if self.detail else self.motif


@dataclass(frozen=True, slots=True)
class Interpretation:
    """Lecture d'un enonce, avec sa confiance et sa recevabilite.

    L'interpretation n'est jamais une decision: elle etablit ce que l'enonce
    exprime, a charge pour la couche symbolique d'en tirer les consequences.
    """

    enonce: str
    intention: str
    confiance_d_intention: float
    entites: tuple[EntiteExtraite, ...] = ()
    reserves: tuple[Reserve, ...] = ()
    recevabilite: str = Recevabilite.RECEVABLE.value

    @property
    def est_recevable(self) -> bool:
        return self.recevabilite == Recevabilite.RECEVABLE.value

    @property
    def appelle_confirmation(self) -> bool:
        return self.recevabilite == Recevabilite.A_CONFIRMER.value

    def valeur_de(self, type_d_entite: str) -> str | None:
        """Restitue la valeur de la premiere entite d'un type donne."""
        for entite in self.entites:
            if entite.type_d_entite == type_d_entite:
                return entite.valeur
        return None

    def valeurs_de(self, type_d_entite: str) -> tuple[str, ...]:
        """Restitue les valeurs de toutes les entites d'un type donne."""
        return tuple(
            entite.valeur
            for entite in self.entites
            if entite.type_d_entite == type_d_entite
        )


class Interprete:
    """Applique le modele a un enonce et en restitue la lecture."""

    def __init__(
        self,
        modele: InterpreteDEnonces,
        tokeniseur: Tokeniseur,
        confiance_minimale: float = CONFIANCE_MINIMALE,
    ) -> None:
        self._modele = modele
        self._tokeniseur = tokeniseur
        self._confiance_minimale = confiance_minimale
        self._intentions = list(Intention)
        self._etiquettes = etiquettes_bio()
        self._modele.eval()

    def interpreter(self, enonce: str) -> Interpretation:
        """Etablit l'intention et les entites d'un enonce.

        La confiance restituee est la probabilite attribuee par le modele a la
        classe retenue. Elle n'est pas une garantie d'exactitude, mais une
        mesure d'assurance: une confiance faible signale une lecture que le
        modele lui-meme ne tient pas pour assuree.
        """
        jetons = segmenter(enonce)
        if not jetons:
            return Interpretation(
                enonce=enonce,
                intention="",
                confiance_d_intention=0.0,
                reserves=(Reserve(MotifDeReserve.HORS_PERIMETRE.value, "enonce vide"),),
                recevabilite=Recevabilite.IRRECEVABLE.value,
            )

        encode = self._tokeniseur.encoder(jetons)
        indices = torch.tensor([encode.indices], dtype=torch.long)
        masque = torch.tensor([encode.masque], dtype=torch.long)

        with torch.no_grad():
            sortie = self._modele(indices, masque)

        intention, confiance = self._lire_intention(sortie.scores_d_intention[0])
        entites = self._lire_entites(
            sortie.scores_d_etiquettes[0], encode.jetons, sum(encode.masque)
        )

        return self._qualifier(
            Interpretation(
                enonce=enonce,
                intention=intention,
                confiance_d_intention=confiance,
                entites=entites,
            )
        )

    def _lire_intention(self, scores: Tensor) -> tuple[str, float]:
        """Retient l'intention la plus probable et sa confiance."""
        probabilites = torch.softmax(scores, dim=-1)
        confiance, rang = probabilites.max(dim=-1)
        return self._intentions[int(rang.item())].value, float(confiance.item())

    def _lire_entites(
        self, scores: Tensor, jetons: Sequence[str], longueur_utile: int
    ) -> tuple[EntiteExtraite, ...]:
        """Assemble les jetons etiquetes en entites completes.

        Une etiquette de continuation isolee est traitee comme une ouverture:
        le modele peut produire une suite invalide, et rejeter l'entite
        entiere priverait le systeme d'une information partiellement correcte.
        """
        probabilites = torch.softmax(scores, dim=-1)
        confiances, rangs = probabilites.max(dim=-1)

        extraites: list[EntiteExtraite] = []
        courants: list[str] = []
        confiances_courantes: list[float] = []
        type_courant = ""
        debut = 0

        for position in range(1, longueur_utile):
            etiquette = self._etiquettes[int(rangs[position].item())]
            jeton = jetons[position]
            confiance = float(confiances[position].item())

            if etiquette == ETIQUETTE_HORS_ENTITE:
                if courants:
                    extraites.append(
                        self._assembler(
                            type_courant, courants, confiances_courantes, debut, position
                        )
                    )
                    courants, confiances_courantes, type_courant = [], [], ""
                continue

            type_annonce = etiquette[2:]
            ouverture = etiquette.startswith("B-") or type_annonce != type_courant

            if ouverture and courants:
                extraites.append(
                    self._assembler(
                        type_courant, courants, confiances_courantes, debut, position
                    )
                )
                courants, confiances_courantes = [], []

            if ouverture:
                debut = position
                type_courant = type_annonce

            courants.append(jeton)
            confiances_courantes.append(confiance)

        if courants:
            extraites.append(
                self._assembler(
                    type_courant, courants, confiances_courantes, debut, longueur_utile
                )
            )

        return tuple(extraites)

    @staticmethod
    def _assembler(
        type_d_entite: str,
        jetons: Sequence[str],
        confiances: Sequence[float],
        debut: int,
        fin: int,
    ) -> EntiteExtraite:
        """Constitue une entite a partir de ses jetons.

        Les jetons purement numeriques sont recolles sans espace: un numero de
        chambre segmente en chiffres doit etre restitue sous sa forme d'usage.
        """
        valeur = (
            "".join(jetons)
            if all(jeton.isdigit() for jeton in jetons)
            else " ".join(jetons)
        )
        return EntiteExtraite(
            type_d_entite=type_d_entite,
            valeur=valeur,
            confiance=min(confiances) if confiances else 0.0,
            debut=debut,
            fin=fin,
        )

    def _qualifier(self, interpretation: Interpretation) -> Interpretation:
        """Etablit la recevabilite au regard de la confiance et des attentes."""
        reserves: list[Reserve] = []

        if interpretation.confiance_d_intention < self._confiance_minimale:
            reserves.append(
                Reserve(
                    MotifDeReserve.CONFIANCE_INSUFFISANTE.value,
                    f"{interpretation.confiance_d_intention:.2f}",
                )
            )

        attendues = ENTITES_ATTENDUES.get(Intention(interpretation.intention), frozenset())
        obtenues = {entite.type_d_entite for entite in interpretation.entites}
        essentielle = entite_essentielle(attendues)

        if essentielle is not None and essentielle.value not in obtenues:
            reserves.append(
                Reserve(MotifDeReserve.ENTITE_MANQUANTE.value, essentielle.value)
            )

        return Interpretation(
            enonce=interpretation.enonce,
            intention=interpretation.intention,
            confiance_d_intention=interpretation.confiance_d_intention,
            entites=interpretation.entites,
            reserves=tuple(reserves),
            recevabilite=(
                Recevabilite.RECEVABLE.value
                if not reserves
                else Recevabilite.A_CONFIRMER.value
            ),
        )


def entite_essentielle(attendues: frozenset[TypeDEntite]) -> TypeDEntite | None:
    """Designe l'entite sans laquelle l'intention demeure inexploitable.

    Une intention portant sur une chambre est inexploitable si la chambre
    demeure inconnue; les autres entites precisent la situation sans la
    conditionner.
    """
    for essentielle in (
        TypeDEntite.CHAMBRE,
        TypeDEntite.RESERVATION,
        TypeDEntite.AGENT,
        TypeDEntite.SECTEUR,
    ):
        if essentielle in attendues:
            return essentielle
    return None


@dataclass(frozen=True, slots=True)
class ReferentielConnu:
    """References effectivement presentes dans l'etablissement.

    Le referentiel constitue l'autorite face aux extractions du modele: une
    reference absente n'existe pas, quelle que soit la confiance du modele.
    """

    chambres: frozenset[str] = field(default_factory=frozenset)
    reservations: frozenset[str] = field(default_factory=frozenset)
    agents: frozenset[str] = field(default_factory=frozenset)
    secteurs: frozenset[str] = field(default_factory=frozenset)

    def references_de(self, type_d_entite: str) -> frozenset[str] | None:
        """Restitue les references connues d'un type, ou rien si non verifiable."""
        correspondances = {
            TypeDEntite.CHAMBRE.value: self.chambres,
            TypeDEntite.RESERVATION.value: self.reservations,
            TypeDEntite.AGENT.value: self.agents,
            TypeDEntite.SECTEUR.value: self.secteurs,
        }
        return correspondances.get(type_d_entite)


def _normaliser(valeur: str) -> str:
    """Ramene une reference a une forme comparable."""
    return valeur.replace(" ", "").replace("-", "").replace("_", "").lower()


def verifier_les_entites(
    interpretation: Interpretation, referentiel: ReferentielConnu
) -> Interpretation:
    """Confronte les entites extraites aux references de l'etablissement.

    La verification est le mecanisme par lequel la couche symbolique dispose de
    ce que la couche neuronale propose: une extraction plausible mais sans
    correspondance reelle est ecartee, ce qui interdit qu'un raisonnement
    s'engage sur une reference inventee.

    Les entites dont le type ne designe aucune reference, telle une
    localisation, demeurent non verifiees: leur exactitude ne conditionne pas
    la validite du raisonnement.
    """
    verifiees: list[EntiteExtraite] = []
    reserves = list(interpretation.reserves)

    for entite in interpretation.entites:
        connues = referentiel.references_de(entite.type_d_entite)
        if connues is None:
            verifiees.append(entite)
            continue

        correspondance = _retrouver(entite.valeur, connues)
        existe = correspondance is not None
        verifiees.append(
            EntiteExtraite(
                type_d_entite=entite.type_d_entite,
                valeur=correspondance or entite.valeur,
                confiance=entite.confiance,
                debut=entite.debut,
                fin=entite.fin,
                existe=existe,
            )
        )

        if not existe:
            reserves.append(
                Reserve(
                    MotifDeReserve.ENTITE_INEXISTANTE.value,
                    f"{entite.type_d_entite}={entite.valeur}",
                )
            )
            logger.info(
                "entite extraite sans correspondance reelle: %s=%s",
                entite.type_d_entite,
                entite.valeur,
            )

    return Interpretation(
        enonce=interpretation.enonce,
        intention=interpretation.intention,
        confiance_d_intention=interpretation.confiance_d_intention,
        entites=tuple(verifiees),
        reserves=tuple(reserves),
        recevabilite=(
            Recevabilite.RECEVABLE.value
            if not reserves
            else Recevabilite.A_CONFIRMER.value
        ),
    )


def _retrouver(valeur: str, connues: frozenset[str]) -> str | None:
    """Retrouve la reference reelle correspondant a une valeur extraite.

    La comparaison ignore les separateurs et la casse: un enonce mentionne une
    reference sous une forme abregee que le referentiel enregistre autrement.
    """
    recherchee = _normaliser(valeur)
    for reference in connues:
        if _normaliser(reference) == recherchee:
            return reference
    return None


def referentiel_depuis(
    chambres: Sequence[str],
    reservations: Sequence[str] = (),
    agents: Sequence[str] = (),
    secteurs: Sequence[str] = (),
) -> ReferentielConnu:
    """Constitue un referentiel a partir des references de l'etablissement."""
    return ReferentielConnu(
        chambres=frozenset(chambres),
        reservations=frozenset(reservations),
        agents=frozenset(agents),
        secteurs=frozenset(secteurs),
    )


def resumer(interpretation: Interpretation) -> Mapping[str, object]:
    """Restitue une interpretation sous une forme lisible."""
    return {
        "enonce": interpretation.enonce,
        "intention": interpretation.intention,
        "confiance": round(interpretation.confiance_d_intention, 4),
        "entites": {
            entite.type_d_entite: entite.valeur for entite in interpretation.entites
        },
        "recevabilite": interpretation.recevabilite,
        "reserves": [str(reserve) for reserve in interpretation.reserves],
    }
