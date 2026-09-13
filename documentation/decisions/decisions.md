# Décisions d'architecture

Chaque décision consigne ce qui a été retenu, ce qui a été écarté, et pourquoi.
Une décision sans alternative examinée n'en est pas une.

---

## D-01 — Programmation par ensembles-réponses pour le raisonnement

**Retenu** : Clingo, langage ASP.

**Écarté** : un moteur à règles impératif, un solveur de contraintes généraliste.

**Pourquoi.** Une décision critique doit être justifiable. ASP produit non
seulement une solution mais l'ensemble des atomes qui la fondent, ce dont la
justification se déduit. Un moteur impératif exigerait d'écrire séparément la
décision et son explication, avec le risque qu'elles divergent.

ASP distingue par ailleurs contraintes dures et préférences souples dans le
même formalisme : une chambre non conforme est écartée, une chambre moins
adaptée est pénalisée. Cette distinction est celle du métier.

**Conséquence.** Les règles sont dans `connaissances/regles/`, éditables sans
recompilation. Le vocabulaire des justifications les accompagne dans
`connaissances/explications/`.

---

## D-02 — Séparation du diagnostic et de la décision

**Retenu** : deux programmes logiques distincts.

**Écarté** : un programme unique produisant décision et motifs.

**Pourquoi.** Un programme unique sans solution ne restitue rien — ni chambre
retenue, ni raison. Or c'est précisément quand aucune solution n'existe que le
responsable a besoin de savoir pourquoi.

Le diagnostic établit les motifs de rejet indépendamment de toute décision. Il
produit donc une explication même en l'absence de solution.

**Risque encouru et parade.** Deux programmes peuvent diverger sans que rien ne
le signale. Le défaut s'est produit : le diagnostic déclarait admissible ce que
la décision refusait. Deux propriétés vérifiées par Hypothesis garantissent
désormais la concordance dans les deux sens.

---

## D-03 — CP-SAT pour l'ordonnancement, non ASP

**Retenu** : OR-Tools CP-SAT pour la planification du housekeeping.

**Écarté** : étendre les règles ASP à l'ordonnancement.

**Pourquoi.** ASP raisonne sur des ensembles finis d'atomes. Un ordonnancement
manipule des intervalles temporels, où les contraintes de non-recouvrement et
d'échéance s'expriment naturellement par variables d'intervalle. Les encoder en
ASP produirait un programme volumineux et lent.

**Conséquence.** Deux moteurs coexistent, chacun sur le type de problème qui
lui convient. La frontière est nette : affectation et arbitrage relèvent d'ASP,
ordonnancement de CP-SAT.

---

## D-04 — Encodeur préentraîné plutôt qu'appris depuis l'initialisation

**Retenu** : CamemBERT spécialisé, dix couches basses figées.

**Écarté** : le Transformer construit et entraîné de zéro, conservé comme
référence de comparaison.

**Pourquoi.** La mesure a tranché. Sur formulations inconnues, la
reconnaissance d'intention passe de 0,671 à 0,908 ; l'extraction d'entités ne
gagne rien, 0,982 contre 0,959.

L'explication tient à la nature des deux tâches. L'extraction repose sur des
indices structurels transférables — un nombre après « chambre » est un numéro,
quelle que soit la phrase. L'intention repose sur une compétence lexicale :
savoir que « trempé », « mouillé » et « inondé » relèvent du même champ. Aucun
corpus de domaine ne procure cette connaissance ; 138 Go de français la
procurent.

**Conséquence assumée.** La comparaison des deux approches constitue un
résultat du projet, non un renoncement : elle établit où le préapprentissage
est indispensable et où il ne sert à rien.

---

## D-05 — Corpus engendré par patrons, partitions disjointes

**Retenu** : 39 intentions, 20 patrons chacune, jeu d'évaluation aux
formulations disjointes de l'entraînement.

**Pourquoi.** La littérature signale qu'un modèle entraîné sur des patrons
apprend les patrons plutôt que la langue. La parade est le protocole : les
formulations d'évaluation n'apparaissent jamais à l'entraînement.

**Ce que cela a révélé.** Sans cette disjonction, le premier modèle aurait
affiché 0,998 de justesse. Sur formulations inconnues, il plafonnait à 0,502.
L'écart mesure exactement la mémorisation.

**Un garde-fou a détecté un défaut réel.** Deux énoncés sur 1995 figuraient
dans les deux partitions — 0,1 %. Aucune mesure globale ne l'aurait révélé.

---

## D-06 — Validité temporelle des états instantanés

**Retenu** : les états de propreté et d'occupation ne s'opposent qu'à une
arrivée imminente.

**Pourquoi.** Une chambre sale aujourd'hui sera nettoyée ; une chambre occupée
sera libérée. Leur état du jour ne peut écarter une affectation portant sur une
date ultérieure. Seule la disponibilité calendaire, établie par les séjours
enregistrés, demeure opposable.

**Ce que le défaut coûtait.** Avant correction, 79 chambres étaient écartées
pour « non prête » sur un séjour commençant une semaine plus tard.

---

## D-07 — Le système n'applique rien

**Retenu** : le système propose, consigne les décisions, et ne modifie jamais
l'état de l'établissement.

**Pourquoi.** Un système d'aide à la décision qui exécute retire au responsable
la décision qu'il prétend éclairer. L'état de l'exploitation demeure tenu par
le logiciel de gestion hôtelière.

**Conséquence.** Le journal enregistre ce qui a été demandé, compris, proposé
et décidé — sans jamais toucher aux chambres ni aux séjours. Les écarts entre
proposition et décision y sont distingués : ce sont eux qui signalent une
divergence entre le raisonnement et le jugement humain.

**Et le simulateur.** Un écran séparé, sous le préfixe `/simulation/`, tient le
rôle du logiciel de gestion pour la démonstration. La séparation est maintenue
visible.

---

## D-08 — Préférences exprimées traduites en critères d'optimisation

**Retenu** : une préférence reconnue dans l'énoncé devient un poids dans le
programme logique.

**Pourquoi.** C'est le point où la composition neuro-symbolique prend son sens :
une formulation en français acquiert une portée sur le raisonnement, sans
qu'aucune règle n'ait à être réécrite. « Une chambre à côté de la 405 » produit
`distance(c406, 1)` et pénalise chaque chambre à proportion de son éloignement.

**Ce que la mesure établit.** Sans préférence, trois chambres sont équivalentes.
Avec, l'ordre change et la chambre voisine l'emporte.

**Limite assumée.** La proximité se déduit de la numérotation et ne vaut qu'au
sein d'un étage. Aucun plan de l'établissement n'est exploité.

---

## D-09 — Abstention motivée plutôt que réponse approximative

**Retenu** : quatre niveaux de risque, et une abstention qui nomme son motif.

**Pourquoi.** Un système qui répond toujours transfère au responsable la charge
de déceler ses erreurs. Un système qui déclare ne pas pouvoir répondre de façon
fiable lui restitue une information exploitable.

**La distinction fine.** « Je ne comprends pas » diffère de « je comprends mais
il me manque un détail ». Le critère : une entité vérifiée rattache l'énoncé à
l'établissement. En son absence, une confiance faible révèle que l'intention a
été retenue faute de mieux.

**Mesure.** Trois abstentions justes sur trois, zéro abusive, dans l'évaluation
comparative.