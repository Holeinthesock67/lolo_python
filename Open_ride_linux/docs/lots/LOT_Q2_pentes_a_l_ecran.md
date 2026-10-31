# Lot Q2 – Pentes plus lisibles à l'écran (caméra et relief)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Pentes plus lisibles à l'écran : caméra inclinée et relief exagéré à l'affichage | GDScript | — | Moyenne | Oui (valeur par défaut choisie par le propriétaire sur la GTX 1060) ; issue #169 |

## 1. Objectif

Essai du 25 octobre : « la pente affichée par Godot semble plus faible visuellement que la consigne ». La valeur du HUD est juste, et le relief est construit avec les vraies altitudes. Mais la caméra reste horizontale à 1,4 m (champ de vision vertical de 65°) : une pente de 7 % ne fait que 4°, et elle paraît presque plate. Ce lot fait regarder la caméra le long de la route et ajoute une exagération **visuelle** du relief, réglable. La physique et les consignes envoyées au trainer ne changent pas.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/contracts/world_format_v1.md` §4–5 (route, tuiles), `docs/lots/LOT_E1_rendu_route_terrain.md`.
2. Code : `engine/scripts/camera_follow.gd`, `main.gd` (`_process` : position et cap de la caméra), `route_data.gd`, `road_builder.gd`, `terrain_tiles.gd`, `world_streamer.gd`, `tree_renderer.gd`, `building_mesh.gd`, `engine_args.gd` ; `core/src/openride_core/launcher.py` et `config.py` (`[render]`).

## 3. Prérequis

Aucun.

## 4. Travail demandé

- **Inclinaison de la caméra :**
  - nouvelle fonction de `camera_follow.gd`, `pitch_deg(route, s, v)` : angle de la droite qui joint l'œil au point de la route situé 20 m devant (entre 15 et 30 m selon la vitesse), lissé avec une constante de temps de 0,5 s, borné à ±12° ;
  - `main.gd` applique cet angle à `camera.rotation.x`, en plus du cap (deux lignes au plus dans `main.gd`).
- **Exagération du relief (option) :**
  - `visual_grade_scale` de 1,0 à 2,0, valeur proposée 1,5 : les altitudes affichées de la route et du terrain valent `alt_origine + (alt − alt_origine) × k` ;
  - appliqué à la construction des maillages (`road_builder.gd`, `terrain_tiles.gd`) et à la hauteur de la caméra ;
  - arbres, bâtiments et eau restent posés au sol, sans être étirés : seule leur position verticale suit ;
  - le profil d'altitude du HUD et la valeur de pente restent les vraies valeurs.
- **Réglage :** `[render] visual_grade_scale` dans `config.toml` (validation des bornes dans `config.py`), passé par le lanceur à l'engine en `--visual-grade=K` (`engine_args.gd`, défaut 1,0 tant que le propriétaire n'a pas choisi).
- **Recette visuelle :** trois captures (`engine/tests/visual_check.py`, scène supplémentaire) sur le parcours `demo` à des points de 0 %, ~4 % et ~8 % avec k = 1,0 et k = 1,5.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/camera_follow.gd`, `main.gd` (application de l'angle et de k seulement), `road_builder.gd`, `terrain_tiles.gd`, `world_streamer.gd` (transmission de k), `engine_args.gd` ; `engine/tests/visual_check.py` ; `core/src/openride_core/config.py`, `launcher.py` ; `README.md`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `engine/tests/unit/test_camera_pitch.gd`, `engine/tests/unit/test_visual_grade_scale.gd`.
- **Interdits :** le core hors `config.py` et `launcher.py` (aucune physique ne change), le contrat IPC, le format `.world`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Tous les tests passent (`pytest` core et compilateur, `run_engine_tests.sh`, hors échec connu #119).
2. `pitch_deg` : 0° sur le plat ; pour une pente constante de 8 %, atan(0,08) ± 0,3° une fois le lissage établi ; bornes à ±12° ; variation lissée (pas de saut de plus de 1° par image à 60 images/s sur une marche 0 → 8 %).
3. k = 1,0 : sommets de la route et du terrain identiques à ceux d'aujourd'hui (comparaison exacte dans le test) ; k = 1,5 : écart d'altitude à l'origine multiplié par 1,5 à 1 cm près ; route et terrain restent raccordés (le terrain passe toujours sous la chaussée, règle du format §5).
4. Arbres et bâtiments : hauteur de maillage inchangée avec k = 1,5, base posée au sol exagéré à 5 cm près.
5. HUD : valeur de pente et profil identiques avec k = 1,0 et 1,5.
6. Coût : construction d'un tronçon et d'une tuile pas plus de 5 % plus lente qu'avant (mesure dans le test).

**Sur le PC cible (le propriétaire) :** rouler `essai-69` avec k = 1,0, 1,3 et 1,5 et choisir la valeur par défaut ; vérifier les images par seconde (`[perf-rendu]`).

## 8. Hors périmètre

- Mouvement de la tête, roulis dans les virages, vue à la troisième personne.
- Changement de la pente envoyée au trainer (voir Q1).
