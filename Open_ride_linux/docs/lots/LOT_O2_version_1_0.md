# Lot O2 – Numéro de version unique et notes de version

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Numéro de version unique (`VERSION`) et notes de version (`CHANGELOG.md`) | Python + GDScript | N3 ; de préférence fin de J4 | Petite | **Livré le 26 octobre** (issue #120) |

## 1. Objectif

Le core, le compilateur et l'engine affichent tous `0.1.0`, chacun dans son fichier, et aucune note de version n'existe. Pour publier une 1.0, il faut **un seul numéro** connu des trois programmes, visible par le propriétaire (ligne de commande, journal, menu) et un fichier `CHANGELOG.md` qui dit ce que contient chaque version. Ce lot met en place le mécanisme ; le passage effectif à `1.0.0` et l'étiquette Git se font à la recette finale (lot O8).

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md` §1 (contenu livré), `docs/lots/LOT_J4_paquetage_autonome.md`.
2. Code : `core/src/openride_core/__init__.py` et `compiler/src/openride_compiler/__init__.py` (`__version__`), `core/pyproject.toml`, `compiler/pyproject.toml`, `engine/project.godot` (`config/version`), `core/src/openride_core/__main__.py` (`--version`), `core/src/openride_core/launcher.py`, `core/src/openride_core/ipc_server.py` (`hello_ack.core_version`), `engine/scripts/ipc_client.gd` (`hello.engine_version`), `docs/contracts/ipc_v1.md` §5, `core/tests/test_docs_coherence.py`.

## 3. Prérequis

Après N3 (qui est seul à modifier `ipc_client.gd` dans la série N) et de préférence après la fin de J4 (issue #50), qui touche aussi les `pyproject.toml`.

## 4. Travail demandé

- **Source unique :** fichier `VERSION` à la racine de `Open_ride_linux/` (une ligne, `0.9.0` dans ce lot). Les deux `pyproject.toml` lisent la version de façon dynamique (ou un test vérifie l'égalité), `__version__` des deux paquets la reprend (`importlib.metadata`, repli sur le fichier en mode éditable), `engine/project.godot` porte la même valeur.
- **Test de cohérence** (`core/tests/test_version.py`) : les quatre valeurs sont égales, au format `MAJEUR.MINEUR.CORRECTIF`, et la première section de `CHANGELOG.md` porte ce numéro ou « Non publiée ».
- **Script** `scripts/bump-version.sh X.Y.Z` : met à jour `VERSION`, `project.godot` et la première section du `CHANGELOG.md` (date du jour), sans commit ni étiquette.
- **Affichage :** `openride --version`, `openride-core --version` et `openride-compiler --version` ; première ligne du journal du lanceur (`[openride] OpenRide 0.9.0`) ; `hello_ack.core_version` et `hello.engine_version` (champs déjà prévus par le contrat) portent ce numéro au lieu d'une valeur écrite en dur ; l'engine lit la sienne dans `ProjectSettings` (`application/config/version`).
- **`CHANGELOG.md`** (format « Keep a Changelog », en français) : section `0.9.0 – Non publiée` qui résume par grands thèmes ce que contient `main` (séance SIM et ERG, Click, compilateur GPX/FIT/TCX, rendu E1 à E4, lanceur, journal, outils), à partir de `docs/SUIVI_AVANCEMENT.md` §1 ; sections suivantes vides.
- Mettre à jour `README.md` (où lire la version, comment la changer) et `CLAUDE.md` si les commandes y sont listées.

## 5. Fichiers concernés

- **Nouveaux :** `VERSION`, `CHANGELOG.md`, `scripts/bump-version.sh`, `core/tests/test_version.py`.
- **Modifiés :** `core/pyproject.toml`, `compiler/pyproject.toml`, les deux `__init__.py`, `ipc_server.py`, `ipc_client.gd`, `compiler/src/openride_compiler/cli.py` (`--version`), `core/src/openride_core/launcher.py`, `engine/project.godot`, `README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** le contrat IPC, `main.gd`, `.github/workflows/` (sauf si un chemin de fichier doit y être ajouté).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/` et `compiler/`, ainsi que `engine/tests/run_engine_tests.sh`.
2. `pip install .` (hors mode éditable, dans un environnement neuf) puis `openride-core --version` et `openride-compiler --version` affichent `0.9.0`.
3. Changer une seule des quatre valeurs fait échouer `test_version.py` avec un message qui nomme le fichier.
4. `scripts/bump-version.sh 1.0.0` dans une copie temporaire met à jour les trois fichiers et le test passe ; un argument mal formé est refusé.
5. Le journal du lanceur commence par la ligne de version ; dans `engine/tests/run_e2e.sh`, `hello` et `hello_ack` portent tous deux `0.9.0`.

## 8. Hors périmètre

- Publication (étiquette Git, release GitHub) : lot O8, par le propriétaire.
- Affichage de la version dans le menu : lot O4 (écran des réglages).

## 9. Livraison

Livré le 26 octobre 2026 (issue #120), thread « Développer les lots O restants ».

- `VERSION` (`0.9.0`) fait foi. Les `pyproject.toml` gardent une version écrite (setuptools refuse de lire un fichier hors du dossier du paquet) : `core/tests/test_version.py` exige l'égalité et `bump-version.sh` les met à jour aussi.
- `__version__` des deux paquets : le fichier `VERSION` quand le paquet tourne depuis le dépôt (mode éditable), sinon `importlib.metadata`.
- `hello_ack.core_version` = `__version__` ; l'engine lit `application/config/version` dans `ProjectSettings` (variable `engine_version` de `ipc_client.gd`, qui remplace la constante `ENGINE_VERSION`).
- `openride --version`, `openride-core --version`, `openride-compiler --version` affichent « programme 0.9.0 » ; première ligne du journal du lanceur : `[openride] OpenRide 0.9.0`, avec ou sans rotation.
- `CHANGELOG.md`, `scripts/bump-version.sh` (refuse un numéro mal formé, code 2), section « Version » du `README.md`.
- Tests : `core/tests/test_version.py` (14) et première ligne du journal dans `test_launcher.py`. À vérifier sur le PC : `run_engine_tests.sh` et `run_e2e.sh` (Godot absent du conteneur cloud).
