# Lot X19 – Micro-banc par image et budgets par machine

## 1. Objectif

Chaque lot du décor vivant mesure le coût de sa mise à jour par image à sa façon, et certains tests gardent un seuil de temps en dur (`test_passersby_model` < 0,2 ms échoue au cloud). Le fil R demande en plus la mesure du temps de synthèse des sons R18 et de leur mémoire, par machine (objectif 300 ms et 8 Mo sur la GTX 1060, limite large de 2 s en CI).

## 2. À lire

`engine/tests/perf_budget.gd` et `perf_budgets.json` (lot X2), les tests des modèles du décor (`test_crowd_model.gd`, `test_fauna_behaviour.gd`, `test_passersby_model.gd`…), `engine/scripts/sound_model.gd` / synthèse des sons du Cyber-Rogue.

## 3. Travail demandé

- **`PerfBudget.frame_cost(fn, frames, warmup)`** : coût médian et p95 d'une mise à jour par image sur N images simulées (chauffe, médiane, p95), et **`PerfBudget.memory_kb(fn)`** (mémoire statique avant et après, `Performance.MEMORY_STATIC`).
- **Budgets** ajoutés à `perf_budgets.json` pour les coûts par image du décor encore mesurés en dur, pour la synthèse des sons (`sound_synthesis_rogue` : 300 ms, 8 Mo sur le PC cible ; `ci_ms` large).
- **Rapport** `engine/tests/perf_budget_report.py` : lit les lignes `[PERF]` d'un passage de `run_engine_tests.sh` (ou `PERF_CSV`) et donne par budget la mesure, le budget de cette machine et la marge.

## 4. Fichiers

- **Modifiés :** `perf_budget.gd`, `perf_budgets.json`, tests unitaires concernés, `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `engine/tests/perf_budget_report.py`, `core/tests/test_perf_budget_report.py`.

## 5. Critères d'acceptation

1. `frame_cost` testé sur une fonction de coût connu ; budgets lus par machine.
2. Le rapport lit les lignes `[PERF]` réelles d'un passage de `run_engine_tests.sh`.

## 6. Hors périmètre

Optimiser le décor.

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x19`).

- **`PerfBudget.frame_cost(fn, images, chauffe)`** : `fn` appelée une fois par image simulée (l'état avance d'un appel à l'autre), rend `median_ms`, `p95_ms` et `frames`. **`PerfBudget.memory_kb(fn)`** : `Performance.MEMORY_STATIC` avant et après, en Ko ; **`check_memory(nom, Ko)`** face à `budget_kb` (`ci_kb` en CI, remplacement par machine comme pour les temps). `passes(valeur, limite)` porte le verdict seul (report ou strict).
- **Plus aucun seuil de temps en dur** dans les tests unitaires : passants (`passersby_model_frame`, `passersby_frame` ; les 80 passants affichés restent un contrôle à part), nuages (`sky_clouds_frame`), vent (`wind_evaluate`), végétation par biome (`vegetation_tile_biomes`), maillages des véhicules (`vehicle_meshes_build`), courbes de 2 h (`chart_geometry_2h`), poids des biomes (`biome_weights_1000`). La ligne de profil de la tuile de jungle n'est plus une ligne `[PERF]`.
- **Mémoire des sons synthétisés au lancement** (`sound_generation_memory`, 4 Mo, mesurée sur `SoundPlayer.new()` : 1,9 Mo) ; **sons du Cyber-Rogue** déclarés (`sound_synthesis_rogue` 300 ms, `ci_ms` 2 000 ; `sound_synthesis_rogue_memory` 8 Mo), à mesurer quand R18 sera livré : le rapport les liste en « non mesurés ».
- **`run_engine_tests.sh`** : `PERF_CSV` reçoit `date;nom;valeur;budget;dépassé;unité` (ms ou Ko) ; `PERF_LINES=FICHIER` garde les lignes brutes.
- **`engine/tests/perf_budget_report.py`** : lit les lignes `[PERF]` (sortie du passage, `PERF_LINES` ou `PERF_CSV`, ancien CSV sans unité compris) ; pour chaque budget de `perf_budgets.json` : mesure, budget de la machine, marge, du plus serré au plus large, puis les non mesurés et les mesures sans budget ; `--json`, `--strict` (code 1 au-delà d'un budget).
- **Mesuré au cloud** (passage complet, `VISUAL_CONFIGS=none`) : 34 budgets mesurés sur 36, 3 dépassements en mode report, connus et sans lien avec ce lot (`sound_generation` 855 ms pour 500, `boats_frame` 0,20 pour 0,15 ms, `vegetation_tile_max` 55 pour 50 ms) ; le plus serré ensuite : `fauna_frame_200` à 2 % de marge.
- Tests : `engine/tests/unit/test_perf_budget.gd` (15 vérifications : coût connu de 1 ms par image avec une image de 3 ms vue par le p95, mémoire, budgets PC, CI et locaux, verdicts) ; `core/tests/test_perf_budget_report.py` (5 tests).
- Reste sur le PC : un passage avec `PERF_LINES`, puis le rapport (marges sur la GTX 1060).
