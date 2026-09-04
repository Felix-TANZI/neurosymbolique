"""Arbitrage des situations ou plusieurs sejours se disputent une ressource.

Un conflit d'affectation n'admet pas un traitement unique: sa nature determine
la conduite. Le module etablit d'abord cette nature, puis en tire la conduite
appropriee.

Lorsqu'aucune solution n'existe, le module ne se contente pas de le constater:
il etablit ce qu'il faudrait relacher pour qu'une solution apparaisse. Un
systeme d'aide a la decision qui se borne a signaler l'impasse laisse le
responsable sans prise; en designant la contrainte a lever, il lui restitue un
levier d'action.
"""

import logging
from dataclasses import dataclass
from datetime import date
from enum import StrEnum, unique

from sqlalchemy.orm import Session

from src.domaine import Categorie, NumeroChambre, Reservation
from src.donnees import DepotChambres, DepotReservations, EntiteIntrouvableError

from .affectation import AffecterChambre, Recommandation, demande_depuis
from .composition import SituationIncompleteError

logger = logging.getLogger(__name__)


@unique
class NatureDuConflit(StrEnum):
    """Configuration dans laquelle deux sejours se disputent une chambre."""

    ABSENT = "absent"
    AUCUN_INSTALLE = "aucun_installe"
    UN_INSTALLE = "un_installe"
    DEUX_INSTALLES = "deux_installes"
    CHEVAUCHEMENT_PARTIEL = "chevauchement_partiel"


@unique
class Relachement(StrEnum):
    """Contrainte dont la levee retablirait l'existence d'une solution."""

    CATEGORIE = "categorie"
    EQUIPEMENT = "equipement"
    PERMUTATION = "permutation"
    AUCUN = "aucun"


@dataclass(frozen=True, slots=True)
class LevierPropose:
    """Contrainte a relacher et consequence attendue de ce relachement.

    Le levier n'est pas applique: il est presente au responsable, a qui revient
    d'apprecier si le relachement propose est acceptable au regard de
    l'engagement contractuel pris envers le client.
    """

    relachement: str
    enonce: str
    chambres_ainsi_ouvertes: int = 0


@dataclass(frozen=True, slots=True)
class ArbitrageRendu:
    """Conduite etablie face a un conflit d'affectation."""

    nature: str
    chambre: str
    sejour_maintenu: str | None = None
    sejour_a_reloger: str | None = None
    motif_de_l_arbitrage: str = ""
    recommandation: Recommandation | None = None
    leviers: tuple[LevierPropose, ...] = ()
    constats: tuple[str, ...] = ()
    anomalie: bool = False

    @property
    def a_trouve_une_solution(self) -> bool:
        return self.recommandation is not None and self.recommandation.a_conclu

    @property
    def chambre_proposee(self) -> str | None:
        if self.recommandation is None:
            return None
        return self.recommandation.chambre_proposee

    @property
    def demande_une_intervention(self) -> bool:
        """Indique qu'aucune solution automatique n'existe."""
        return self.nature != NatureDuConflit.ABSENT.value and not (
            self.a_trouve_une_solution
        )


