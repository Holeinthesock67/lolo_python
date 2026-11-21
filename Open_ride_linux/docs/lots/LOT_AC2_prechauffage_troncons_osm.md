# Lot AC2 : préchauffage des tronçons OSM (bâtiments, eau, mer, côte, ponts)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| À-coups de main : préchauffage des tronçons OSM (bâtiments, eau, mer, écume, plages, ponts) dans le plan unique | GDScript | PI2 | Petite | En cours (PR #953, banc PC à faire) |

Fil global « Supprimer les à-coups récurrents de main » (21/11). Analyse : `/mnt/project-files/statut/ACOUPS_MAIN_2026-11-21.md`.

## Constat
- Banc rNUIT20, DB1 (« Tour des nouveaux paysages ») en low : une image de **1 610 ms** à 1 862 m, avec
  2 pipelines compilés, dans l'image où le tronçon OSM 5 entre dans la scène.
- Le tronçon 5 apporte le **premier cours d'eau** du parcours (un ruisseau). Les tronçons 0 et 1 n'ont que de la mer :
  le matériau de l'eau (`water_mesh.gd`) n'avait jamais été dessiné, son shader se compilait donc en roulant.
- Le préchauffage unique de PI2 (`warmup_plan.gd`) couvrait portiques, spectateurs, passants, cyclistes et forêts,
  pas les nœuds des tronçons OSM. Même risque pour le premier pont, la première plage ou la première mer d'un parcours.
- En medium et high, le cache des shaders était déjà chaud (low passe en premier) : le gel n'arrive qu'au premier
  lancement, comme chez un joueur après l'installation ou une mise à jour du pilote.

## Correction (une seule voie)
- `osm_streamer.gd warm_up(camera)` : une étape « osm » du préchauffage unique (`main.gd _warmup_steps`). Un triangle
  minuscule de chaque sorte de nœud de tronçon (bâtiments, lignes et aires d'eau, mer, écume, plages, ponts), avec le
  **vrai matériau**, le **format de sommets de son constructeur** (`WARM_FORMATS`) et les **mêmes ombres**
  (`_casts_shadow`, partagé avec `integrate`), posé devant la caméra pendant 5 images puis retiré.
- Le format compte : un pipeline dépend du matériau, du format des sommets et de la passe (ombre ou non).

## Tests
`engine/tests/unit/test_osm_warm.gd` : pour chaque sorte, le format du préchauffage est celui que produit le vrai
constructeur (building_mesh, water_mesh, sea_mesh dont l'horizon, bridge_mesh) ; warm_up pose 7 nœuds avec matériau et
ombres des vrais nœuds, les retire après 5 images, et un nouveau préchauffage remplace l'ancien.

## Suite possible (pas dans ce lot)
Récif low : 3,9 images lentes par minute (50 à 100 ms, scripts ~35 ms non notés, de 4,3 à 7,8 km). À instrumenter.

## Recette PC
Catégorie : rendu. Low, medium et high, **shaders à froid** (`--shaders froid` de PI1) : DB1 `demo-biomes-paysages`
(nominal, 50 km/h) ; attendu : plus d'image de plus de 200 ms vers 1,9 km, étape « préchauffage osm » au chargement,
budgets GPU 8/13/16 ms inchangés.
