# Architecture

Ce document décrit les couches du système, ce que chacune établit, et ce
qu'elles se transmettent. Il complète `decisions.md`, qui justifie les choix
structurants.

---

## Le principe directeur

**La couche neuronale propose, la couche symbolique dispose.**

La formule n'est pas décorative : elle décrit une asymétrie de responsabilité.
La couche neuronale établit ce qu'un énoncé exprime — avec une confiance, donc
faillible. La couche symbolique établit ce qui est vrai de l'établissement et
ce que les règles autorisent — sans incertitude, à partir de faits vérifiables.

Une lecture neuronale n'engage donc jamais le raisonnement sans avoir été
confrontée à l'état réel. C'est ce que la mesure établit : le modèle comprend
« fuite dans la 999 » avec 0,95 de justesse d'intention et propose de reloger
des clients d'une chambre inexistante. Comprendre n'est pas savoir.

---

## Le parcours d'une demande

    « il y a une fuite dans la 319, une chambre à côté de la 318 »
      ↓
    ① INTERPRÉTATION — src/neuronal/
      intention : incident_avec_preference (0,91)
      entités   : chambre=319, proximite=318
      ↓
    ② VÉRIFICATION — src/neuronal/inference.py
      319 existe    → retenue
      318 existe    → retenue
      ↓
    ③ APPRÉCIATION DU RISQUE — src/gouvernance/risque.py
      confiance suffisante, entités vérifiées
      niveau : modéré (situation engageante)
      ↓
    ④ TRADUCTION — src/symbolique/regles/
      faits du domaine → programme logique
      préférence → distance(c317, 1). poids(proximite, 2).
      ↓
    ⑤ RAISONNEMENT — Clingo
      diagnostic : quelles chambres sont admissibles, et pourquoi les autres
      décision   : laquelle retenir, à quel coût
      ↓
    ⑥ ORCHESTRATION — src/orchestration/
      la chambre devient indisponible
      les séjours concernés sont identifiés
      trois options par séjour, écartées l'une après l'autre
      ↓
    ⑦ JUSTIFICATION — src/gouvernance/explication.py
      chaque énoncé se rattache à un élément de la trace
      ↓
    ⑧ RESTITUTION — src/api/
      propositions, contreparties, motifs de rejet chiffrés
      ↓
    ⑨ DÉCISION HUMAINE — consignée au journal, rien n'est appliqué

---

## Les couches

### `domaine/` — ce dont on parle

Entités immuables : chambre, réservation, client, agent, tâche, technicien,
intervention. Objets de valeur : numéro, période, exigence, préférence.

**L'immuabilité n'est pas une coquetterie.** Une décision est prise sur une
situation donnée ; si cette situation pouvait changer en place, la reconstituer
a posteriori deviendrait impossible. Toute modification produit un nouvel objet.

Le domaine ne dépend de rien. C'est le contrat que `lint-imports` vérifie.

### `donnees/` — ce qui persiste

Tables SQLAlchemy, conversion vers et depuis le domaine, dépôts, générateur
d'établissement simulé.

**Le mappage est explicite**, non impératif : l'immuabilité des entités
l'impose. La conversion aller-retour est vérifiée par Hypothesis sur 150
exemples engendrés.

Le journal des décisions n'expose aucune méthode de modification. La propriété
tient par construction, et un test le vérifie.

### `neuronal/` — ce que l'énoncé exprime

Taxonomie de 39 intentions et 10 types d'entités. Corpus engendré par patrons,
partitions disjointes. Deux modèles : celui appris depuis l'initialisation, et
CamemBERT spécialisé.

L'architecture suit JointBERT : un encodeur partagé, deux têtes — l'une sur le
jeton de classification pour l'intention, l'autre par jeton pour les étiquettes
BIO. La perte combine les deux.

**Cette couche ne décide de rien.** Le contrat d'architecture le garantit : elle
n'accède à aucune couche supérieure.

### `symbolique/` — ce que les règles établissent

Ontologie OWL dérivée des énumérations du domaine, vérifiée par le raisonneur
HermiT. Traduction des situations en programmes logiques. Règles ASP séparées
en diagnostic et décision. Ordonnancement CP-SAT.

### `gouvernance/` — ce qui se dit et ce qui se tait

Justification par gabarits, appréciation du risque, abstention motivée.

**La propriété de fidélité** : chaque énoncé de justification se rattache à un
élément de la trace du raisonnement. Vérifiée dans les deux sens — aucun énoncé
sans fondement, aucun élément de trace sans énoncé. C'est ce qui distingue une
explication d'une reconstruction plausible.

Les gabarits sont dans `connaissances/explications/`, éditables sans
recompilation. Un test vérifie que tout motif de pénalité déclaré dans les
règles dispose d'une formulation.

### `orchestration/` — ce qu'il convient de faire

Cas d'usage : affectation, traitement d'incident, arbitrage de conflit,
production d'options, répartition de charge, affectation d'interventions,
consultation, journal.

Chaque cas d'usage assemble domaine, données et raisonnement sans qu'aucun ne
connaisse l'autre.

### `api/` — ce qui est exposé

Une route principale, `POST /demandes`, qui interprète et aiguille. Des routes
de consultation. Le journal. Et, sous le préfixe `/simulation/`, le simulateur
du logiciel de gestion — clairement distingué.

### `evaluation/` — ce que le système vaut

Scénarios annotés, banc comparatif, mesures. Trois approches confrontées sur la
même base.

---

## Les contrats vérifiés

Deux contrats `import-linter`, vérifiés à chaque exécution du CI :

**Le respect des couches.** `domaine` ne dépend de rien ; `donnees` et
`symbolique` dépendent du domaine ; `orchestration` les assemble ; `api` est
au sommet.

**La couche neuronale n'accède à aucune couche supérieure.** Elle ne peut donc
rien décider — la contrainte est structurelle, pas conventionnelle.

---

## Ce que le système ne fait pas

**Il n'applique aucune décision.** L'état de l'exploitation est tenu ailleurs.

**Il ne répond pas à tout.** 39 situations sont reconnues ; le reste est
refusé plutôt qu'interprété approximativement.

**Il n'exploite aucun plan de l'établissement.** La proximité se déduit de la
numérotation, au sein d'un même étage seulement.

**Il ne réapprend pas.** Le journal collecte les écarts entre proposition et
décision, mais aucun réentraînement automatique n'a lieu : modifier un système
critique sans supervision serait une faute.