class ArbitrerUnConflit:
    """Etablit la conduite a tenir face a un conflit d'affectation."""

    def __init__(self, affectation: AffecterChambre) -> None:
        self._affectation = affectation

    def executer(
        self,
        session: Session,
        chambre: str,
        jour: date,
        temps_maximal: float | None = None,
    ) -> ArbitrageRendu:
        """Etablit la nature du conflit puis la conduite appropriee."""
        numero = self._retrouver(session, chambre)
        concurrents = self._sejours_concurrents(session, numero, jour)

        if len(concurrents) < 2:
            return ArbitrageRendu(
                nature=NatureDuConflit.ABSENT.value,
                chambre=str(numero),
                constats=(
                    f"Aucun conflit n'affecte la chambre {numero}: "
                    f"{len(concurrents)} sejour y est enregistre.",
                ),
            )

        en_conflit = _sejours_qui_se_chevauchent(concurrents)
        if not en_conflit:
            return ArbitrageRendu(
                nature=NatureDuConflit.ABSENT.value,
                chambre=str(numero),
                constats=(
                    f"Aucun conflit n'affecte la chambre {numero}. "
                    f"Les {len(concurrents)} sejours enregistres se succedent "
                    f"sans se chevaucher.",
                ),
            )

        premier, second = self._ordonner(list(en_conflit), jour)
        nature = self._qualifier(premier, second, jour)

        if nature is NatureDuConflit.DEUX_INSTALLES:
            logger.warning(
                "deux sejours installes simultanement en %s: %s et %s",
                numero,
                premier.identifiant,
                second.identifiant,
            )

        recommandation = self._reloger(session, second, numero, jour, temps_maximal)
        leviers = (
            self._etablir_les_leviers(session, second, numero, jour, premier)
            if not recommandation.a_conclu
            else ()
        )

        return ArbitrageRendu(
            nature=nature.value,
            chambre=str(numero),
            sejour_maintenu=str(premier.identifiant),
            sejour_a_reloger=str(second.identifiant),
            motif_de_l_arbitrage=self._motiver(premier, nature, jour),
            recommandation=recommandation,
            leviers=leviers,
            constats=self._constater(premier, second, nature),
            anomalie=nature is NatureDuConflit.DEUX_INSTALLES,
        )

    @staticmethod
    def _retrouver(session: Session, chambre: str) -> NumeroChambre:
        """Verifie que la chambre appartient a l'etablissement."""
        try:
            return DepotChambres(session).retrouver(NumeroChambre(chambre)).numero
        except EntiteIntrouvableError as erreur:
            raise SituationIncompleteError(
                f"la chambre {chambre} n'appartient pas a l'etablissement"
            ) from erreur

    @staticmethod
    def _sejours_concurrents(
        session: Session, chambre: NumeroChambre, jour: date
    ) -> list[Reservation]:
        """Releve les sejours affectes a la chambre et encore en cours."""
        from src.domaine import Periode

        horizon = Periode(jour, date(jour.year + 1, jour.month, jour.day))
        return [
            sejour
            for sejour in DepotReservations(session).lister_sur_periode(horizon)
            if sejour.chambre_affectee == chambre and sejour.periode.depart > jour
        ]

    @staticmethod
    def _ordonner(
        sejours: list[Reservation], jour: date
    ) -> tuple[Reservation, Reservation]:
        """Designe le sejour maintenu et celui a reloger.

        Trois criteres s'appliquent successivement. Un sejour deja commence est
        maintenu: deloger un client installe engage un demenagement, une
        compensation et une reclamation, quand deplacer une arrivee a venir
        demeure invisible pour elle. A defaut, le sejour le plus anciennement
        engage est maintenu, l'anteriorite constituant un motif opposable. A
        defaut encore, le statut de fidelite departage.
        """
        def rang(sejour: Reservation) -> tuple[int, date, int]:
            commence = sejour.periode.arrivee <= jour
            return (
                0 if commence else 1,
                sejour.periode.arrivee,
                -sejour.client.statut.value if hasattr(sejour.client, "statut") else 0,
            )

        classes = sorted(sejours, key=rang)
        return classes[0], classes[1]

    @staticmethod
    def _qualifier(
        premier: Reservation, second: Reservation, jour: date
    ) -> NatureDuConflit:
        """Etablit la configuration du conflit."""
        premier_installe = premier.periode.arrivee <= jour
        second_installe = second.periode.arrivee <= jour

        if premier_installe and second_installe:
            return NatureDuConflit.DEUX_INSTALLES
        if premier_installe or second_installe:
            return NatureDuConflit.UN_INSTALLE

        nuitees_communes = _nuitees_communes(premier, second)
        duree_minimale = min(
            (premier.periode.depart - premier.periode.arrivee).days,
            (second.periode.depart - second.periode.arrivee).days,
        )
        if 0 < nuitees_communes < duree_minimale:
            return NatureDuConflit.CHEVAUCHEMENT_PARTIEL

        return NatureDuConflit.AUCUN_INSTALLE

    def _reloger(
        self,
        session: Session,
        sejour: Reservation,
        chambre_disputee: NumeroChambre,
        jour: date,
        temps_maximal: float | None,
    ) -> Recommandation:
        """Etablit une proposition de relogement pour le sejour ecarte."""
        depot_chambres = DepotChambres(session)
        depot_reservations = DepotReservations(session)

        parc = [
            chambre
            for chambre in depot_chambres.lister()
            if chambre.numero != chambre_disputee
        ]
        occupations = [
            occupation
            for occupation in depot_reservations.lister_affectees_sur_periode(
                sejour.periode
            )
            if occupation.identifiant != sejour.identifiant
        ]

        demande = demande_depuis(
            parc, sejour.avec_chambre(None), occupations, jour=jour
        )
        return self._affectation.executer(demande, temps_maximal)

    def _etablir_les_leviers(
        self,
        session: Session,
        sejour: Reservation,
        chambre_disputee: NumeroChambre,
        jour: date,
        alternatif: Reservation,
    ) -> tuple[LevierPropose, ...]:
        """Etablit les contraintes dont la levee ouvrirait une solution.

        Chaque levier est evalue en reexecutant le raisonnement sur une demande
        allegee. Le nombre de chambres ainsi ouvertes mesure l'effet du
        relachement et permet au responsable d'apprecier ce qu'il concede.
        """
        leviers: list[LevierPropose] = []

        if sejour.exigences_obligatoires:
            sans_exigences = _sans_exigences(sejour)
            essai = self._reloger(
                session, sans_exigences, chambre_disputee, jour, 10.0
            )
            if essai.a_conclu:
                exigences = ", ".join(
                    equipement.value.replace("_", " ")
                    for equipement in sorted(
                        sejour.exigences_obligatoires, key=lambda e: e.value
                    )
                )
                leviers.append(
                    LevierPropose(
                        relachement=Relachement.EQUIPEMENT.value,
                        enonce=(
                            f"Renoncer aux equipements exiges ({exigences}) "
                            f"ouvrirait la chambre {essai.chambre_proposee}."
                        ),
                        chambres_ainsi_ouvertes=len(essai.resultat.admissibles),
                    )
                )

        if sejour.categorie_contractee is not Categorie.STANDARD:
            declasse = _declasser(sejour)
            essai = self._reloger(session, declasse, chambre_disputee, jour, 10.0)
            if essai.a_conclu:
                leviers.append(
                    LevierPropose(
                        relachement=Relachement.CATEGORIE.value,
                        enonce=(
                            f"Proposer une categorie inferieure a "
                            f"{sejour.categorie_contractee.name.lower()} "
                            f"ouvrirait la chambre {essai.chambre_proposee}."
                        ),
                        chambres_ainsi_ouvertes=len(essai.resultat.admissibles),
                    )
                )

        permutation = self._reloger(
            session, alternatif, chambre_disputee, jour, 10.0
        )
        if permutation.a_conclu:
            leviers.append(
                LevierPropose(
                    relachement=Relachement.PERMUTATION.value,
                    enonce=(
                        f"Reloger {alternatif.identifiant} plutot que "
                        f"{sejour.identifiant} permettrait de le placer en "
                        f"{permutation.chambre_proposee}."
                    ),
                    chambres_ainsi_ouvertes=len(permutation.resultat.admissibles),
                )
            )

        if not leviers:
            leviers.append(
                LevierPropose(
                    relachement=Relachement.AUCUN.value,
                    enonce=(
                        "Aucun relachement de contrainte n'ouvre de solution: "
                        "l'etablissement est sature sur cette periode."
                    ),
                )
            )

        return tuple(leviers)

    @staticmethod
    def _motiver(
        premier: Reservation,
        nature: NatureDuConflit,
        jour: date,
    ) -> str:
        """Formule le motif de l'arbitrage rendu."""
        if nature is NatureDuConflit.DEUX_INSTALLES:
            return (
                f"Les deux clients sont installes, ce qui constitue une "
                f"anomalie. {premier.identifiant} est maintenu au titre de "
                f"l'anteriorite de son arrivee, le {premier.periode.arrivee}."
            )
        if premier.periode.arrivee <= jour:
            return (
                f"{premier.identifiant} est deja installe: le deloger "
                f"engagerait un demenagement et une compensation."
            )
        return (
            f"{premier.identifiant} est maintenu au titre de l'anteriorite de "
            f"son engagement, arrivee prevue le {premier.periode.arrivee}."
        )

    @staticmethod
    def _constater(
        premier: Reservation,
        second: Reservation,
        nature: NatureDuConflit,
    ) -> tuple[str, ...]:
        """Formule les constats etablis sur la situation."""
        enonces = [
            f"Deux sejours sont affectes a la meme chambre: "
            f"{premier.identifiant} et {second.identifiant}.",
        ]

        communes = _nuitees_communes(premier, second)
        if nature is NatureDuConflit.CHEVAUCHEMENT_PARTIEL:
            enonces.append(
                f"Le conflit ne porte que sur {communes} nuitees: un relogement "
                f"partiel demeure envisageable."
            )
        else:
            enonces.append(f"Les sejours se chevauchent sur {communes} nuitees.")

        if nature is NatureDuConflit.DEUX_INSTALLES:
            enonces.append(
                "Anomalie: deux clients occupent simultanement la chambre. "
                "La situation appelle une verification immediate."
            )

        return tuple(enonces)


