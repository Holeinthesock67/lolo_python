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

## 9. Livraison

Livré sur la branche `lot-p14-bord-de-route`, sans toucher à `main.gd`, à `road_builder.gd`, à `world_streamer.gd`, au core ni au contrat.

- **`climb_detector.gd`** (`detect(route)`, partagé avec P15) : profil tous les 20 m, lissé sur 100 m.
  - Creux et sommets à hystérésis de 8 m ; une montée s'arrête aussi après 300 m sans regagner 1,5 m (replat au sommet). Les montées séparées par moins de 300 m sont fusionnées.
  - Gardées : 1,5 km à 4 % de moyenne au moins, ou 80 m de dénivelé. Début et sommet recalés sur le profil brut.
  - Rend début, sommet, longueur, dénivelé, pente moyenne, pente maximale sur un kilomètre glissant et altitude du sommet.
- **`roadside_model.gd`** : liste `{kind, s, side, lines}`.
  - Panneau de sommet : nom du point d'intérêt nommé à moins de 400 m, sinon « Sommet », et l'altitude au format français (« 1 234 m »).
  - Panneaux d'approche à 5, 3, 2 et 1 km du sommet (« Sommet à 3 km », « Pente moyenne 7 % » sur le reste de la montée).
  - Bornes « km N », sans doublon au départ d'une boucle.
  - Un objet qui tomberait dans l'eau ou sur un pont (surface ou cours d'eau, 2 m de marge) est avancé par pas de 10 m, au plus 100 m.
  - `paint_marks` : chiffres de 5 à 1 km du sommet pour le shader. `for_chunk` : objets d'un tronçon.
- **`roadside_props.gd`** : panneaux et bornes construits par code, texte en `Label3D`, côté droit à 1,5 m du bord, face au cycliste qui arrive. Lettres de 12 cm au moins (lisibles à 30 m). `add_chunk` et `remove_chunk` suivent les tronçons.
- **`road_markings.gdshader`** : marquages à partir des UV d'E1 : ligne médiane 3 m sur 13 m, bandes de rive, chiffres à sept segments sur la voie de droite (`marks`, 8 par tronçon), usure réglable. La couverture des traits est calculée par pixel (`fwidth`) : au loin, les traits s'estompent au lieu de scintiller. P17 l'applique à la place de `road_builder.make_material`.
- **Tests** : `test_climb_detector.gd` (7 vérifications), `test_roadside_model.gd` (13), `render/test_road_markings_render.gd` (6).
- **Reste sur le PC cible (le propriétaire)** : parcours de col, après le branchement par P17.
