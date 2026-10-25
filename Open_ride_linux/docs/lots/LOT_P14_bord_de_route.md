# Lot P14 – Bord de route : panneaux de col, bornes kilométriques, marquages au sol

## 1. Objectif

Donner des repères au cycliste, comme sur une vraie route :
- un **panneau de col** au sommet de chaque montée notable, avec le nom (point OSM s'il existe, sinon « Sommet ») et l'altitude ;
- des **panneaux d'approche** « Sommet à 3 km, pente moyenne 7 % » à 5, 3, 2 et 1 km du sommet, comme dans les cols ;
- des **bornes kilométriques** tous les kilomètres de parcours ;
- des **marquages au sol** : ligne médiane discontinue, bandes de rive, et le chiffre des kilomètres restants peint sur la route dans le dernier kilomètre d'une montée.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_K2_modele_hud_profil.md` (profil d'altitude), `docs/lots/LOT_E1_rendu_route_terrain.md` (ruban de route).
2. Code : `engine/scripts/route_data.gd`, `engine/scripts/hud_view_model.gd` (profil), `engine/scripts/road_builder.gd` (lecture seulement : UV et largeur du ruban), `engine/scripts/osm_layers.gd` (points d'intérêt).

## 3. Prérequis

P4 livré (`living`). Version 1.0 publiée.

## 4. Travail demandé

- Nouveau modèle pur `engine/scripts/climb_detector.gd` : montées du parcours à partir du profil (au moins 1,5 km et 4 % de moyenne, ou 80 m de dénivelé), avec début, sommet, longueur, pente moyenne et pente maximale par kilomètre ; montées voisines de moins de 300 m de replat fusionnées ; résultat partagé avec P15.
- Nouveau modèle `engine/scripts/roadside_model.gd` : liste des objets à poser `{kind, s, side, text}` (panneau de col, panneaux d'approche, bornes) ; aucun objet sur un pont ni dans l'eau (couche eau) ; textes en français, nombres au format français.
- Nouveau nœud `engine/scripts/roadside_props.gd` : panneaux et bornes construits par code, texte en `Label3D` (police par défaut de Godot), placés sur le côté droit à 1,5 m du bord ; chargés et retirés avec les tronçons ; panneau lisible à 30 m.
- Nouveau shader `engine/shaders/road_markings.gdshader` : marquages dessinés à partir des UV du ruban existant (ligne médiane 3 m / 10 m, bandes de rive), chiffres des derniers kilomètres en montée ; couleur et usure réglables ; à appliquer par P17 à la place du matériau actuel de la route (ce lot ne touche pas `road_builder.gd`).

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/climb_detector.gd`, `engine/scripts/roadside_model.gd`, `engine/scripts/roadside_props.gd`, `engine/shaders/road_markings.gdshader`, `engine/tests/unit/test_climb_detector.gd`, `engine/tests/unit/test_roadside_model.gd`, `engine/tests/render/test_road_markings_render.gd`.
- **Modifiés :** `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, `road_builder.gd`, `world_streamer.gd`, le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier, rendu compris.
2. Profil synthétique avec une montée de 8 km à 7 % et une bosse de 400 m à 5 % : une seule montée détectée, sommet à ± 20 m, pente moyenne 7,0 % ± 0,2.
3. Panneaux d'approche à 5, 3, 2 et 1 km du sommet, textes « Sommet à 3 km » et « Pente moyenne 7 % » ; panneau du sommet avec l'altitude arrondie au mètre.
4. Bornes : une par kilomètre, aucune en double sur une boucle.
5. Rendu des marquages : ligne médiane claire au centre du ruban, motif de 13 m, bandes de rive aux deux bords.
6. Aucun objet dans l'eau ni sur la route.

**Sur le PC cible (le propriétaire) :** un parcours de col : panneaux lisibles, au bon endroit, sans scintillement des marquages au loin.

## 8. Hors périmètre

- Panneaux de direction, noms de village à l'entrée, glissières, écritures des supporters sur la route.
