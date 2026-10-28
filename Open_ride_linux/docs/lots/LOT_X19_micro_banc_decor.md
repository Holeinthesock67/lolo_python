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
