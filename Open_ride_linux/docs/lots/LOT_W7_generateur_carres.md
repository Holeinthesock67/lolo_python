# Lot W7 – Générateur de carrés de 1 km : terrain fondu avec toutes les routes, couches par carré

## 1. Objectif

Produire, pour un carré de 1 km de la grille fixe de la zone UTM, tout ce que l'engine affiche : grille proche fondue avec **toutes** les routes du carré, couches bâtiments, végétation, eau et points d'intérêt, et les tuiles lointaines de 5 km. Les carrés vont dans le cache (W2) et se réutilisent d'une séance à l'autre.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_W.md` §3.3, §3.4 et §4, `LOT_W1_contrat_monde_vivant.md` §4.2 (coordonnées relatives au coin de tuile), `LOT_W2_cache_local_monde.md`.
2. `docs/contracts/world_format_v1.md` §5 à §8.
3. Code : `compiler/src/openride_compiler/terrain.py` (`RouteAxis`, `blend`, `tile_coords`), `osm_layers.py` (bâtiments, végétation, eau, points d'intérêt, `compute_footprint_base_y`, `compute_contour_min_y`), `worldgen/graph.py`, `worldgen/edge_profile.py`, `worldgen/osmdb.py`.

## 3. Prérequis

W2, W3 et W5 livrés.

## 4. Travail demandé

Module `worldgen/squares.py` :

- `SquareKey(zone, IX, IN)` (grille de 1 km : `IX = floor(E / 1000)`, `IN = floor(N / 1000)`) et `FarKey(zone, IX5, IN5)` (grille de 5 km).
- `generate_square(key, db, provider, cache) -> Path` :
  1. emprise du carré plus une marge de 50 m ; arêtes du graphe qui la touchent (W4) et leur profil (W5) ;
  2. grille de 101 × 101 du relief, puis fondu avec l'axe formé par **toutes** ces arêtes (`RouteAxis` construit sur leur polyligne et leurs altitudes de profil, demi-largeur selon la classe : 3 m par défaut, 2 m pour `c` et `k`) ; bords partagés avec les carrés voisins identiques (les deux carrés voient les mêmes arêtes dans leur marge) ;
  3. couches depuis la base : bâtiments (`base_y` au minimum du terrain fondu sous l'empreinte), végétation, eau, points d'intérêt, en réutilisant les fonctions de `osm_layers.py` ; un objet appartient au carré qui contient son centre (pas de doublon) ; coordonnées relatives au coin du carré (W1 §4.2) ;
  4. `edges.json` : arêtes dont le premier nœud est dans le carré, avec leur profil (pour ne pas les recalculer) ;
  5. écriture atomique dans `genere/<zone>/<IX>_<IN>/` (dossier temporaire puis renommage), `meta.json` avec les versions (`WORLDGEN_VERSION`, schéma de la base, date OSM, source du relief), puis `cache.add`.
- `generate_far(key, provider, cache)` : 101 × 101 à 50 m, relief seul (comme le niveau `far` du compilateur).
- `SquareQueue` : file de priorités (priorité = distance au cycliste le long de la route engagée, puis distance à vol d'oiseau), sans doublon, avec annulation des demandes devenues lointaines ; exécutée par un `ProcessPoolExecutor` de `min(4, cœurs − 1)` processus par W8 (ce lot fournit la file et la fonction, pas le processus).
- Carré déjà en cache et valide : rien n'est recalculé ; périmé : régénéré sans téléchargement.

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/worldgen/squares.py`, `compiler/tests/test_world_squares.py`.
- **Modifiés :** `compiler/src/openride_compiler/osm_layers.py` seulement pour rendre publiques des fonctions déjà existantes, sans changer leur comportement ; `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest` passe dans `compiler/`, sans réseau (relief `SyntheticProvider`, base écrite par le test).
2. Deux carrés voisins traversés par une même route : bord commun identique au bit près ; à moins de 4 m de l'axe, terrain = altitude du profil − 0,05 m.
3. Le terrain d'un carré est le même quelle que soit la séance qui l'a demandé (deux origines de séance différentes : fichiers identiques).
4. Bâtiment à cheval sur deux carrés : présent dans un seul, celui de son centre ; coordonnées relatives correctes (retour au repère global à 1e-6 m près).
5. Carré en cache valide : `generate_square` ne recalcule rien (compteur d'appels au relief à 0) ; version changée : régénéré.
6. Temps par carré mesuré dans le test et affiché ; sur le PC cible, moins de 300 ms en médiane (plan §3.3), à vérifier par le propriétaire avec le rapport de W0.

## 8. Hors périmètre

Processus et horizon (W8), tuiles vectorielles (W13).
