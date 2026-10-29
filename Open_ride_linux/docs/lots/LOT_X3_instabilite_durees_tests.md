# Lot X3 – Rapport d'instabilité et de durée des tests

## 1. Objectif

Les suites prennent bien plus longtemps sur GitHub que la durée annoncée, et certains tests échouent selon la machine ou la charge (`test_tree_renderer` sur le PC, `test_workout_chart_model` au cloud, `test_vegetation_placer` sous charge). Personne ne sait quels tests sont lents ni lesquels échouent une fois sur dix. Ce lot donne ce tableau et reprend la fin du lot J5 (rapports JUnit).

## 2. À lire

`core/tests/conftest.py`, `compiler/tests/conftest.py`, `scripts/isolation_tests.py` (verrou d'une suite à la fois), `engine/tests/run_engine_tests.sh` (fonction `record`), `scripts/recette_pc.py`, `docs/lots/LOT_J5_integration_continue_v2.md`.

## 3. Travail demandé

- **`scripts/stabilite_tests.py`** : lance N fois (`--fois 5`) chaque suite choisie (`--suites core,compiler,engine`), sous le verrou commun ; pytest avec `--junitxml` et `--durations=0` ; l'engine avec `ENGINE_JUNIT=FICHIER` (nouveau : `run_engine_tests.sh` écrit un JUnit, une entrée par fichier de test, durée et statut). Sortie dans `~/OpenRide/stabilite/<date>_<heure>/` : `resume.txt`, `resume.json`, `tests.csv` (suite, test, passages, échecs, durée médiane, durée maximale), les JUnit bruts.
- **Analyse** : taux de réussite par test, liste des tests instables (au moins un échec et un succès), les 20 plus lents, durée totale médiane par suite ; `--analyse DOSSIER` refait l'analyse sans relancer.
- **CI** : les deux jobs gardent le JUnit en artefact (`actions/upload-artifact`), sans autre étape.

## 4. Fichiers

- **Nouveaux :** `scripts/stabilite_tests.py`, `core/tests/test_stabilite_tests.py`.
- **Modifiés :** `engine/tests/run_engine_tests.sh`, `.github/workflows/openride.yml`, `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. Analyse testée sur des JUnit fabriqués : test instable reconnu, test toujours en échec non classé instable, classement des lents, cas d'un test absent d'un passage.
2. `run_engine_tests.sh` écrit un JUnit valide (lu par `xml.etree`) ; sans `ENGINE_JUNIT`, rien ne change.
3. `stabilite_tests.py --fois 2 --suites compiler` passe au cloud.

## 6. Hors périmètre

Corriger les tests instables trouvés (lots à part).

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x3`).

- **`scripts/stabilite_tests.py`** : `--fois N` (5 par défaut), `--suites core,compiler,engine`, `--out DOSSIER` (défaut `~/OpenRide/stabilite/<date>_<heure>/`), `--godot`. Les passages se font sous le verrou commun des suites (`verrou_suite("stabilite_tests")`) ; pytest est lancé avec `--junitxml` et `--durations=0` (sources du dépôt dans `PYTHONPATH`, même sans installation), l'engine avec `ENGINE_JUNIT`. Le dossier reçoit `junit/<suite>_<passage>.xml`, `journaux/<suite>_<passage>.log`, `passages.json` (code et durée de chaque suite), `tests.csv` (suite, test, passages, échecs, absences, durée médiane, durée maximale), `resume.txt` et `resume.json` (tests instables, tests toujours en échec, les 20 plus lents, durée médiane de chaque suite). `--analyse DOSSIER` refait l'analyse sans relancer. Code 0 sans test instable ni toujours en échec, 1 sinon, 2 pour une option fausse.
- **Règles** : un test sauté ne compte pas comme un passage ; un test absent d'un passage (ajouté ou retiré entre deux passages) compte une absence, sans échec ; instable = au moins un échec et une réussite ; toujours en échec = échec à chaque passage où il a tourné.
- **`run_engine_tests.sh`** : avec `ENGINE_JUNIT=FICHIER`, un `<testcase>` par ligne du résumé (fichier de test unitaire, test de rendu ou étape), la durée étant le temps écoulé depuis la ligne précédente et le détail de l'échec en message ; sans la variable, rien ne change.
- **CI** : les JUnit des deux suites Python (`junit-python-3.11`, `junit-python-3.14`) et de l'engine (`junit-engine`) sont gardés en artefact (`actions/upload-artifact@v5`, même après un échec), ce qui termine le critère 4 du lot J5.
- Tests : `core/tests/test_stabilite_tests.py` (5 tests : test instable, toujours en échec, test sauté, classement des lents, absence d'un passage, fichiers écrits, JUnit de `run_engine_tests.sh` avec un faux Godot lu par `xml.etree`).
