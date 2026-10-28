# Lot X34 – Hygiène des suites : recompte des tests, erreurs relevées, seuils de temps

## 1. Objectif

Trois défauts des suites signalés par les fils le 28 octobre :

1. les nombres de tests écrits dans `README.md` et `docs/SUIVI_AVANCEMENT.md` (vérifiés par `test_docs_coherence`) changent à chaque fusion : toutes les PR ouvertes entrent alors en conflit sur ces lignes et doivent être recomptées à la main (fil des fusions) ;
2. `run_engine_tests.sh` ne relève pas les lignes `ERROR:` écrites par Godot pendant un test unitaire qui passe (ex. « Parameter m is null » de `test_living_decor`) (fil du décor) ;
3. des seuils de temps restent en dur hors de `PerfBudget` (ex. `test_passersby_model` < 0,2 ms, qui échoue au cloud) (fil du décor).

## 2. À lire

`core/tests/test_docs_coherence.py` (comptes de tests), `engine/tests/run_engine_tests.sh`, `engine/tests/perf_budget.gd`, `perf_budgets.json`.

## 3. Travail demandé

- **`scripts/recompte_tests.py`** : compte les tests du core, du compilateur et de l'engine comme `test_docs_coherence` les compte, et réécrit les lignes concernées de `README.md` et `SUIVI_AVANCEMENT.md` (`--verifier` : seulement dire ce qui diffère, code 1). Le message d'échec de `test_docs_coherence` donne la commande à lancer. Utilisable après une fusion de `main` dans une branche, avant de pousser.
- **Erreurs relevées** : `run_engine_tests.sh` compte, pour chaque test unitaire, les lignes `ERROR:` et `SCRIPT ERROR` de sa sortie, hors liste des tolérances (mêmes motifs que `visual_check.py`) ; une erreur fait échouer le test (`ENGINE_ERRORS=report` pour seulement les afficher le temps de corriger).
- **Seuils en dur** : recherche des comparaisons de temps dans `engine/tests/unit/*.gd` (`get_ticks_usec`/`get_ticks_msec` comparés à une constante) ; chacune passe par `PerfBudget.check` avec une entrée dans `perf_budgets.json` ; un test GDScript du lot vérifie qu'il n'en reste aucune (lecture des sources).

## 4. Fichiers

- **Nouveaux :** `scripts/recompte_tests.py`, `core/tests/test_recompte_tests.py`, `engine/tests/unit/test_no_hardcoded_timing.gd`.
- **Modifiés :** `run_engine_tests.sh`, tests unitaires concernés, `perf_budgets.json`, `test_docs_coherence.py` (message), `docs/OUTILS_DE_TEST.md`, `CLAUDE.md` (règle : lancer le recompte après une fusion), ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. `recompte_tests.py` sur une copie où un nombre est faux le corrige ; relancé, il ne change plus rien.
2. Un test unitaire qui écrit une erreur Godot échoue ; les erreurs existantes sont corrigées ou listées dans les tolérances avec leur raison.
3. Plus aucun seuil de temps en dur ; la suite passe au cloud.

## 6. Hors périmètre

Changer la façon dont la doc annonce les nombres.
