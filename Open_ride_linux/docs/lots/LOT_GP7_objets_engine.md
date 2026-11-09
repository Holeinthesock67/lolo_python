# Lot GP7 – Engine : boîtes, objets, projectiles, effets et sons

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : rendu des boîtes, des objets et des projectiles, effets de glissade, d'averse et de super-forme, sons | GDScript | GP2, GP6 | Grande | En PR, captures et banc à valider (version 4.0 proposée) |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Afficher ce que le core envoie dans `state.gp` et `gp_hit`, selon les maquettes validées.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` §8 ; maquettes GP6 ; `engine/scripts/segment_markers.gd`, `engine/scripts/bots_view.gd`, `engine/scripts/sound_player.gd` ; scène des gags WTF (WTF5, WTF6) pour la réserve d'instances.

## 3. Travail demandé

- Boîtes en `MultiMesh`, deux rangées au plus dans la scène ; réserve d'instances par sorte d'objet, aucune création en course.
- Effets par préréglage : `low` sans particules, `medium` limité, `high` complet.
- Sons : roulette, lancer, glissade, averse, sonnette, klaxon.

## 4. Critères d'acceptation

1. Banc au pire cas (départ, tous les bots, six boîtes, douze objets) en `low`, `medium` et `high` : budgets GPU de 6, 12 et 14 ms tenus.
2. Captures validées par le propriétaire avant fusion.
3. Tests de modèle sans scène (objet affiché à la bonne voie, disparition hors trame).

## 5. Livraison (8 novembre 2026)

- Modèle sans nœud `engine/scripts/grandprix/gp_scene_model.gd` : boîtes (une par voie, deux rangées au plus), objets à leur voie (centres des voies du core) ou au milieu pour toute la route, réserve de 12 instances par sorte dessinée (bidon, musette, musette guidée, nuage d'orage) où chaque objet garde sa place d'une trame à l'autre, effets par objet en cours et par préréglage, onomatopées des messages `gp_hit` (doublons écartés).
- Scène `engine/scripts/grandprix/gp_scene.gd` (charte CT9, matériaux non éclairés, sans ombre) : boîtes en `MultiMesh` (six instances), réserves créées à la construction (aucune création en course, vérifié par le test), une réserve d'effets par coureur (étoiles de la glissade, nuage et averse, halo de la super-forme, voiture d'équipe, rafales, traits du coup de fouet), préchauffage de trois images au départ. `low` : sprites seulement (rideau de pluie dessiné, ni rafales ni traits) ; `medium` : averse de 48 gouttes, sans étincelles ; `high` : averse de 140 gouttes et étincelles.
- Sons (`grandprix/gp_sound_model.gd`, jingles `gp_*` de `event_sounds_model.gd`) : roulette, lancer, glissade, averse, sonnette, klaxon. Un objet volé par le Furtif sonne comme un lancer (la trame ne les distingue pas).
- Branchement : `main.gd` (`gp_scene.step` à la place affichée du cycliste et des bots, `_gp_riders`), `ipc_client.gd` (signal `gp_hit_received`).
- Tests : `engine/tests/unit/test_gp_scene.gd` (voies, réserve, disparition hors trame, préréglages, sons, scène sans création de nœud) ; scénario de banc `engine/tests/sim_bench_scenarios/grand_prix.json` (4 bots, chaos fou, boîtes tous les 1 000 m, `--mode grandprix` ajouté à `sim_bench.py`) et son test `core/tests/test_sim_bench_scenarios.py`.
- Banc GPU et captures à lancer sur le PC, en `low`, `medium` et `high` : `engine/tests/sim_bench.py --scenario grand_prix --quality <q> --native --probe`.
- Banc r831 (9 novembre, PC) : sans échec, GPU médian low 5,25 / medium 6,34 / high 8,04 ms. Les captures toutes les 15 s ne montraient ni boîte ni objet : les rangées n'entrent dans la trame qu'à 400 m, et le cycliste simulé ne lançait jamais son objet. Le scénario capture maintenant 35 m avant chaque rangée (`first_m` 465, `every_m` 1 000 ; `first_m` ajouté à `sim_bench.py`) et 1,5 s après un appui sur Z toutes les 20 s (objets lancés, effets sur le cycliste).
