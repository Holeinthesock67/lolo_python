# Lot X21 – Tour visuel guidé

## 1. Objectif

Les recettes visuelles (E3/E4, P16, P17, U18, Y11/Y12) demandent de rouler jusqu'au bon endroit pour regarder. Ce lot fait le trajet : il place la caméra sur une liste de points d'un vrai parcours compilé et produit une planche à cocher. Le propriétaire juge, l'outil fait le trajet.

## 2. À lire

`engine/tests/vitrine_rendu.gd` et `vitrine_biomes.gd` (scène sans core), `engine/scripts/world_streamer.gd`, `route.gd` (position à la distance), `render_quality.gd`, `camera_views.gd`.

## 3. Travail demandé

- **`engine/tests/tour_visuel.gd`** (script sans core, comme les vitrines) : charge un `.world`, applique un préréglage, et pour chaque point (distance en mètres, vue de caméra, heure, météo) place le cycliste et la caméra, attend que les tronçons soient chargés, capture.
- **Liste des points** en JSON (`engine/tests/tours/*.json`) ; points automatiques (`--auto`) : village le plus dense, forêt, eau, montées à 0, 5 et 10 %, départ et arrivée, frontières de biome.
- **`engine/tests/tour_visuel.py`** : lance Godot (Xvfb ou `--native`), puis écrit `planche.html` : une carte par point, la capture, les mesures (triangles, appels de dessin), et trois cases « OK / à revoir / défaut » avec une note, mémorisées dans la page (localStorage) et exportables en JSON.

## 4. Fichiers

- **Nouveaux :** `engine/tests/tour_visuel.gd`, `tour_visuel.py`, `engine/tests/tours/demo.json`, `core/tests/test_tour_visuel.py` (points automatiques sur une route fabriquée, planche).
- **Modifiés :** `docs/OUTILS_DE_TEST.md`, `engine/tests/README.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. `tour_visuel.py --world demo --auto` sous Xvfb : une capture par point, planche lisible.
2. Points automatiques testés sur une route fabriquée (montée trouvée au bon endroit).

## 6. Hors périmètre

Le jugement visuel lui-même.
