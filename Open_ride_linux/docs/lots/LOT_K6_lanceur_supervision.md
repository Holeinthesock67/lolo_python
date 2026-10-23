# Lot K6 – Lanceur unique `openride` et supervision des deux programmes

## 1. Objectif

Remplacer, à terme, `scripts/openride-dev.sh` par une commande Python `openride` (SRS §3 et lot G : « lanceur unique, qui arrête tout à la fermeture de la fenêtre ; supervision : relance du core ou de l'engine sans perdre la séance »). Le lanceur ne dépend pas du futur contrat v1.1 : il démarre, surveille et arrête deux processus.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/SRS_v1.1.md` §3 (architecture), §9 (données sûres) ; `docs/contracts/ipc_v1.md` §5 et §6 (`hello`, `shutdown`, perte de l'engine).
3. Code : `scripts/openride-dev.sh` (comportement de référence, y compris l'arrêt forcé au bout de 10 s puis `openride-core release-trainer`, PR #28), `core/src/openride_core/__main__.py`, `core/src/openride_core/config.py` (ports, `ConfigError`), `core/src/openride_core/session.py` (`_shutdown`).

## 3. Prérequis

Aucun. Partir de `main` à jour. Si J1 est livré, transmettre aussi `--route` et `--workout`.

## 4. Travail demandé

- Nouveau module `core/src/openride_core/launcher.py` et commande `openride` (`[project.scripts]` du core).
- `openride [options du core]` : lit la configuration (erreur lisible si invalide), lance `openride-core run …` puis l'engine (`GODOT`, `--path engine`, ports de la configuration), journal du core dans `~/run_victory.log` comme aujourd'hui.
- **Supervision :**
  - l'engine se ferme normalement → arrêt propre du core (SIGINT), attente de 10 s au plus, puis SIGKILL et `openride-core release-trainer` ;
  - l'engine plante (code ≠ 0) → il est relancé jusqu'à 3 fois en 2 minutes ; la séance continue côté core (pause `engine_lost`, contrat §6) ;
  - le core plante → message clair, arrêt de l'engine, rappel de `openride-core recover` ;
  - SIGINT, SIGTERM, SIGHUP reçus par le lanceur → même arrêt propre.
- Chemins des exécutables passés par paramètres, pour que les tests remplacent core et engine par de **faux programmes** Python (qui dorment, quittent avec un code donné, ignorent SIGINT…).
- `scripts/openride-dev.sh` reste en place ; une ligne de son en-tête renvoie vers `openride`.
- Hors de ce lot : icône et fichier `.desktop` (une section « À faire » dans le rapport suffit).

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/launcher.py`, `core/tests/test_launcher.py`.
- **Modifiés :** `core/pyproject.toml` (`[project.scripts]`), `README.md` et `CLAUDE.md` (commande), `scripts/openride-dev.sh` (commentaire), `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `cd core && pytest -q` passe en entier ; les tests du lanceur durent moins de 20 s au total.
2. Avec de faux programmes : fermeture normale de l'engine → le faux core reçoit SIGINT et le lanceur rend 0.
3. Faux core qui ignore SIGINT → SIGKILL au bout du délai (réduit pour le test) et appel de la commande de libération du trainer (faux également).
4. Faux engine qui plante 2 fois puis tient → 2 relances ; qui plante 4 fois en 2 minutes → abandon, arrêt propre du core, code ≠ 0.
5. Faux core qui plante → l'engine est arrêté, le message cite `openride-core recover`.
6. SIGHUP envoyé au lanceur → arrêt propre des deux faux programmes.
7. Aucun processus orphelin à la fin de chaque test (vérifié par PID).

## 8. Hors périmètre

- Menus (G, K5), icône de bureau, paquet.
- Essai réel avec le Victory et Godot (propriétaire, à lister dans le rapport).
