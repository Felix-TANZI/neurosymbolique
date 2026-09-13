# État des exigences

Reprise des exigences du cahier des charges technique version 2.0, annotées de
leur état de réalisation et de la preuve qui l'établit.

**Légende.** `fait` — l'exigence est satisfaite et vérifiée ; `partiel` — une
part est satisfaite, le reste est précisé ; `manque` — l'exigence n'est pas
traitée.

---

## Périmètre — les neuf décisions critiques

| Réf. | Décision | État | Preuve |
|---|---|---|---|
| DC-1 | Affectation d'une chambre | **fait** | `orchestration/affectation.py`, 11 tests |
| DC-2 | Réaffectation | **fait** | `orchestration/incident.py`, `arbitrage.py` |
| DC-3 | Indisponibilité et propagation | **fait** | `TraiterUnIncident`, scénario S-09 |
| DC-4 | Priorisation du nettoyage | **fait** | `symbolique/ordonnancement/`, CP-SAT |
| DC-5 | Chambre urgente | **partiel** | intention reconnue, ordonnancement non branché |
| DC-6 | Réaffectation d'agent | **partiel** | intention reconnue, replanification non branchée |
| DC-7 | Qualification de gravité | **fait** | `domaine/maintenance.py`, `qualifier_la_criticite` |
| DC-8 | Priorisation des interventions | **fait** | `orchestration/maintenance.py`, 23 tests |
| DC-9 | Affectation de technicien | **fait** | `AffecterLesInterventions`, scénario S-19 |

**Sept décisions sur neuf sont complètes.** DC-5 et DC-6 sont reconnues par le
modèle mais leur traitement n'est pas relié à l'ordonnanceur : le système
comprend la demande sans la traiter.

---

## EF-1xx — Interprétation

| Réf. | État | Preuve |
|---|---|---|
| EF-101 | **fait** | `neuronal/inference_preentrainee.py` ; F1 entités 0,959 sur formulations inconnues |
| EF-102 | **fait** | `EntiteExtraite.confiance`, `Interpretation.confiance_d_intention` |
| EF-103 | **fait** | `gouvernance/risque.py`, seuil 0,70 configurable ; 3 abstentions justes sur 3 |
| EF-104 | **fait** | 39 intentions couvrant les trois services ; justesse 0,908 |
| EF-105 | **manque** | aucune estimation de durée ni de gravité probable n'est apprise ; la criticité est établie par règle, non estimée |
| EF-106 | **fait** | `MotifDAbstention.HORS_DOMAINE` ; scénarios S-12, S-13, S-23 |
| EF-107 | **partiel** | l'API accepte une situation structurée ; l'interface n'expose plus de formulaire depuis la refonte |

---

## EF-2xx — Représentation des connaissances

| Réf. | État | Preuve |
|---|---|---|
| EF-201 | **fait** | `symbolique/ontologie/schema.py`, vérifiée par HermiT |
| EF-202 | **fait** | `decision_chambres.lp` sépare contraintes d'intégrité et `#minimize` |
| EF-203 | **fait** | `connaissances/regles/` monté en lecture seule, éditable sans reconstruction |
| EF-204 | **partiel** | la concordance diagnostic/décision est vérifiée par deux propriétés Hypothesis ; aucune détection d'incohérence à l'ajout d'une règle |
| EF-205 | **manque** | `version_regles` existe dans le journal mais n'est ni renseigné ni exploité |
| EF-206 | **fait** | le service maintenance a été ajouté sans modifier le moteur — démonstration effective de l'exigence |

---

## EF-3xx — Raisonnement

| Réf. | État | Preuve |
|---|---|---|
| EF-301 | **fait** | `diagnostic_chambres.lp`, prédicat `admissible/2` |
| EF-302 | **fait** | `#minimize` sur les pénalités souples |
| EF-303 | **fait** | contraintes d'intégrité ASP ; propriété Hypothesis `TestGarantieDeConformite` |
| EF-304 | **fait** | `RejetDePaire`, motifs dénombrés et restitués |
| EF-305 | **fait** | `LevierPropose` dans `arbitrage.py` — relâchement d'équipement, de catégorie, ou permutation |
| EF-306 | **partiel** | incident → indisponibilité → relogement fonctionne ; incident → intervention technique est restitué mais non chaîné |
| EF-307 | **fait** | un moteur unique traite les neuf décisions ; contrat `lint-imports` |
| EF-308 | **fait** | `Resultat.penalites`, `options_ecartees`, `Justification` |
| EF-309 | **fait** | `Resultat.interrompu`, `temps_maximal` ; gabarit `optimalite_non_garantie` |

---

## EF-4xx — Justification et gouvernance

