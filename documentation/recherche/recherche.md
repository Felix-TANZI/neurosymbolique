# Travaux consultés et positionnement

Synthèse des travaux sur lesquels les décisions techniques du projet se sont
appuyées.

> **Avertissement.** Les références bibliographiques ci-dessous sont
> incomplètes : les titres, auteurs et années ont été relevés au cours des
> recherches sans que les notices complètes aient été conservées.
> Une citation approximative dans un travail académique est plus dommageable
> qu'une absence de citation.

---

## 1. Architecture conjointe d'interprétation

### Ce que la littérature établit

Le modèle de référence pour la reconnaissance conjointe d'intention et
l'extraction d'entités est **JointBERT**, publié en 2019. Son principe : un
encodeur unique alimente deux têtes de classification, optimisées par une perte
combinée.

Le mécanisme est précisément documenté. L'état caché final du jeton de
classification alimente la tête d'intention ; l'état final du premier
sous-jeton de chaque mot alimente la tête d'étiquetage. Le modèle est optimisé
en minimisant la somme des entropies croisées des deux tâches, avec un
coefficient pondérant l'étiquetage.

Les travaux rapportent une amélioration significative de la précision de
classification, de la mesure F1 d'extraction et de la justesse au niveau de la
phrase, comparativement aux modèles récurrents à attention.

### Ce que le projet en a retenu

L'architecture à encodeur partagé et deux têtes, avec la perte combinée. Le
coefficient d'étiquetage est fixé à 2,0 pour compenser le déséquilibre des
classes : un énoncé produit une étiquette d'intention et une dizaine
d'étiquettes de jetons.

**Référence à compléter.** Chen, Zhu, Wang (?), *BERT for Joint Intent
Classification and Slot Filling*, arXiv 2019. Implémentation de référence
disponible publiquement.

---

## 2. Entraînement d'un Transformer depuis l'initialisation

### Ce que la littérature établit

La croyance courante veut qu'entraîner un Transformer profond depuis
l'initialisation exige de grandes quantités de données. Un travail de 2020
nuance ce point : avec une initialisation et une optimisation appropriées, les
bénéfices des Transformers profonds se transposent à des tâches exigeantes sur
petits jeux de données.

Les techniques désignées : initialisation contrôlée à faible écart type,
échauffement du taux d'apprentissage, régularisation.

### Ce que le projet en a retenu, et ce qu'il a mesuré

Le premier modèle a été construit selon ces principes : initialisation à écart
type 0,02, échauffement sur 10 % des pas, décroissance en cosinus,
pré-normalisation.

**La mesure a nuancé la conclusion.** Sur l'extraction d'entités, l'approche
fonctionne : F1 de 0,982 sur des formulations jamais vues. Sur la
reconnaissance d'intention, elle plafonne à 0,671.

L'explication tient à la nature des deux tâches. L'extraction repose sur des
indices structurels transférables — un nombre après « chambre » est un numéro,
quelle que soit la phrase. L'intention repose sur une compétence lexicale :
savoir que « trempé », « mouillé » et « inondé » relèvent du même champ. Aucun
corpus de domaine ne procure cette connaissance.

**C'est un résultat du projet**, obtenu par comparaison contrôlée : même
corpus, même graine, même partition, même protocole.

**Référence à compléter.** *Optimizing Deeper Transformers on Small Datasets*,
2020 (?). Vérifier auteurs et lieu de publication.

---

## 3. Encodeur préentraîné pour le français

### Ce que la littérature établit

**CamemBERT** est le modèle de référence pour le français, fondé sur
l'architecture RoBERTa et entraîné sur 138 Go de texte français. Ses
applications documentées incluent la classification de texte et l'étiquetage de
jetons.

### Ce que le projet en a retenu

Le modèle est spécialisé sur le domaine avec dix couches basses figées.
110 645 022 paramètres au total, 14 800 941 effectivement entraînés.

**Le gel n'est pas un pis-aller.** Un corpus de 13 000 énoncés engendrés par
patrons ne saurait améliorer une représentation acquise sur 138 Go ; il la
dégraderait. Geler protège ce qui fait la valeur du modèle, et réduit le calcul
par trois.

**Deux taux d'apprentissage distincts** : 2×10⁻⁵ pour l'encodeur, 10⁻³ pour les
têtes. Les têtes partent de zéro et doivent apprendre vite ; l'encodeur porte
des représentations acquises qu'un taux élevé détruirait.

**Référence à compléter.** Martin et al. (?), *CamemBERT: a Tasty French
Language Model*, ACL 2020 (?). Vérifier la liste complète des auteurs.

---

## 4. Corpus engendrés par patrons

### Ce que la littérature établit

La génération de données par patrons comporte deux risques documentés : la
rigidité inhérente des patrons, et le surapprentissage. Les travaux consultés
insistent sur la conception soigneuse du processus de génération et sur la
validation rigoureuse des performances.

