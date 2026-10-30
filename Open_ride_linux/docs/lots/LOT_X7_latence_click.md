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

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x7`, sur X35 pour `sim_bench.py`).

- **Core** : nouveau module `latency_log.py`. Un identifiant par appui à la notification BLE qui le termine (`input_providers.ZwiftClickProvider`, après le filtre du relais par l'autre boîtier), rangé dans une file par fournisseur dans l'ordre de ses événements ; `evenement` quand la séance le lit (`session._drain_inputs`, appui d'identification compris) ; `ipc` à l'envoi de l'événement à l'engine, avec `latence_id` et `latence_t` dans le message `input` ; `cp` à la prochaine écriture au Control Point (`ftms_driver.call`) quand l'appui a changé le braquet ou le biais ERG, attendue au plus 2 s. Heure : heure murale du démarrage plus l'horloge monotone (pas de saut d'horloge pendant la mesure). Activé par `[log] latence = true` ou `openride-core run --latence` ; sinon aucune ligne et aucun champ de plus.
- **Contrat** : `latence_id` et `latence_t` ajoutés à `input.schema.json` et au §6 de `ipc_v1.md`, champs de diagnostic absents en usage normal, sans changement de révision.
- **Engine** : `ipc_client.gd` émet `latency_input_received` ; `main.gd` écrit `recu` à la réception et `affiche` à la première image dessinée (`RenderingServer.frame_post_draw`) après un état dont le braquet, la cible ou le biais ERG diffèrent de ceux de la réception, attendu au plus 2 s. **Écart** : pas d'écart d'horloge mesuré au `hello` : le core et l'engine tournent sur la même machine et lisent la même horloge système.
- **Analyse** : `log_report --latence CORE.log ENGINE.log [--json]` (appariement par identifiant, appuis incomplets et étages manquants comptés à part, médiane, p95, maximum des étages notification → événement, événement → envoi, événement → Control Point, envoi → reçu, reçu → image, et de bout en bout). Un identifiant repart de 1 à chaque lancement du core : analyser les journaux d'un seul lancement.
- **Banc simulé** : `sim_bench.py --latence` (vérifications « appuis appariés de bout en bout » au moins 10, et p95 de bout en bout sous 150 ms, stricte avec `--native`, indicative sous Xvfb ; `latence.json` dans le dossier du scénario). Mesuré dans le conteneur (`--scenario demo --duration 120`, Xvfb) : 19 appuis appariés sur 22 ; notification → événement 17 ms, événement → Control Point 36 ms, envoi → reçu 187 ms et reçu → image 273 ms en médiane (rendu logiciel, une image toutes les 140 ms environ). La mesure qui compte se fait en fenêtre réelle sur le PC.
- Tests : `core/tests/test_latence_click.py` (7 tests : rien sans l'option, une ligne par étage et par appui, attente du Control Point périmée, champs conformes au schéma, clé de configuration, appariement et statistiques de `log_report`, commande).