| Réf. | État | Preuve |
|---|---|---|
| EF-401 | **fait** | `gouvernance/explication.py`, gabarits dans `connaissances/explications/` |
| EF-402 | **fait** | motifs dominants chiffrés : « 101 chambres déjà réservées sur ces dates » |
| EF-403 | **fait** | `Justification.contreparties`, avantages et contreparties par option |
| EF-404 | **fait** | le système n'écrit jamais dans l'état de l'établissement (D-07) |
| EF-405 | **fait** | `orchestration/journal.py`, `ConsignerUneDecision`, 13 tests |
| EF-406 | **partiel** | consultation faite ; export non implémenté |
| EF-407 | **fait** | trace restituée, repliable dans l'interface |

---

## EF-5xx — Apprentissage incrémental

| Réf. | État | Preuve |
|---|---|---|
| EF-501 | **fait** | le journal distingue les écarts : `marque_un_ecart` |
| EF-502 | **manque** | aucun réapprentissage automatique |
| EF-503 | **partiel** | le jeu d'évaluation est figé et disjoint ; aucune comparaison de versions |
| EF-504 | **fait** | les contraintes dures ne sont modifiables que par édition de fichier ; aucun composant d'apprentissage n'y accède — vérifié par `lint-imports` |
| EF-505 | **manque** | pas de gestion de versions de modèles |
| EF-506 | **partiel** | `historique.json` consigne chaque entraînement ; aucune décision de déploiement automatique |

**Ce qui est acquis.** La collecte est en place et la frontière EF-504 est
structurelle. Le réapprentissage lui-même n'est pas construit.

---

## EF-6xx — Interfaces

| Réf. | État | Preuve |
|---|---|---|
| EF-601 | **fait** | FastAPI, documentation OpenAPI générée |
| EF-602 | **fait** | interface React : Aujourd'hui, Traiter, Établissement, Historique |
| EF-603 | **partiel** | les règles sont éditables par fichier ; aucune interface d'administration |

---

## ENF — Exigences non fonctionnelles

| Réf. | Exigence | État | Preuve |
|---|---|---|---|
| ENF-01 | Zéro violation de contrainte dure | **fait** | propriété Hypothesis, 80 exemples engendrés par exécution |
| ENF-02 | Garantie indépendante du neuronal | **fait** | `lint-imports` : la couche neuronale n'accède à aucune couche supérieure |
| ENF-03 | Déterminisme | **fait** | graines consignées ; deux exécutions de `specialiser` ont produit des chiffres identiques à la décimale |
| ENF-04 | Couverture explicative | **fait** | test de couverture des motifs : tout motif déclaré a une formulation |
| ENF-05 | Fidélité explicative | **fait** | vérifiée bidirectionnellement : aucun énoncé sans trace, aucune trace sans énoncé |
| ENF-06 | Intelligibilité | **manque** | aucune évaluation par des opérateurs métier |
| ENF-07 | Latence sous 5 s au 95e centile | **partiel** | 883 ms en moyenne sur l'évaluation ; centile non mesuré |
| ENF-08 | 300 chambres sans dégradation | **partiel** | profils `complexe` (800) et `resort` (400) existent ; mesure non refaite depuis les extensions |
| ENF-09 | Authentification et rôles | **manque** | aucune authentification |
| ENF-10 | Journal en ajout seul | **fait** | `JournalDesDecisions` n'expose aucune méthode de modification ; test dédié |
| ENF-11 | Aucune donnée personnelle réelle | **fait** | établissement entièrement simulé |
| ENF-12 | Aucun secret dans le dépôt | **fait** | secrets en variables d'environnement GitHub |
| ENF-13 | Architecture modulaire | **fait** | deux contrats `lint-imports` tenus, 74 fichiers analysés |
| ENF-14 | Couverture de tests > 80 % | **fait** | 488 tests, seuil `--cov-fail-under=80` dans `pyproject.toml` |

---

## Synthèse

| | Fait | Partiel | Manque |
|---|---|---|---|
| Décisions critiques | 7 | 2 | 0 |
| Exigences fonctionnelles | 26 | 7 | 4 |
| Exigences non fonctionnelles | 9 | 3 | 2 |

**Ce qui manque et qui compte.** L'authentification (ENF-09) est absente : le
système est ouvert à quiconque y accède. L'estimation des grandeurs incertaines
(EF-105) n'est pas construite. Le réapprentissage (EF-502, EF-505) est collecté
mais non exécuté.

**Ce qui manque et qui se défend.** L'évaluation d'intelligibilité (ENF-06)
suppose des opérateurs métier disponibles — le risque RT-05 du cahier des
charges l'avait anticipé. L'interface d'administration (EF-603) est remplacée
par l'édition de fichiers, ce qui satisfait le besoin sans l'ergonomie.

**Un résultat non prévu au cahier des charges.** La comparaison entre un
Transformer appris depuis l'initialisation et un encodeur préentraîné
spécialisé n'était pas exigée. Elle établit où le préapprentissage est
indispensable — 0,671 contre 0,908 sur la reconnaissance d'intention — et où il
ne sert à rien — 0,982 contre 0,959 sur l'extraction d'entités.