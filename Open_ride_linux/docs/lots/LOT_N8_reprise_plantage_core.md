# Lot N8 – Reprise d'une séance après un plantage du core

## 1. Objectif

Aujourd'hui, si le core plante, le lanceur `openride` arrête Godot et rappelle `openride-core recover` : la séance est sauvée en FIT mais **terminée**. La SRS demande que la séance ne se perde jamais. Ce lot fait relancer le core par le lanceur, qui reprend la séance à partir de son journal (temps, distance, position, braquet, bloc ERG), en pause, et l'engine (resté ouvert) la rattrape au `hello` suivant. Le FIT final contient toute la séance.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/contracts/ipc_v1.md` §6 (pannes) en v1.1 (valeur `core_restarted`, lot N1 §4.5).
2. `docs/lots/LOT_K6_lanceur_unique.md`, `docs/lots/LOT_M8_journal_lanceur.md`, `docs/lots/LOT_C_core_conformite.md` (reprise après `recording_failed`).
3. Code : `core/src/openride_core/launcher.py` (`Supervisor`), `core/src/openride_core/session.py`, `core/src/openride_core/recorder.py`, `core/src/openride_core/journal.py`, `core/src/openride_core/__main__.py` (`run`, `recover`).

## 3. Prérequis

- Lot N1 fusionné (valeur `core_restarted`) : **bloqué** jusque-là.
- Lots M4 et M8 (PR #90 et #96) et PR #91 : fusionnés le 24 octobre, partir de `main` à jour (ils ont modifié `journal.py`, `recorder.py`, `session.py` et `launcher.py`).

## 4. Travail demandé

- `openride-core run --resume JOURNAL` : relit le `.jsonl` (lignes tronquées tolérées, comme `recover`), restaure `t`, `s`, la vitesse nulle, le braquet, le mode, l'entraînement et le bloc ERG (temps écoulé dans le bloc), puis ouvre la séance en `PAUSED` avec `pause_reason` = `core_restarted`. Le journal continue **dans le même fichier** (événement `resume_after_crash` avec l'heure).
- Lanceur : si le core sort avec un code d'erreur pendant une séance (journal ouvert et non terminé), il le relance avec `--resume` et les mêmes options, au plus 3 fois en 10 min (même règle que pour Godot) ; au-delà, comportement actuel (`recover`). Godot n'est plus arrêté pendant la relance.
- Le trainer est relâché (pente 0 %) avant la relance, par `release-trainer` si le core n'a pas pu le faire.
- Le FIT final porte une seule séance, avec une pause à l'endroit du plantage.

## 5. Fichiers concernés

- **Modifiés :** `launcher.py`, `session.py`, `recorder.py`, `__main__.py` (option `--resume`), `core/tests/test_launcher.py`, `README.md` et `CLAUDE.md` (option citée), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Nouveaux :** `core/src/openride_core/resume.py` (lecture de l'état à reprendre), `core/tests/test_resume.py`.
- **Interdits :** l'engine, le contrat (sauf erreur signalée).

## 6. Modifications de contrat autorisées

Aucune : `core_restarted` est ajouté par le lot N1.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Séance simulée (`--trainer sim`) de 10 min en temps accéléré, core tué (`SIGKILL`) à 6 min : relance automatique, séance en `PAUSED` / `core_restarted`, `t` et `s` à moins d'une seconde et de 10 m de la dernière ligne du journal ; après `resume` et 4 min, le FIT a une durée chronométrée de 10 min à 2 s près et une seule session.
3. Même essai en ERG : même bloc, temps restant du bloc à 1 s près, biais conservé.
4. Quatre plantages en 10 min : pas de quatrième relance, `recover` appelé, message clair dans le journal du lanceur.
5. Journal tronqué au milieu d'une ligne : reprise sur la dernière ligne complète.
6. Plantage hors séance (`IDLE`) : relance simple sans `--resume`.

**Sur le PC cible (Laurent) :** tuer le core pendant une vraie séance (`pkill -9 -f openride-core`) et vérifier la reprise, puis l'import du FIT.

## 8. Hors périmètre

- Reprise après un redémarrage complet du PC.
- Affichage du message de reprise dans l'engine (N6).