### Ce que le projet en a retenu, et ce que la mesure a révélé

Trois parades ont été appliquées : formulations d'évaluation disjointes de
l'entraînement, perturbations lexicales réalistes, masquage aléatoire de jetons
pendant l'entraînement.

**La disjonction des partitions a été décisive.** Sans elle, le premier modèle
aurait affiché 0,998 de justesse d'intention. Sur formulations inconnues, il
plafonnait à 0,502. L'écart mesure exactement la mémorisation.

**Un défaut réel a été détecté par le garde-fou.** Deux énoncés sur 1995
figuraient dans les deux partitions — un dixième de pour cent. Aucune mesure
globale ne l'aurait révélé.

**Un second enseignement, quantitatif.** Un corpus de 10 200 énoncés engendrés
à partir de 150 patrons contient l'information de 150 structures, pas de 10 200
exemples. Porter les patrons de 150 à 450 a fait passer la justesse d'intention
de 0,502 à 0,671 — sans changer le volume. **C'est la diversité qui compte, pas
le volume.**

**Référence à compléter.** Travaux sur la génération synthétique pour la
compréhension d'énoncés. Notices non conservées.

---

## 5. Échelle des jeux de référence

### Ce que la littérature établit

Deux jeux servent de référence dans le domaine. **ATIS** compte 4 478 énoncés
d'entraînement, 21 intentions et 120 types de créneaux. **SNIPS** en compte
13 084, avec 7 intentions et 72 créneaux.

### Ce que le projet en a retenu

Le corpus final compte 13 300 énoncés d'entraînement, 39 intentions, 10 types
d'entités. **L'échelle de SNIPS, avec davantage d'intentions et moins de types
d'entités.**

Cette comparaison permet de situer le corpus sans prétendre à une contribution
sur ce plan : il est de taille usuelle pour le domaine.

---

## 6. Multi-intention

### Ce que la littérature établit

La plupart des approches supposent qu'un énoncé porte une intention unique.
Or un énoncé en situation réelle en porte souvent plusieurs, et les systèmes à
intention unique produisent alors de mauvaises performances.

Une approche documentée, **SLIM**, introduit un classifieur explicite reliant
chaque élément extrait à son intention, la relation étant de plusieurs vers un.

### Ce que le projet a décidé, et pourquoi il s'écarte

Le projet emploie des **intentions composites** plutôt qu'une classification
multi-étiquette : `incident_avec_preference`, `incident_avec_intervention`,
`changement_avec_preference`.

**Trois raisons.** Le domaine comporte peu de combinaisons sensées — une
poignée, pas quinze. La structure du modèle reste inchangée, donc l'évaluation
demeure comparable. Le traitement en aval est plus simple : une intention
composite déclenche un traitement, sans logique de combinaison.

**C'est un écart assumé.** La littérature traite le cas général ; le domaine
appelle une solution spécifique et plus fiable. Le résultat le confirme :
passer de 29 à 39 intentions n'a pas dégradé la justesse — 0,908 dans les deux
cas.

**Référence à compléter.** SLIM, *Explicit Slot-Intent Mapping with BERT for
Joint Multi-Intent Detection and Slot Filling* (?). Vérifier auteurs et année.

---

## 7. Ce que le projet apporte

Trois éléments ne proviennent pas de la littérature consultée.

**La mesure de ce que le préapprentissage apporte, tâche par tâche.** La
comparaison est faite sur le même corpus et le même protocole. Elle établit que
l'extraction d'entités n'en tire aucun bénéfice et que la reconnaissance
d'intention en tire 24 points.

**La traduction d'une préférence exprimée en critère d'optimisation.** Une
formulation française — « une chambre à côté de la 405 » — devient un poids
dans un programme logique, sans qu'aucune règle n'ait à être réécrite.

**L'évaluation comparative de trois approches décisionnelles.** Neuronale
seule, symbolique seule, composée — sur 24 scénarios annotés couvrant trois
services. Le résultat central : la couche neuronale comprend « fuite dans la
999 » avec 0,952 de justesse d'intention et propose de reloger des clients
d'une chambre inexistante. La composée la détecte dans 100 % des cas.

---

## 8. Ce qu'il reste à vérifier

**Les notices bibliographiques.** Toutes les références ci-dessus doivent être
vérifiées : auteurs complets, titres exacts, lieux et années de publication.

**Le positionnement dans la taxonomie de Kautz.** Le cahier des charges
classe l'architecture en Type 3, fédérative. Cette classification n'a pas été
revérifiée depuis, et la taxonomie elle-même mérite une référence précise.

**L'état de l'art des systèmes d'aide à la décision hôtelière.** Aucune
recherche n'a été conduite sur ce point. L'objectif OS-1 du cahier des charges
le prévoyait.

**Les travaux sur la fidélité explicative.** La propriété est implémentée et
vérifiée, mais son fondement théorique n'a pas été recherché. C'est une lacune
pour un mémoire, puisque la notion est centrale au projet.