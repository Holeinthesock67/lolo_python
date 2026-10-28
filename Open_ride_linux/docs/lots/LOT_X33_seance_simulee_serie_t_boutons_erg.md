# Lot X33 – Séance simulée de la série T et des boutons de l'ERG (T11, J7)

## 1. Objectif

La recette T11 (série T : montée, sprint, arches, bonus Z, records, jingles) et l'essai J7 (boutons de l'ERG au Click et au clavier, lot O17) se font aujourd'hui sur le vélo, puis en lisant les journaux à la main. Le 28 octobre, le propriétaire a demandé que tout ce qui se vérifie sans pédaler sorte de la séance (20 min de vélo au plus) : une séance simulée doit jouer ces étapes et vérifier seule ce que l'écran et les journaux montrent. Il ne reste alors au vélo que le ressenti (effort, son, lisibilité).

## 2. À lire

1. `docs/RECETTE_SERIE_T.md` (T11), `docs/PROTOCOLE_TEST_2026-10-26.md` §J7, `plans/SEANCE_VELO_T11_J7_P27.md` du dossier du projet.
2. `engine/tests/sim_bench.py` (scénarios du banc, `_capture_loop`, `_scenario_checks`), `core/src/openride_core/sim_scenarios.py` (événements `press`).
3. `engine/scripts/key_map.gd` (clavier = Click), `main.gd` (`_on_test_message`, `_unhandled_input`), `core/tests/test_session_serie_t.py` (lignes `powerup` et `segment` du journal).

## 3. Prérequis

PR du banc des menus (messages `key` et `control_file` du Click simulé). T11 et O17 fusionnés (fait). La course contre 4 bots (étape 8 de T11) attend T15, T12 et T13 (#453, #487, #488) : scénario prévu, vérifications activées quand le contrat le permet.

## 4. Travail demandé

- **Touches simulées dans l'engine** : message de test `key` du banc des menus (fil « Tester automatiquement les menus au clic et clavier », branche `claude/project-thread-90nm7t`) : `{"type": "_test", "action": "key", "key": "Z", "shift": false, "hold_ms": 200}`, vrai chemin de Godot (`_unhandled_input`, `key_map.gd`, puis `input_event` vers le core en séance) ; l'engine journalise `[test] key done=…`. Ce lot n'ajoute pas d'autre message.
- **Événements du banc** : une section `inputs` dans les scénarios du banc, à côté de `events` : `{"t": 42, "key": "Z", "hold_ms": 200}` (clavier, message `key`) ou `{"t": 42, "button": "Z", "duration_s": 0.2}` (Click simulé, par le `control_file` du scénario Bluetooth du même fil, chemin Bluetooth complet), joués par `sim_bench.py` au temps voulu, capture juste après.
- **Arches rapprochées** : `bench.powerups` (contenu de `~/OpenRide/powerups.toml` du HOME temporaire), par exemple `{"obtain": {"arch_every_m": 1000, "per_segment": true}}`.
- **Scénarios** :
  - `serie_t` : parcours `demo`, SIM, puissance du cycliste assez forte pour atteindre le sprint en moins de 6 min ; Z joué au Click simulé à chaque arche ; fin de séance par la commande `end_session` après le sprint. Vérifie : lignes `segment` de la montée et du sprint (début, résultat, record) au journal ; au moins une arche et un bonus pris (ligne `powerup`) avec la vitesse qui monte pendant 15 s ; jingle `Events` au journal de l'engine (`[test] event_sound …`) ; écran « Records du parcours » après la fin.
  - `erg_boutons` : `erg_court`, appuis du Click puis des touches : + et − courts (biais ± 2 %), longs (± 10 %), `Page haut`/`Page bas`, Z (bloc suivant), Y puis `Échap` (pause, reprise). Vérifie au journal du core la cible ERG avant et après chaque appui (rapport attendu ± 0,5 point), le changement de bloc, la pause et la reprise, l'absence de ligne `powerup` en ERG.
  - `course_bots` (désactivé tant que T12 n'est pas sur `main`) : 4 bots à profil, encart des deux voisins à l'écran, écarts au journal.
- **Rapport** : une ligne par attente de RECETTE_SERIE_T et de J7, avec le renvoi à l'étape de la recette.

## 5. Fichiers concernés

- **Modifiés :** `engine/tests/sim_bench.py`, `engine/tests/README.md`, `docs/OUTILS_DE_TEST.md`, `docs/RECETTE_SERIE_T.md` et `docs/PROTOCOLE_TEST_2026-10-26.md` (ce que la séance simulée couvre), ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `engine/tests/sim_bench_scenarios/serie_t.json`, `erg_boutons.json`, `course_bots.json` ; `core/tests/test_sim_bench_scenarios.py` (scénarios lisibles, clés connues, vérifications tirées des scénarios sur des journaux fabriqués, cas négatifs).

## 6. Critères d'acceptation

1. `sim_bench.py --scenario serie_t --scenario erg_boutons` sous Xvfb : toutes les vérifications passent sur `main`.
2. Cas négatif : en coupant l'envoi de `input_event` par le clavier (engine modifié pour l'essai), `erg_boutons` échoue sur les appuis du clavier.
3. Suites core et engine vertes.

## 7. Hors périmètre

Le ressenti au vélo (dureté, son, lisibilité), le bloc P27 de la séance B.
