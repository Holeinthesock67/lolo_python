# Lot O36 – Départ au pédalage, après le chargement

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Départ au pédalage : la séance attend le décor du départ, le trainer et quelques secondes de pédalage avant de lancer chrono, distance, ERG et bots ; réglable dans « Réglages › Séance » | Python + GDScript | N6, O3 | Petite | Demande du propriétaire du 31 octobre ; en PR |

## 1. Objectif

Demande du propriétaire du 31 octobre : « des critères de démarrage moins stricts et laisser le temps au jeu de se lancer et charger avant de commencer à vraiment pédaler ».

Constat sur les journaux du PC du 30 octobre (recette 1.0, lancement `--autostart`) : il n'y avait aucun critère, `start` passait en `RUNNING` à l'instant. Le chrono tournait 2 s avant la connexion du trainer, 4 s avant celle de l'engine et 7 s avant l'affichage du parcours. Depuis le menu, « Démarrer » lançait aussi la séance avant que le décor autour du départ soit construit et avant le premier coup de pédale.

## 2. Spécification

| # | Règle |
| --- | --- |
| O36-1 | `[depart] mode = "pedalage"` (défaut) : après `start` (menu ou `--autostart`), le core reste en `READY`, avec l'objet `start_wait` dans `state`. Chrono, distance, ERG, bots, segments et journal ne partent qu'à l'ouverture du départ. Le trainer reste libre (pente 0 %) et les mesures (puissance, cadence, FC) sont affichées. |
| O36-2 | Trois étapes, dans l'ordre : **décor** (l'engine envoie `scene_ready` pour le parcours en cours : parcours chargé, aucune tuile voulue en attente, 10 images de suite sous 33 ms ; au plus `attente_decor_s` = 60 s si l'engine ne l'envoie jamais), **trainer** (mesures reçues), **pédalage** (`duree_s` = 3 s cumulées à `cadence_rpm` = 30 tr/min ou plus, 40 W sans cadence). |
| O36-3 | Tolérance : un à-coup sous le seuil de moins de 2 s ne remet pas le compte à zéro ; au-delà, le compte redescend aussi vite qu'il monte. Engine perdu ou trainer perdu pendant l'attente : l'étape retombe, le compte repart de zéro. |
| O36-4 | Pendant l'attente, le menu est masqué et l'écran « START YOUR ENGINES » s'affiche (demande du propriétaire du 31 octobre, `start_screen.gd`, dessiné par le code) : bandes de damier, cinq feux de départ (1 allumé pour le décor, 2 pour le trainer, 3 à 5 avec le pédalage), barre du pédalage, cadence mesurée, étape (« Départ : chargement du décor… », « Départ : connexion du trainer… », « Pédale pour partir : 30 tr/min, 1,2 s sur 3 s ») et « Y : annuler ». Voile opaque pendant le chargement, plus léger pendant le pédalage ; feux verts « GO ! » 1,2 s au départ. Y (Click ou clavier), `pause`, `end_session`, `select_workout`, `start_run`, `start_open_world` et `select_profile` annulent l'attente : retour à l'écran Prêt. |
| O36-5 | `[depart] mode = "immediat"` : `start` passe en `RUNNING` tout de suite, comme avant. `openride-core run --depart immediat|pedalage` remplace le réglage ; les essais sans engine ni cycliste (`gigue_charge`, `coupures`) passent `--depart immediat`. |
| O36-6 | Menu « Réglages › Séance » : **Départ** (au pédalage ou immédiat) et **Cadence de départ** (10 à 90 tr/min, pas de 5). `duree_s` (0 à 10 s) et `attente_decor_s` (0 à 600 s) restent dans `config.toml`. Réglages du profil de joueur (`config.PROFILE_KEYS`). |

## 3. Contrat

`docs/contracts/ipc_v1.md`, révision 1.5 (ajouts compatibles) : objet facultatif `start_wait` `{phase, cadence_rpm, hold_s, held_s, waited_s}` de `state`, commande `scene_ready {route_id}`, réglages `depart.mode` et `depart.cadence_rpm` de `settings`. Schémas `state` et `cmd` mis à jour. Un engine plus ancien n'envoie pas `scene_ready` : le départ attend alors `attente_decor_s` secondes au plus, puis le pédalage.

## 4. Fichiers

- Core : `start_gate.py` (nouveau, module pur), `session.py` (attente en `READY`, `scene_ready`, annulation), `config.py` (`[depart]`), `settings.py`, `ipc_server.py` (`start_wait`), `__main__.py` (`--depart`), outils `gigue_charge.py` et `coupures.py`.
- Engine : `start_wait_model.gd` (nouveau, décor prêt, feux et textes), `start_screen.gd` (nouveau, écran « Start your engines »), `main.gd`, `menu_flow.gd` (menu masqué pendant l'attente), `settings_view_model.gd`.
- Tests : `core/tests/test_start_gate.py`, `engine/tests/unit/test_start_wait_model.gd` ; `conftest.py` garde `immediat` par défaut pour le reste de la suite.
- Docs : contrat, guide d'utilisation, SRS (`[depart]`).

## 5. Recette (PC, via le fil de fusion)

En low, medium et high : lancer une séance depuis le menu sur un parcours avec terrain, ne pas pédaler pendant 20 s (écran « Start your engines », feux rouges, chrono à 0), captures de l'écran en low, medium et high à faire valider, puis pédaler : départ 3 s après. Annuler une fois avec Y. Relever dans le journal les lignes « Départ : étape … » et l'instant « Décor du départ prêt » de l'engine.
