# Lot R24 (R-gel) – Monde classique gelé pendant une run Cyber-Rogue

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Monde classique gelé pendant toute la run Cyber-Rogue, pause comprise : plus de parcours de démo chargé sous la scène du mode | GDScript, Python (banc) | R22, #897 | Petite | En revue, **version 2.0** |

## 1. Constat

Passes PC r842b et r842c du 12 novembre (`rogue_galerie --native --probe --speed 4`, lot R22) : images de 137 à 146 ms
en medium et high. La plus nette tombe vers 104-107 s : route (23-26 ms), puis arbres proches (92-131 ms) et tuiles
lointaines, c'est-à-dire un chargement du monde classique pendant la run. Une autre tombe à la sortie, à 5 000 m.

## 2. Cause

`main.gd` charge la démo en fond des menus quand la trame n'a pas de parcours (lot N6) : « pas de parcours et menu
affiché ». En mode ROGUE, `state.route_id` est toujours nul (contrat IPC), et l'écran de **pause** de la run est un
menu : chaque pause demandait la démo, et `_poll_route_job` la construisait en entier (`streamer.set_world`, tuiles,
arbres, OSM, horizon) sous la scène du mode, cachée mais payée. Depuis #897 (décor vidé au départ de la run), le
monde est vide au départ, mais la pause le reconstruisait quand même.

Confirmé dans le cloud (banc `rogue_bench.py`, low) sur main : `route_loaded id=demo` au journal de l'engine juste
après la capture de la pause.

Deux autres chemins pouvaient reconstruire le décor pendant la run : un thème ou un biome changés dans les réglages
de la pause (`_apply_theme`, `_apply_biome`) relançaient `streamer.set_world` sur l'ancien parcours.

## 3. Travail

Règle unique : **pendant une run (scène du mode présente), aucun parcours classique**. Le décor vidé au départ
(#897) reste vide jusqu'à la sortie de la scène, puis le parcours du menu est rechargé, comme tout changement de
parcours.

- `rogue_host.gd` : `classic_route_id(route_id, menu_shown, run_active, demo_id)`, fonction pure qui décide du parcours
  classique voulu pour la trame (démo des menus hors run seulement, rien pendant la run).
- `main.gd` : la trame passe par cette fonction ; thème et biome ne reconstruisent le décor que si un parcours est
  affiché (`_route_loaded_id`) ; lignes de test `route_requested` et `rogue_scene_left`.
- `rogue_bench.py` : nouvelle vérification « monde classique gelé pendant la run (pause comprise) » : aucun
  `route_requested` ni `route_loaded` entre `route_world_released` et `rogue_scene_left`.

Hors périmètre : les images lentes aux changements de salle (cause « inconnue », ~140 ms en medium à r842b) et
celle de la sortie à 5 000 m. Celle-ci vient du banc lui-même : en `--test-mode`, la caméra des menus est coupée et
suit `s` de la trame (5 000 m) sur la démo rechargée ; dans le jeu, le bilan recharge la démo autour de son départ.
La passe PC dira si les images lentes de salle restent.

## 4. Tests

- `engine/tests/unit/test_rogue_host.gd` : `classic_route_id` (menu, séance, run, pause de run).
- `core/tests/test_rogue_bench_gel.py` : lecture du journal par le banc.
- Banc `rogue_bench.py` dans le cloud (Xvfb, Vulkan logiciel) : avant, démo chargée à la pause ; après, 170/170 en
  low, aucun parcours demandé ni chargé avant la sortie de la scène.
- À faire sur le PC : `rogue_galerie --native --probe --speed 4` en low, medium et high (budgets GPU 8, 13 et 16 ms ;
  pire image et images lentes comparées à r842c).

## 5. Livraison

PR à venir sur la branche `claude/project-thread-siecmy`.
