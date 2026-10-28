# Lot X7 – Latence appui Click → commande → écran

## 1. Objectif

Ligne 10 de la recette 1.0 et fenêtres de timing des séries R et T : la latence entre l'appui sur le Click et le changement visible (braquet, biais ERG) n'a jamais été mesurée. Ce lot horodate chaque étage et en fait la statistique.

## 2. À lire

`core/src/openride_core/zwift_click.py` (réception, `PressClassifier`), `session.py` (traitement de l'événement, écriture au Control Point), `ipc_server.py` (événement `input_event` vers l'engine), `engine/scripts/main.gd` (réception de l'événement, mise à jour du HUD), `tools/log_report.py`.

## 3. Travail demandé

- **Journal du core** (niveau DEBUG, activé par `[log] latence = true` ou `--latence`) : une ligne `[latence] id=N etage=notif|evenement|ipc|cp t=…` par étage, avec un identifiant d'appui commun (horloge monotone convertie en heure murale au démarrage).
- **Engine** : en recevant l'événement relayé, puis à la première image dessinée après le changement du HUD, ligne `[latence] id=N etage=recu|affiche t=…` (même horloge : l'engine reçoit l'heure du core dans l'événement et l'écart d'horloge mesuré au `hello`).
- **`log_report --latence CORE.log ENGINE.log`** : médiane, p95 et maximum de chaque étage et de bout en bout (notif → affiché), nombre d'appuis appariés.
- **Sans matériel** : le banc simulé (`sim_bench.py --latence`) active les deux journaux ; une vérification « latence bout en bout p95 < 150 ms » en INFO sous Xvfb (rendu logiciel), stricte avec `--native`.

## 4. Fichiers

- **Modifiés :** `zwift_click.py`, `session.py`, `ipc_server.py`, `config.py` (clé `[log] latence`), `engine/scripts/main.gd`, `tools/log_report.py`, `engine/tests/sim_bench.py`, `docs/SRS_v1.1.md` (clé de configuration), `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `core/tests/test_latence_click.py`.

## 5. Critères d'acceptation

1. Sans l'option, aucune ligne `[latence]` ; avec, une ligne par étage et par appui.
2. `log_report --latence` sur des journaux fabriqués : appariement par `id`, appuis incomplets comptés à part, statistiques justes.
3. Banc simulé : au moins 10 appuis appariés de bout en bout.

## 6. Hors périmètre

Réduire la latence ; le boîtier gauche muet (reporté à la 4.0).
