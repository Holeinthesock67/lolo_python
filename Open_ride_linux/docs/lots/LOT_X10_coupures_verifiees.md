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

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x10`).

- **`python -m openride_core.tools.coupures`** : actions `godot`, `trainer`, `click_droit`, `clicks`, `ceinture` (`--actions` pour en choisir), guidées (guide X5/X8, essai `coupures` de `guide materiel`). Godot est tué par l'outil (tous les processus `Godot*`, comme `essais/coupures.sh`) ; les boîtiers du Click sont coupés par `bluetoothctl block` quand leur adresse est dans `config.toml`, sinon l'outil demande de retirer les piles ; trainer et ceinture sont des consignes.
- **Attendus** (écrits avec chaque action dans `actions.jsonl`, relus par `--analyse`) : `godot` : « l'engine a planté » au journal du lanceur en 5 s, puis « Reçu 'hello' de l'engine » en 40 s ; `trainer` : `down` et pause en 10 s, `up` et reprise en 30 s après la fin ; boîtiers : `down` en 10 s, `up` en 30 s après la fin ; ceinture : FC absente des relevés en 10 s (FC relayée : gel Q5 + 2 s, 17 s par défaut), revenue en 20 s après la fin. Une ligne n'est cherchée qu'entre la coupure et l'action suivante : une reprise tardive est en ÉCHEC avec son délai, une reprise absente en ÉCHEC « absent ».
- **Repli clavier :** le clavier reste actif en parallèle du Click (contrat IPC §6) ; il n'y a pas de repli à vérifier, l'attendu n'est donc pas listé.
- **`--sim`** : scénario généré (`sleep` + `drop` puis `wake` pour le trainer et les boîtiers, `contact` pour la ceinture), core avec les vrais pilotes, vrai lanceur (`launcher.Supervisor`, compilation coupée) et Godot sous Xvfb ; l'action `godot` tue l'engine lancé par l'outil et lui seul. `--sans-engine` : core seul, sans l'action `godot`. `--court` : coupures de 4 à 10 s.
- **Mesuré au cloud** : `--sim --court --actions godot,trainer` : plantage noté en 0,1 s, engine relié de nouveau en 3,0 s, pause 3,1 s après la coupure, reprise 0,4 s après la fin ; `--sim --sans-engine --court` : les 12 attendus des quatre coupures matérielles obtenus.
- Tests : `core/tests/test_coupures.py` (9 tests : reprise à temps, trop tardive, absente et non confondue avec l'action suivante, chronologie du journal du lanceur et de la FC, délai de la FC relayée, `--analyse`, arrêt de Godot limité aux descendants, essai simulé sans engine, essai du guide).

