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

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x34`).

- `scripts/recompte_tests.py` : motifs, comptes et correction ; `test_docs_coherence.py` les importe (plus de double définition) et vérifie aussi les fichiers de tests unitaires et de rendu de l'engine. Premier passage : la doc annonçait 7 tests de rendu pour 11 fichiers.
- `run_engine_tests.sh` : le filtre des erreurs Godot ne tolère plus toute ligne « mesh … null » ; il n'écarte qu'une erreur dont la ligne `at:` suivante vient de `servers/rendering/dummy/` (210 lignes « Parameter "m" is null » par passage, toutes du serveur factice de `--headless`, dans `test_avatar_model`, `test_fauna_biomes`, `test_ribbon_builder`, `test_roadside_model`, `test_rogue_host` et `test_world_menu_view`). Aucune autre erreur n'apparaît sur `main`.
- Seuils en dur remplacés par `PerfBudget.check` (onze entrées ajoutées à `perf_budgets.json`) dans `test_biome_model`, `test_passersby_model` (deux, dont celui qui échouait au cloud), `test_sky_clouds`, `test_vegetation_biomes`, `test_vehicle_mesh`, `test_visual_grade_scale` (surcoût relatif en %, nouvel argument `unit` de `PerfBudget.check`), `test_wind_model`, `test_workout_chart_model` (trois). Les lignes `[PERF]` passent à quatre décimales (les budgets de quelques µs s'affichaient 0,00).
- `test_no_hardcoded_timing.gd` : repère un `_check(` qui compare une durée à un nombre (il a trouvé le troisième seuil de `test_workout_chart_model`).
- Écart : le surcoût de `visual_grade_overhead` dépasse son budget au cloud (9,5 % pour 5 %), signalé en mode `report` comme avant ; c'est la raison du passage par le budget.
