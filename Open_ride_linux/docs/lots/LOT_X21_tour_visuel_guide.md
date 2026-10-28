# Lot X21 – Tour visuel guidé

## 1. Objectif

Les recettes visuelles (E3/E4, P16, P17, U18, Y11/Y12) demandent de rouler jusqu'au bon endroit pour regarder. Ce lot fait le trajet : il place la caméra sur une liste de points d'un vrai parcours compilé et produit une planche à cocher. Le propriétaire juge, l'outil fait le trajet.

## 2. À lire

`engine/tests/vitrine_rendu.gd` et `vitrine_biomes.gd` (scène sans core), `engine/scripts/world_streamer.gd`, `route.gd` (position à la distance), `render_quality.gd`, `camera_views.gd`.

## 3. Travail demandé

- **Scène du tour** (prévue comme un script `tour_visuel.gd` sans core, comme les vitrines ; faite avec la vraie scène, voir §7) : charge un `.world`, applique un préréglage, et pour chaque point (distance en mètres, vue de caméra, heure, météo) place le cycliste et la caméra, attend que les tronçons soient chargés, capture.
- **Liste des points** en JSON (`engine/tests/tours/*.json`) ; points automatiques (`--auto`) : village le plus dense, forêt, eau, montées à 0, 5 et 10 %, départ et arrivée, frontières de biome.
- **`engine/tests/tour_visuel.py`** : lance Godot (Xvfb ou `--native`), puis écrit `planche.html` : une carte par point, la capture, les mesures (triangles, appels de dessin), et trois cases « OK / à revoir / défaut » avec une note, mémorisées dans la page (localStorage) et exportables en JSON.

## 4. Fichiers

- **Nouveaux :** `engine/tests/tour_visuel.py`, `engine/tests/tours/demo.json`, `core/tests/test_tour_visuel.py` (points automatiques sur une route fabriquée, planche).
- **Modifiés :** `engine/scripts/main.gd` et `world_streamer.gd` (message de test `camera_view`, tuiles en attente dans la capture), `docs/OUTILS_DE_TEST.md`, `engine/tests/README.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. `tour_visuel.py --world demo --auto` sous Xvfb : une capture par point, planche lisible.
2. Points automatiques testés sur une route fabriquée (montée trouvée au bon endroit).

## 6. Hors périmètre

Le jugement visuel lui-même.

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x21`).

- **Écart au cahier : pas de `tour_visuel.gd`.** Une scène à part aurait recopié ce que `main.gd` fait déjà : chargement du `.world`, tuiles, décor, préréglage, vues de caméra, météo. `tour_visuel.py` pilote donc la vraie scène (`main.tscn`, `--test-mode`) face au faux core des tests graphiques (`visual_check.VisualCore`, aucun vrai core). C'est ce qui sera vu au vélo.
- **Engine** :
  - message de test `camera_view` (vue imposée, ligne `[test] camera_view done=…`) ;
  - `world_streamer.pending_count()` (tuiles voulues pas encore affichées) ;
  - la capture donne `streaming_pending` et `triangles`.
- **`tour_visuel.py`** : pour chaque point (distance, vue, météo), il attend la fin des tuiles (`streaming_pending` à 0, 12 essais d'une seconde au plus) puis capture.
  - Points en entrée : `tours/*.json`, vérifiés (clés connues, vues valides), et `--auto` ; les deux se cumulent, triés dans le sens de la route.
  - Fichiers écrits : `points.json`, `mesures.csv` et `planche.html` (localStorage, export JSON).
- **Points automatiques** :
  - départ et arrivée ;
  - plat et montées à 5 et 10 %, sur la pente lissée sur 200 m ; une montée absente du parcours n'est pas inventée (tolérance 1,5 point) ;
  - village le plus dense (bâtiments à moins de 150 m, puis au plus près d'eux) ;
  - forêt et eau les plus proches de la route (300 m au plus) ;
  - trois frontières de biome au plus (couche `biome`, biome dominant tous les 50 m) ;
  - deux points à moins de 150 m sont fusionnés, et la carte donne les deux raisons.
- **L'heure n'est pas un réglage** : l'engine n'a pas de cycle jour et nuit.
- **Mesuré au cloud sous Xvfb** (critère 1) : `--world demo --auto --tour demo` a donné 8 points, 8 captures et 0 tuile en attente.
  - Les quatre vues de caméra ont été prises.
  - La pluie est active à son point : 480 particules, chaussée mouillée à 1,0.
  - Sur `demo`, il n'y a pas de montée à 10 %, donc pas de point à 10 %.
- **Tests** : `core/tests/test_tour_visuel.py` (11 tests). Ils couvrent :
  - le parcours fabriqué : montées à 5 et 10 % trouvées au bon endroit (critère 2), village, forêt, eau, frontière de biome ;
  - le parcours plat : aucune montée inventée ;
  - les points fusionnés, le tour `demo`, les tours mal écrits et la planche.

