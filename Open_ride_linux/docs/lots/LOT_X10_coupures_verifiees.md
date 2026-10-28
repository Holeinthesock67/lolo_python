# Lot X10 – Coupures volontaires, attendu contre obtenu

## 1. Objectif

`essais/coupures.sh` (essai 69) n'a jamais été lancé, et ses effets se lisent à la main. Ce lot en fait un outil officiel : chaque coupure est horodatée, puis l'outil vérifie au journal la réaction attendue et son délai.

## 2. À lire

`essais/coupures.sh` du dossier du projet, `core/src/openride_core/tools/log_report.py`, `tools/guide.py`, `engine/tests/sim_bench.py` (`_scenario_checks` : down/up, pause `trainer_lost`), `launcher.py` (relance de Godot), `docs/SIMULATION_BLE.md`.

## 3. Travail demandé

- **`python -m openride_core.tools.coupures`** : liste d'actions horodatées (`guide.jsonl`) : Godot tué (`SIGKILL` sur le processus de l'engine), trainer éteint 5 s (consigne à l'écran), boîtier droit du Click éteint 30 s, deux boîtiers 30 s, ceinture retirée. Sur le PC, les actions matérielles sont guidées (bip, compte à rebours) ; l'arrêt de Godot est fait par l'outil.
- **Attendu contre obtenu** : pour chaque action, la ligne attendue au journal du lanceur ou du core (`down` puis `up`, `PAUSED (trainer_lost)` puis `RUNNING`, relance de l'engine, repli clavier) et un délai maximal ; tableau OK/ÉCHEC avec le délai mesuré.
- **`--sim`** : mêmes actions sur le Bluetooth simulé (événements `drop` et `silence` injectés par un scénario généré) et vraie relance de l'engine sous Xvfb, pour la CI ou le cloud.
- **`--analyse DOSSIER`** pour refaire la comparaison.

## 4. Fichiers

- **Nouveaux :** `core/src/openride_core/tools/coupures.py`, `core/tests/test_coupures.py`.
- **Modifiés :** `tools/guide.py`, `docs/OUTILS_DE_TEST.md`, `docs/PROTOCOLE_TEST_2026-10-26.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. L'analyse sur des journaux fabriqués : coupure suivie de sa reprise (OK), reprise trop tardive (ÉCHEC), reprise absente (ÉCHEC).
2. `coupures --sim` sans Godot (`--sans-engine`) passe au cloud ; avec Godot sous Xvfb, la relance de l'engine est vue.

## 6. Hors périmètre

Changer les délais de reconnexion.
