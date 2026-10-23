# Lot J1 – Lancer une séance sur un parcours et un entraînement choisis

## 1. Objectif

Aujourd'hui, `openride-core run --autostart` charge toujours le parcours `demo`, et rien ne permet de choisir un entraînement `.zwo` : l'engine n'envoie jamais `select_route` ni `select_workout`, et la ligne de commande n'a pas d'option pour le faire (audit J du 23 octobre, constat J-M1). Conséquences :
- les parcours compilés par `openride-compiler build` ne peuvent pas être roulés ;
- l'essai ERG sur le Victory (critère 11 du lot F) ne peut pas être lancé.

Ce lot ajoute deux options à `openride-core run`, en attendant le menu du lot G.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/contracts/ipc_v1.md` §4 (`select_route`, `select_workout`, `start`) et §7 (séquence d'une séance).
3. `docs/SRS_v1.1.md` §6 (ERG) et §11 (dossiers `~/OpenRide/Workouts/`, `~/.local/share/openride/routes/`).
4. Code : `core/src/openride_core/__main__.py` (`cmd_run`), `core/src/openride_core/session.py` (`CoreSession.run`, `_on_command`, `_select_route`, `_select_workout`), `core/src/openride_core/workout.py` (`workout_path`), `core/src/openride_core/catalog.py`, `scripts/openride-dev.sh`.
5. Tests existants : `core/tests/test_drivers_session.py`, `core/tests/test_workout.py`.

## 3. Prérequis

Aucun. Partir de `main` à jour.

## 4. Travail demandé

- `openride-core run` gagne :
  - `--route ID` : identifiant du parcours (`<routes>/<ID>.world`) ; défaut `demo` ;
  - `--workout ID` : entraînement `~/OpenRide/Workouts/<ID>.zwo` à sélectionner avant `start` ; absent = SIM.
- `CoreSession.run(autostart, route_id="demo", workout_id=None)` : avec `autostart`, la séquence est `select_route(route_id)`, puis `select_workout(workout_id)` s'il est donné, puis `start`, en passant par `_on_command` comme aujourd'hui (même chemin que l'engine).
- **Erreurs :** un parcours introuvable ou invalide, ou un entraînement invalide, donne un message clair dans le journal et **un code de sortie 1 sans lancer la boucle** (pas de séance démarrée sur le mauvais parcours). Le contrôle se fait avant d'ouvrir les ports IPC.
- Sans `--autostart`, `--route` et `--workout` sont refusés par `argparse` avec un message en français (rien ne les utiliserait).
- `scripts/openride-dev.sh` transmet déjà tous les arguments au core : vérifier, et ajouter un exemple dans son en-tête.
- Documentation : `README.md` et `CLAUDE.md` (commandes), en-tête de `__main__.py`.

## 5. Fichiers concernés

- **Nouveau :** `core/tests/test_run_cli.py`.
- **Modifiés :** `core/src/openride_core/__main__.py`, `core/src/openride_core/session.py` (signature de `run` et autostart seulement), `scripts/openride-dev.sh` (commentaire), `README.md`, `CLAUDE.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune. Les commandes IPC utilisées existent déjà.

## 7. Critères d'acceptation

1. `cd core && pytest -q` passe en entier.
2. Un test lance `CoreSession` (MockDriver, `routes_root=tmp_path / "routes"`, `workouts_dir` temporaire, `fit_export.ACTIVITIES_DIR` redirigé) avec un `.world` synthétique (`tools/fake_world.py` ou `demo_world.py`) et `route_id` différent de `demo` : la première trame `state` a ce `route_id`, `session_state` = `RUNNING` et `route_length_m` égale à la longueur du parcours.
3. Avec `workout_id` d'un `.zwo` de `core/workouts/` copié dans le dossier temporaire : `mode` = `ERG` et `erg.workout_name` renseigné dès le début.
4. Parcours inexistant ou `.zwo` invalide : `main(["run", "--trainer", "mock", "--input", "none", "--autostart", "--route", "inexistant"])` renvoie 1, sans socket ouvert (vérifier qu'aucun port n'est lié, ou que `IpcServer.start` n'est pas appelé).
5. `--route X` sans `--autostart` : erreur `argparse` (code 2) avec un message en français.
6. Le test de cohérence `test_docs_coherence.py` accepte les nouvelles options citées dans `README.md` et `CLAUDE.md`.

## 8. Hors périmètre

- Menu de choix dans l'engine et messages IPC de liste (lot G, décision de Laurent).
- Modification de l'engine Godot.

## 9. Essais à faire sur le matériel (propriétaire)

- `scripts/openride-dev.sh --trainer ftms --input click --autostart --workout sweet_spot_3x10` après `python -m openride_core.tools.workouts install` : critère 11 du lot F.
- `scripts/openride-dev.sh --trainer ftms --input click --autostart --route <parcours compilé>`.
