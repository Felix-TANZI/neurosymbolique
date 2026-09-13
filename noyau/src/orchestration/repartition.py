"""Repartition d'une charge de travail decrite dans l'enonce.

Le cas d'usage se distingue des autres en ce que les donnees ne proviennent pas
de l'etablissement mais de la demande elle-meme: un responsable qui demande
comment repartir douze chambres entre trois agents n'interroge pas un etat, il
soumet une situation hypothetique.

La repartition vise le temps d'achevement, non l'egalite des charges. Trois
agents traitant respectivement cinq, quatre et trois chambres achevent plus tot
que trois agents en traitant quatre chacun si les durees different: c'est
l'instant ou le dernier termine qui determine quand le service est acheve.
"""

import logging
from dataclasses import dataclass, field
from datetime import timedelta

logger = logging.getLogger(__name__)

DUREE_PAR_CHAMBRE = timedelta(minutes=30)
AGENTS_MAXIMAUX = 40
CHAMBRES_MAXIMALES = 500


class RepartitionImpossibleError(ValueError):
    """Signale une demande de repartition inexploitable."""


@dataclass(frozen=True, slots=True)
class ChargeAssignee:
    """Part de la charge confiee a un agent."""

    rang: int
    chambres: int
    duree: timedelta

    @property
    def duree_lisible(self) -> str:
        heures, reste = divmod(int(self.duree.total_seconds() // 60), 60)
        if heures and reste:
            return f"{heures} h {reste:02d}"
        if heures:
            return f"{heures} h"
        return f"{reste} min"


@dataclass(frozen=True, slots=True)
class RepartitionProposee:
    """Repartition etablie et ce qu'elle implique."""

    chambres: int
    agents: int
    parts: tuple[ChargeAssignee, ...] = ()
    duree_totale: timedelta = field(default_factory=timedelta)
    justification: tuple[str, ...] = ()

    @property
    def est_equilibree(self) -> bool:
        """Indique que tous les agents recoivent le meme nombre de chambres."""
        if not self.parts:
            return True
        comptes = {part.chambres for part in self.parts}
        return len(comptes) == 1

    @property
    def ecart_maximal(self) -> int:
        """Restitue l'ecart entre la part la plus lourde et la plus legere."""
        if not self.parts:
            return 0
        comptes = [part.chambres for part in self.parts]
        return max(comptes) - min(comptes)

    @property
    def duree_lisible(self) -> str:
        heures, reste = divmod(int(self.duree_totale.total_seconds() // 60), 60)
        if heures and reste:
            return f"{heures} h {reste:02d}"
        if heures:
            return f"{heures} h"
        return f"{reste} min"


class RepartirUneCharge:
    """Etablit la repartition d'une charge entre un effectif donne."""

    def executer(
        self,
        chambres: int,
        agents: int,
        duree_par_chambre: timedelta | None = None,
        echeance: timedelta | None = None,
    ) -> RepartitionProposee:
        """Repartit les chambres entre les agents et etablit la duree.

        La repartition est aussi egale que le permet la division: le reste est
        distribue une unite par agent, ce qui borne l'ecart a une seule chambre.
        Concentrer le reste sur un agent retarderait l'achevement d'autant.
        """
        self._verifier(chambres, agents)

        unitaire = duree_par_chambre or DUREE_PAR_CHAMBRE
        base, reste = divmod(chambres, agents)

        parts = tuple(
            ChargeAssignee(
                rang=rang,
                chambres=base + (1 if rang <= reste else 0),
                duree=unitaire * (base + (1 if rang <= reste else 0)),
            )
            for rang in range(1, agents + 1)
        )

        duree_totale = max((part.duree for part in parts), default=timedelta())

        repartition = RepartitionProposee(
            chambres=chambres,
            agents=agents,
            parts=parts,
            duree_totale=duree_totale,
            justification=self._justifier(
                chambres, agents, parts, duree_totale, unitaire, echeance
            ),
        )
        logger.info(
            "repartition de %d chambres sur %d agents: %s",
            chambres,
            agents,
            repartition.duree_lisible,
        )
        return repartition

    @staticmethod
    def _verifier(chambres: int, agents: int) -> None:
        """Verifie que la demande est exploitable.

        Les bornes ecartent les demandes qui ne decrivent aucune situation
        reelle: une repartition sur zero agent n'a pas de sens, et un nombre
        demesure revele une lecture erronee de l'enonce plutot qu'une intention.
        """
        if agents <= 0:
            raise RepartitionImpossibleError(
                "aucun agent n'est disponible pour cette repartition"
            )
        if chambres <= 0:
            raise RepartitionImpossibleError(
                "aucune chambre n'est a repartir"
            )
        if agents > AGENTS_MAXIMAUX:
            raise RepartitionImpossibleError(
                f"effectif invraisemblable: {agents} agents"
            )
        if chambres > CHAMBRES_MAXIMALES:
            raise RepartitionImpossibleError(
                f"charge invraisemblable: {chambres} chambres"
            )

    @staticmethod
    def _justifier(
        chambres: int,
        agents: int,
        parts: tuple[ChargeAssignee, ...],
        duree: timedelta,
        unitaire: timedelta,
        echeance: timedelta | None,
    ) -> tuple[str, ...]:
        """Formule la repartition et ses consequences."""
        minutes = int(unitaire.total_seconds() // 60)
        enonces = [
            f"{chambres} chambres reparties entre {agents} agents, "
            f"a raison de {minutes} minutes par chambre."
        ]

        comptes = sorted({part.chambres for part in parts}, reverse=True)
        if len(comptes) == 1:
            enonces.append(
                f"Chaque agent traite {comptes[0]} chambres."
            )
        else:
            lourds = sum(1 for part in parts if part.chambres == comptes[0])
            enonces.append(
                f"{lourds} agents traitent {comptes[0]} chambres, "
                f"les autres {comptes[-1]}."
            )

        heures, reste = divmod(int(duree.total_seconds() // 60), 60)
        lisible = (
            f"{heures} h {reste:02d}" if heures and reste
            else f"{heures} h" if heures
            else f"{reste} min"
        )
        enonces.append(
            f"Le service s'acheve au bout de {lisible}, "
            f"quand le dernier agent termine."
        )

        if echeance is not None:
            if duree <= echeance:
                marge = int((echeance - duree).total_seconds() // 60)
                enonces.append(
                    f"L'echeance est tenue, avec {marge} minutes de marge."
                )
            else:
                depassement = int((duree - echeance).total_seconds() // 60)
                agents_requis = _effectif_requis(chambres, unitaire, echeance)
                enonces.append(
                    f"L'echeance est depassee de {depassement} minutes. "
                    f"{agents_requis} agents seraient necessaires pour la tenir."
                )

        return tuple(enonces)


def _effectif_requis(
    chambres: int, unitaire: timedelta, echeance: timedelta
) -> int:
    """Etablit l'effectif permettant de tenir une echeance.

    L'indication restitue au responsable un levier: constater qu'une echeance
    ne sera pas tenue le laisse sans prise, savoir combien d'agents la
    tiendraient lui permet d'arbitrer.
    """
    par_agent = int(echeance.total_seconds() // unitaire.total_seconds())
    if par_agent <= 0:
        return chambres
    return -(-chambres // par_agent)
