# Système de raisonnement neuro-symbolique pour l'aide à la décision critique

Aide à la décision dans la gestion des opérations internes d'un hôtel.
Le système interprète une situation formulée en français, la confronte à
l'état de l'établissement, en tire les conséquences par raisonnement sous
contraintes, et soumet ses propositions à un responsable.

**Principe directeur : la couche neuronale propose, la couche symbolique
dispose.**

## Ce que le système fait

Une phrase suffit :

    il y a une fuite dans la 319

Le système établit que la chambre devient indisponible, identifie les séjours
concernés, propose jusqu'à trois chambres de relogement pour chacun avec leurs
contreparties, et signale ceux qu'il ne peut reloger en indiquant pourquoi.

    quelles chambres sont hors service à l'étage 4

Réponse immédiate depuis l'état de l'établissement.

    j'ai 12 chambres à faire et 3 agents, comment répartir

Répartition équilibrée, durée d'achèvement, et effectif requis si une échéance
ne peut être tenue.

    il y a une fuite dans la 999

Refus : cette chambre n'existe pas. Le modèle a compris la phrase, la
vérification symbolique l'écarte.

## Architecture

    Énoncé libre
      ↓
    Couche neuronale — intention, entités, confiance
      ↓
    Vérification symbolique — les références existent-elles ?
      ↓
    Appréciation du risque — quatre niveaux, ou abstention motivée
      ↓
    Raisonnement — règles ASP, ordonnancement CP-SAT
      ↓
    Justification — dérivée de la trace, jamais rédigée après coup
      ↓
    Décision humaine — consignée au journal

Le système n'applique rien. Il assiste une décision ; l'exploitation demeure
pilotée par ceux qui en répondent.

## Résultats

Évaluation comparative sur 24 scénarios couvrant trois services.

| | Neuronale seule | Symbolique seule | Composée |
|---|---|---|---|
| Conduite juste | 0,458 | 0,042 | **0,958** |
| Justesse d'intention | 0,952 | — | 0,952 |
| Références inexistantes détectées | 0,000 | — | **1,000** |
| Abstentions abusives | 0 | 20 | **0** |
| Latence moyenne | 85 ms | 0 ms | 883 ms |

La ligne des références est l'argument central : la couche neuronale comprend
« fuite dans la 999 » avec 0,95 de justesse d'intention et propose de reloger
des clients d'une chambre qui n'existe pas. **Comprendre n'est pas savoir.**

Le modèle d'interprétation a par ailleurs été comparé à un Transformer appris
depuis l'initialisation, sur le même corpus et le même protocole :

| Sur formulations inconnues | Depuis zéro | CamemBERT spécialisé |
|---|---|---|
| Justesse d'intention | 0,671 | **0,908** |
| F1 des entités | 0,982 | 0,959 |

L'extraction d'entités ne gagne rien au préapprentissage — elle repose sur des
indices structurels. La reconnaissance d'intention gagne 24 points : elle
repose sur une compétence lexicale qu'aucun corpus de domaine ne procure.

## Mise en route

Prérequis : Python 3.13, Node 20, Java 21 (pour le raisonneur ontologique).

    cd noyau
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -e ".[dev]"

Constituer un établissement simulé :

    python -m scripts.constituer --profil urbain --jour 2026-08-12

Entraîner le modèle d'interprétation (environ trois heures sur CPU) :

    python -m scripts.specialiser --epoques 3 --par-intention 400

Lancer le noyau :

    uvicorn src.api:application --reload

Lancer l'interface :

    cd ..\interface
    npm install
    npm run dev

## Vérification

    pytest -m "not lent" --no-cov     # 464 tests, 40 s
    pytest                            # suite complète
    ruff check src tests scripts
    mypy src tests scripts
    lint-imports                      # contrats d'architecture

Évaluation comparative :

    python -m scripts.evaluer --sortie evaluation/resultats.json

## Organisation

    noyau/
      src/
        domaine/          entités immuables, règles métier élémentaires
        donnees/          persistance, conversion, simulation
        neuronal/         taxonomie, corpus, modèles, inférence
        symbolique/       ontologie OWL, règles ASP, ordonnancement CP-SAT
        gouvernance/      justification par gabarits, appréciation du risque
        orchestration/    cas d'usage : affectation, incident, arbitrage…
        evaluation/       scénarios et banc comparatif
        api/              routes FastAPI
      tests/              464 tests, dont propriétés Hypothesis
      scripts/            constitution, entraînement, évaluation
    connaissances/
      regles/             programmes ASP
      explications/       gabarits de justification
    interface/            React, TypeScript, Tailwind
    evaluation/           résultats consignés

Les fichiers de `connaissances/` sont éditables sans recompilation : les règles
et le vocabulaire des justifications relèvent de l'exploitation, non du code.

## Limites connues

Le système reconnaît 39 situations. Une demande qui n'en relève d'aucune est
refusée plutôt qu'interprétée approximativement — c'est délibéré, et mesuré :
3 abstentions justes sur 3 dans l'évaluation.

La proximité entre chambres se déduit de la numérotation et ne vaut qu'au sein
d'un même étage. Aucun plan de l'établissement n'est exploité.

Les poids des modèles ne sont pas versionnés. Ils se régénèrent par les
scripts, dont les graines sont consignées.