# Lot K6 – Lanceur unique `openride` et supervision

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Lanceur unique `openride` : core et Godot supervisés, arrêt propre | Python | — | Petite | **Livré le 23 octobre** (fait directement ; cahier rédigé le 24 octobre) |

Cahier rédigé après coup (vérification du 24 octobre, constat S1) : le lot a été fait directement le 23 octobre, sans cahier préalable. Il décrit ce qui a été livré, pour que l'index des lots reste complet.

## 1. Objectif

Remplacer, pour l'usage courant, `scripts/openride-dev.sh` par une commande Python installée avec le core, `openride [options de openride-core run]`, qui lance le core puis Godot et **supervise** les deux programmes : un plantage de l'un ne doit laisser ni processus orphelin ni trainer réservé.

## 2. À lire

1. `docs/SRS_v1.1.md` (cycle de vie de la séance) et `docs/contracts/ipc_v1.md` (ports, `hello`, `shutdown`).
2. `scripts/openride-dev.sh` (comportement de référence).
3. Code : `core/src/openride_core/__main__.py` (`run`, `recover`, `release-trainer`), `core/src/openride_core/config.py` (ports IPC, chemin de Godot).

## 3. Prérequis

Aucun.

## 4. Travail demandé

- Lancer le core (journal dans `~/run_trainer.log`), puis Godot avec les ports de la configuration, comme `openride-dev.sh`.
- Fermeture normale de Godot : SIGINT au core, 10 s au plus, puis SIGKILL et `openride-core release-trainer`.
- Godot qui plante : relancé jusqu'à 3 fois en 2 minutes (la séance reste en pause), puis abandon.
- Core qui plante : Godot arrêté, rappel de `openride-core recover`.
- SIGINT, SIGTERM et SIGHUP reçus par le lanceur : même arrêt propre.
- Les commandes lancées sont des paramètres, pour que les tests utilisent de faux programmes.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/launcher.py`, `core/tests/test_launcher.py`.
- **Modifiés :** `core/pyproject.toml` (point d'entrée `openride`), `scripts/openride-dev.sh` (renvoi vers `openride`), `README.md`, `CLAUDE.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Chaque cas du §4 a son test, avec de faux programmes ; aucun processus ne reste orphelin à la fin d'un test.
3. Une configuration invalide donne un message lisible et un code de sortie non nul.

## 8. Hors périmètre

- Icône et fichier `.desktop`.
- Menus pilotés au Click (lot G).

## 9. Livraison (23 octobre 2026, fait directement, commit `ab2ca62`)

- `launcher.py` livré avec le point d'entrée `openride` ; `openride-dev.sh` est conservé.
- Tests : `core/tests/test_launcher.py`, 11 tests (fermeture normale, core qui ignore SIGINT puis libération du trainer, Godot relancé deux fois, abandon au quatrième plantage, fenêtre glissante des plantages, plantage du core en cours de séance et au démarrage, SIGINT/SIGTERM/SIGHUP, lecture de la configuration et chemins, configuration invalide).
- Reste à faire sur le matériel : essai réel avec le HomeTrainer et Godot. À faire ensuite : icône et fichier `.desktop`.
