# Lot PL1 – Peloton d'environ 12 bots

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Peloton : 11 bots et un fantôme (12 coureurs avec le cycliste), trame IPC allégée sous 4 096 octets, bots enfermés qui lèvent le pied, bots détaillés plafonnés par qualité, ligne « Peloton » au menu | Python + GDScript | Y18, AS2, AS4, O35 | Moyenne | En PR (5 novembre) ; bancs PC low/medium/high et captures à valider |

Version 3.0. Plan validé par le propriétaire le 5 novembre (`PLAN_APRES_2_0.md` : « Peloton d'environ 12 bots
(core + engine, trame IPC ≤ 4 096 o), tests verts » puis bancs du PC en trois qualités). Préalables tenus : Y18
(bots dessinés comme l'avatar, PR #668) et le placement en travers de la série AS (AS2, AS4) sont sur `main`.
Suites : DS8 (Dernier survivant à 11 adversaires) et GP10 s'appuient sur ce lot.

## 1. Objectif

Rouler dans un vrai petit peloton : jusqu'à 11 bots (puissance constante ou profil) et le fantôme, sans que
la trame `state` dépasse 4 096 octets, sans que les bots se roulent dessus, et sans sortir des budgets GPU
(low 6 ms, medium 12 ms, high 14 ms).

## 2. Ce qui change

### 2.1 Core

- `bots.MAX_CONSTANT_BOTS` passe de 4 à 11 (`MAX_BOTS` = 12 avec le fantôme) : `start.bots`, `--bot` et
  `--bot-profile`, derniers choix du menu (`last_choices.MAX_BOTS`). Le réglage `survivor.opponents` reste borné
  à 4 : il passe à 11 avec DS8.
- Trame allégée (`bots.light_frame`, appelée par la séance avant chaque envoi) : au-delà de 5 bots, les 5 plus
  proches du cycliste gardent tout ; les autres perdent `cp_w`, `mass_kg`, `wbal_pct` et `gap_s` ; `jersey` à
  `null` n'est plus envoyé. Pire trame (`python -m openride_core.ipc_budget`, révision 1.6) : 3 758 octets
  (12 bots, monde ouvert, véhicules), 3 480 avec `devices`.
- Bot enfermé (`draft.blocked_by`, posé par `update_lanes` dans `Lane.blocked`) : un bot qui rattrape un coureur
  dans sa ligne (moins de 0,75 m de côté) sans que son placement l'en sorte, ou qui se retrouve à sa hauteur trop
  près, lève le pied (`_blocked_power`, vitesse ramenée à celle du coureur devant à 0,5 m de sa roue) et freine
  roue contre roue (moins de 0,2 m). En s'écartant pour doubler, il n'est ralenti qu'à moins de 10 cm de la roue.
  Garde en travers (`draft.side_guard`) : à hauteur d'un coureur (roues qui se chevauchent), un bot ne se
  rabat jamais à moins de la largeur d'un coureur plus 10 cm, plus la distance pour arrêter son glissement
  latéral. Un bot arrivé (arrêté sur la ligne) ne compte
  plus dans le placement.
- Contrat IPC révision 1.6 : `bots` jusqu'à 12 éléments (`state`, `start`, `last_choices`), le core et l'engine
  annoncent « 1.6 ».
- `tools/bots_race.py` compte les contacts entre coureurs avec la règle de l'engine (`living_decor.gd` : moins
  de 1,7 m en long et de 0,6 m en travers) et le premier, pour l'enquête ; accepte 11 bots.
- Bancs (`perf_probe.hitch_checks`) : une seconde lente du régime établi que `saccades.csv` explique par une
  capture du banc est écartée, par une image d'avant le premier mètre est jugée avec le départ (150 ms). Le
  peloton se charge en 35 à 40 s, au-delà des 30 s de `warmup_s`.

### 2.2 Engine

- `bots_view_model.gd` : 12 bots gardés (`MAX_BOTS`) ; `cp_w` et `mass_kg` gardés de la dernière trame qui les
  portait.
- `bots_view.gd` : seuls les `QualityPresets.BOT_DETAIL_MAX` bots les plus proches de la caméra (low 5, medium 6,
  high 8) prennent les niveaux 0 et 1 (et leur ombre) ; les autres restent au niveau 2. Apparence tirée du numéro
  de l'id (« bot7 » : dossard 7), stable quand un bot sort de l'écran et revient.
- `bot_hud_model.gd` : l'encart garde 5 lignes au plus (`MAX_ROWS`), autour du cycliste.
- Écran Prêt (`menu_model.gd`) : ligne « Peloton : aucun » sous le fantôme, A long : 4, 8, 11 bots à profil
  (rouleur, grimpeur, sprinteur, diesel en cycle) au « Niveau des bots » des réglages, coupé pour ne pas dépasser
  11 bots avec ceux choisis un par un ; repris des derniers choix.

## 3. Mesures faites au cloud

| Mesure | Résultat |
| --- | --- |
| Pire trame `state` 1.6 | 3 758 octets (limite 4 096), sans allègement ; 3 480 avec `devices` |
| Course de 11 bots au niveau du cycliste (`bots_race`, demo 5 km, plat 20 km, col 10 km, demo à 100 %) | trames de 2 137 à 2 152 octets ; 0 contact partout avec la règle de l'engine (avant correction : des centaines dès 6 bots) |
| Calibrage T13 (4 bots, plat et col courts) | écarts toujours sous 2 % |
| Banc de l'abri (`draft_bench`) | inchangé, contacts du groupe libre sous 1 % du temps |
| Pas de physique, 11 bots à profil | p99 sous 3 ms (test `test_peloton.py`) |

Banc du PC du 5 novembre (tête bcc7741, avant la garde en travers) : GPU médian / p99 peloton low 5,16 / 5,69 ms,
medium 8,22 / 8,97, high 9,89 / 10,83 ; course_bots low 4,94 / 5,53, medium 8,08 / 8,61, high 9,90 / 10,43 :
budgets tenus. Échecs corrigés ensuite : 29 images de contact bot / bot vues par l'engine en medium (garde en
travers, marge de 10 cm), pires images de 135 à 150 ms toutes au départ (0 m) ou pendant une capture (critère
aligné ; les six bancs rejoués passent).

## 4. Critères d'acceptation

1. 11 bots et le fantôme acceptés, 12 bots refusés (`bot_invalid`) ; trame valide et sous 4 096 octets à chaque
   envoi (`core/tests/test_peloton.py`, `test_ipc_budget.py`).
2. Aucun contact entre bots dans une course de 11 bots sur la démo (`bots_race`, test `test_bots_race.py`).
3. Engine : 12 silhouettes, bots détaillés plafonnés par qualité, encart à 5 lignes, ligne « Peloton »
   (`test_bots_view_model.gd`, `test_bot_hud_model.gd`, `test_menu_flow.gd`).
4. Bancs du PC (fil « Fusionner les PR et séquencer les mesures ») : `sim_bench.py --scenario peloton --quality
   low|medium|high` et `course_bots` (non-régression à 4 bots) ; budgets GPU tenus au départ (peloton groupé, pire
   cas) ; repli : baisser `BOT_DETAIL_MAX`, puis `BOT_LOD_M`.
5. Captures du peloton en trois qualités validées par le propriétaire avant fusion.
