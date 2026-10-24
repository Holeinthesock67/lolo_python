# Lot M5 – Rejouer une panne réelle : scénario de simulation tiré de `run_trainer.log`

## 1. Objectif

Le Bluetooth simulé (PR #74) rejoue des pannes écrites à la main. Quand une panne arrive sur le vélo (coupure du Click, erreur 0x80, trainer muet), il faut aujourd'hui relire le journal et recopier les temps dans un scénario JSON. Ce lot ajoute un outil qui **convertit un journal du core en scénario** de simulation : la même suite de connexions, coupures, erreurs et appuis, rejouable sans matériel et utilisable comme test de non-régression.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/SIMULATION_BLE.md` (format des scénarios, actions, réglages).
2. `docs/lots/LOT_H6_analyse_journal.md` et `docs/lots/LOT_K8_diagnostic_click.md` (lignes du journal et leur sens).
3. Code : `core/src/openride_core/tools/log_report.py` (expressions `PATTERNS`, découpage en séances `_split_sessions`, horodatages), `core/src/openride_core/sim_scenarios.py` (`validate`, `load_scenario`, `SCENARIOS`), `core/src/openride_core/ble_sim.py` (`build_world`).
4. Tests : `core/tests/test_log_report.py` (journaux d'exemple), `core/tests/data/`.

## 3. Prérequis

Aucun.

## 4. Travail demandé

- `python -m openride_core.tools.log_scenario [JOURNAL] [-o scenario.json] [--session N] [--from S] [--to S]` (défaut : `~/run_trainer.log`, dernière séance) :
  - temps du scénario = secondes depuis la ligne de démarrage du core de la séance choisie ; `--from` et `--to` découpent une fenêtre (temps recalés à partir de `--from`) ;
  - correspondances au minimum : trainer connecté (`appear_at` à la première connexion), coupure du trainer ou « plus de données » (`drop`, ou `silence` si le journal montre des données qui manquent sans coupure), commande refusée (`refuse_control` ou `att_error` avec le code lu), contrôle perdu 0xFF (`control_lost`), Click connecté et coupé par boîtier (adresse `…E7` = `click_plus`, sinon `click_minus`, comme `log_report`), appuis du Click quand le journal les porte (`press` avec le bouton), ceinture connectée et coupée ;
  - ce qui n'a pas d'équivalent (pause demandée, perf de la boucle) est ignoré et compté dans un résumé imprimé sur la sortie d'erreur ;
  - le scénario écrit passe `validate` ; une clé `"source"` (chemin, séance, fenêtre) est ajoutée **seulement** si `validate` l'accepte, sinon elle va dans le résumé.
- Réutiliser les expressions de `log_report.py` en les important (pas de copie) ; si une ligne utile n'y est pas, l'ajouter dans le nouveau module avec un test qui la vérifie contre la chaîne du code source, comme le fait `CORE_FORMAT_STRINGS`.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/tools/log_scenario.py`, `core/tests/test_log_scenario.py`, un journal d'exemple dans `core/tests/data/` si ceux qui existent ne suffisent pas.
- **Modifiés :** `docs/SIMULATION_BLE.md` (section « Rejouer une panne vue sur le vélo »), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `log_report.py`, `sim_scenarios.py`, `ble_sim.py` (lecture seule ; un manque du format de scénario est signalé dans le rapport, pas contourné).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Aller-retour : une séance `CoreSession` jouée avec le scénario `coupures` produit un journal ; l'outil en tire un scénario dont les événements `drop` et `control_lost` tombent à ± 1,5 s de ceux de `coupures`.
3. Journal d'exemple réel (`core/tests/data/`) avec deux boîtiers du Click : les coupures sont attribuées au bon boîtier.
4. Le scénario produit se charge par `--sim-scenario FICHIER` et une séance de 20 s s'y déroule sans exception.
5. `--from` / `--to` : seuls les événements de la fenêtre sont gardés, temps recalés.
6. Journal sans séance ou illisible : message clair et code de sortie 1, jamais de trace Python.

**Sur le PC cible (le propriétaire) :** après la prochaine coupure réelle, `python -m openride_core.tools.log_scenario -o ~/panne.json`, puis `scripts/openride-dev.sh --trainer sim --input sim --hr sim --sim-scenario ~/panne.json --autostart`.

## 8. Hors périmètre

- Rejouer la puissance ou la cadence mesurées (c'est le rôle de `--replay`, lot H3).
- Sous-commande de `openride-core` (ce module suffit ; à ajouter plus tard si utile).
