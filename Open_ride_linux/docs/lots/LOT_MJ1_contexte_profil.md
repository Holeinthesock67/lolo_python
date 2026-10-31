# Lot MJ1 – Contexte de profil dans le core

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série MJ : contexte de profil dans le core (`profiles.py`), fin des chemins figés, `--profil`, verrou ; sans profil, chemins d'aujourd'hui | Python | — | Moyenne | **Livré le 29 octobre** (branche `claude/project-thread-grv91v-mj1`) |

Série MJ (profils de joueurs et profil d'essai, version 2.0), plan `docs/2.0/PLAN_SERIE_MJ.md`. Demande du propriétaire du 29 octobre 2026 ; étude et maquettes validées le même jour.

## 1. Objectif

Aujourd'hui, les fichiers propres au joueur (`profile.json`, `records.json`, `plan_state.toml`, `Activities/` et ses journaux, caches de l'historique et des puissances) sont à des chemins fixes de `~/OpenRide/`, calculés à l'import des modules ou figés dans les valeurs par défaut des fonctions. Ce lot les remplace par un **contexte de profil** lu au moment de l'appel : un seul objet dit où sont les fichiers du joueur en cours. Sans profil choisi, le contexte reprend exactement les chemins d'aujourd'hui : **aucun changement visible**.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_MJ.md` §1 (constats), §2.1 (arborescence), §3.1 et §4.4 (verrou).
2. Code : `config.py`, `profile.py`, `records.py`, `plans.py`, `journal.py`, `fit_export.py`, `progression.py`, `garage.py`, `session.py`, `launcher.py`, `__main__.py`, `ftp_test.py`, `open_world_save.py`, `tools/xp.py`, `tools/history.py`, `tools/estimate_cp.py`, `tools/recette_v10.py`.

## 3. Prérequis

Aucun.

## 4. Travail demandé

- **Module `profiles.py`** : `ProfileContext` (identifiant, type, dossier racine et chemins dérivés : `profile_path`, `records_path`, `plan_state_path`, `activities_dir`, `journal_dir`, `history_cache`, `mmp_cache`, `lock_path`, table de progression propre au profil si elle existe). `current()` renvoie le contexte actif, `activate()` le change, `for_id()` construit celui d'un profil de `~/OpenRide/Profils/<id>/`.
- **Contexte historique** : sans profil choisi, `current()` reprend les constantes d'aujourd'hui, lues à l'appel (`fit_export.ACTIVITIES_DIR`, `journal.JOURNAL_DIR`, `profile.PROFILE_PATH`, `records.RECORDS_FILE`, `plans.STATE_PATH`, `progression.USER_TABLE_PATH`, caches de `tools/history.py` et `tools/estimate_cp.py`). Les tests qui redirigent ces constantes continuent de marcher.
- **Plus de chemin figé** : toute valeur par défaut d'un chemin de joueur se résout à l'appel par `profiles.current()` (FIT, dernier journal, profil V4, records, plan actif, progression, historique, CP, test de FTP, balade du monde ouvert, reprise du lanceur, recette V10).
- **`--profil ID`** sur toutes les sous-commandes d'`openride-core`, et variable `OPENRIDE_PROFIL` ; le lanceur `openride` transmet `--profil` au core et l'utilise pour la reprise après plantage (`recover`, journal non terminé). Identifiant : minuscules, chiffres et tirets, 1 à 32 caractères, ou `_essai` (lot MJ2) ; sinon erreur lisible, code 2.
- **Verrou** `Profils/<id>/.verrou` (`fcntl.flock`) pris par `openride-core run` pour un profil nommé : une seconde séance sur le même profil est refusée (code 1, message clair) ; un core qui plante rend le verrou de lui-même.

## 5. Fichiers concernés

- **Créés :** `core/src/openride_core/profiles.py`, `core/tests/test_profiles.py`.
- **Modifiés :** les modules du §2, `docs/SUIVI_AVANCEMENT.md`, `docs/lots/00_INDEX.md`, `CLAUDE.md` (module clé).
- **Interdits :** l'engine, le contrat IPC.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe en entier, sans modifier les tests existants autrement que pour une constante déplacée.
2. Sans `--profil`, tous les chemins sont ceux d'avant (test qui compare chaque chemin du contexte historique aux constantes).
3. Avec `--profil cycliste-2`, une séance simulée écrit son journal, son FIT, ses records et son profil V4 sous `Profils/cycliste-2/` et rien ailleurs dans `~/OpenRide/` (hors `Logs/`).
4. `openride-core xp --profil cycliste-2` lit les journaux de ce profil seulement.
5. Deux `run --profil X` simultanés : le second sort avec le code 1.
6. Identifiant refusé (`../x`, majuscules, vide) : code 2.

## 8. Hors périmètre

Profil d'essai (MJ2), `profil.toml` des réglages (MJ4), migration (MJ5), commandes IPC (MJ6, MJ7), écrans (MJ8).

## Livraison

Livré le 29 octobre 2026 (branche `claude/project-thread-grv91v-mj1`, empilée sur MJ0).

- `core/src/openride_core/profiles.py` : `ProfileContext` (`for_id`, `legacy`), `current()`, `activate()`, `resolve()` (option puis `OPENRIDE_PROFIL`), `check_id()`, `ProfileLock` (`fcntl.flock` sur `.verrou`, rendu à la mort du processus).
- Valeurs par défaut résolues à l'appel : `fit_export.default_fit_path`, `journal.latest_journal`, `profile.load_profile`/`peek_profile`/`save_profile`, `RecordBook.load`/`save`, plan actif de `plans.py`, `ProgressionService` (profil V4 et surcharge `progression.toml` du profil si elle existe), `CoreSession` (journaux, records, profil V4), `ftp_test`, `open_world_save`, `tools/xp.py`, `tools/history.py`, `tools/estimate_cp.py`, `tools/recette_v10.py`.
- `--profil ID` ajouté à toutes les sous-commandes d'`openride-core` ; `run` prend le verrou du profil (code 1 si déjà pris). Le lanceur passe `--profil` au core et à `recover`, et cherche les journaux non terminés dans le profil.
- Deux tests redirigeaient `garage.PROFILE_PATH` et `garage.USER_TABLE_PATH` : ils redirigent maintenant `profile.PROFILE_PATH` (le garage ne garde plus de chemin).
- Tests : `core/tests/test_profiles.py`.
