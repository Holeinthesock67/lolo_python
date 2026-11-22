# Lot CR1 – Course classique contre les bots

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Mode « Course » à l'accueil : le Grand Prix sans objet, sur tous les parcours libres | Python, GDScript | GP9, GP13, PL1, BT1 | Moyenne | En PR le 20 novembre 2026 |

## 1. Objectif

Demande du propriétaire du 20 novembre 2026 : « il manque un mode course classique vs bots », précisée par « ça revient
à faire un Grand Prix sans objet mais sur tous les parcours » et « classement éloigné aussi à considérer dans ce mode ».
Choix du propriétaire (carte du 20 novembre) : un nouveau mode « Course » à l'accueil, plutôt qu'une option « sans
objets » du Grand Prix limitée à ses parcours.

## 2. La règle

Une seule course, celle du Grand Prix (`grandprix/mode.py`, `GrandPrixMode`) : arrivée, places, écarts et tours sont
les mêmes ; la Course est le mode `race` de cette course, sans objet (aucun objet joué, aucune boîte sur la route).
Pas de deuxième arbitre, pas d'exception :

- Core : `start` avec `mode` = `race` ; plateau composé par le core (`race.opponents`, 2 à 11, 7 par défaut ; niveaux
  étalés autour de `bots.level_pct`, objectif `bots.objective`), départ groupé (`draft.start_grid`) ; sur une boucle,
  `race.laps` tours (1 à 10, 3 par défaut) ; en ligne, la course va jusqu'à l'arrivée du parcours (ligne posée
  `GP_RUNOUT_M` avant le bout, comme au Grand Prix). La séance garde tout le mode classique (segments, records,
  bonus selon `powerups.mode`, maillots, tactique des bots) et les boutons de la séance libre (Z court : bonus). Mêmes
  refus que le Grand Prix (ERG, `bots`, monde ouvert, parcours en ligne de moins de 1 km) ; SIM seulement ; pas de
  demi-tour. Fin à l'arrivée du cycliste.
- Contrat IPC, révision 1.23 (1.21 et 1.22 réservées à #930 et au fil bots/Elo) : valeur `race` de `start.mode` et de
  `hello_ack.config.modes`, champ facultatif `mode` (`race`) de `state.gp` et de `summary.gp`.
- Engine : entrée « Course » à l'accueil, après le Grand Prix ; écran Prêt des modes à réglages (`SETTINGS_MODES`) sur
  les parcours libres ; HUD du Grand Prix sans case d'objet, voies ni menace : place, tour, écart et **classement
  complet** (les 12 coureurs, bots loin devant ou derrière compris, écart estimé quand le core ne le porte plus) ;
  bilan « Course : 3e sur 8 » et format.
- Journal : `gp_start` avec `mode` = `race` (sans objets ni boîtes), `gp` (arrivées), `gp_summary` ; la recette du
  Grand Prix (`tools/gp_recette.py`) écarte ces courses.

## 3. Livraison (20 novembre 2026)

- Core : `grandprix/mode.py` (`MODES`, paramètre `mode`, pas de boîte sans objet joué), `session.py`
  (`_grandprix_course`, `_grandprix_field`, `_start_grandprix` par mode, boutons de la séance libre en Course),
  `config.RaceConfig`, réglages `race.opponents` et `race.laps` (`settings.py`, clés du profil), `ipc_server.CORE_MODES`,
  `run --mode race`.
- Engine : `menu_model.gd` (`HOME_MODES`, `HOME_DETAILS`, `SETTINGS_MODES`), `menu_flow.gd` (`race_keys`, `race_launch`),
  `grandprix/gp_hud_model.gd` (`is_race`, vue et bilan), `grandprix/gp_view.gd` (case d'objet cachée).
- Tests : `core/tests/test_race_mode.py`, `engine/tests/unit/test_race_menu.gd`.
- Guide : `GUIDE_UTILISATION.md` (paragraphe « Course »).

## 4. Reste

- Captures de l'accueil, de l'écran Prêt, du HUD en course et du bilan, à valider par le propriétaire ; banc
  low/medium/high (`sim_bench --mode race`) par la file du PC.
- Cote Elo et effort des bots en watts (révision 1.22, branchés à la fusion de main, 22 novembre) : la Course
  compte dans la cote comme le Grand Prix (`bot_elo.MODES`, classement de `_elo_order`, plateau par
  `_elo_levels(plan, "race")`), `bots_preview` accepte `race` (ligne « Bots : ≈ X W » de l'écran Prêt), ligne
  « Cote » au bilan ; banc `elo_campagne --mode race`.
- Plus tard : porteurs des maillots dans le classement du HUD (aujourd'hui au bilan et au journal seulement).