def _nuitees_communes(premier: Reservation, second: Reservation) -> int:
    """Denombre les nuitees sur lesquelles deux sejours se chevauchent."""
    debut = max(premier.periode.arrivee, second.periode.arrivee)
    fin = min(premier.periode.depart, second.periode.depart)
    return max(0, (fin - debut).days)


def _sejours_qui_se_chevauchent(
    sejours: list[Reservation],
) -> tuple[Reservation, ...]:
    """Retient les sejours dont les periodes se recouvrent effectivement.

    Plusieurs sejours affectes a une meme chambre ne constituent un conflit que
    s'ils s'y trouvent simultanement. Des sejours qui se succedent decrivent la
    rotation normale d'une chambre, et les traiter comme un conflit relogerait
    un client sans motif.
    """
    for rang, premier in enumerate(sejours):
        for second in sejours[rang + 1 :]:
            if _nuitees_communes(premier, second) > 0:
                return (premier, second)
    return ()


def _sans_exigences(sejour: Reservation) -> Reservation:
    """Restitue le sejour prive de ses exigences obligatoires.

    Les exigences souhaitees sont conservees: elles n'ecartent aucune chambre
    et continuent d'orienter le choix vers la meilleure option restante.
    """
    from dataclasses import replace

    return replace(
        sejour,
        exigences=frozenset(
            exigence for exigence in sejour.exigences if not exigence.obligatoire
        ),
        chambre_affectee=None,
    )


def _declasser(sejour: Reservation) -> Reservation:
    """Restitue le sejour ramene a la categorie immediatement inferieure."""
    from dataclasses import replace

    inferieures = {
        Categorie.SUITE: Categorie.JUNIOR_SUITE,
        Categorie.JUNIOR_SUITE: Categorie.SUPERIEURE,
        Categorie.SUPERIEURE: Categorie.STANDARD,
    }
    return replace(
        sejour,
        categorie_contractee=inferieures.get(
            sejour.categorie_contractee, Categorie.STANDARD
        ),
        chambre_affectee=None,
    )
