# Lot W13 – Tuiles vectorielles OpenFreeMap : partout dans le monde, préchargées autour des départs habituels

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Tuiles vectorielles OpenFreeMap : au fil de la balade et préchargées autour des départs habituels | Python | W2, W7 (W0) | Moyenne | Oui, après W7 (issue #268) |

## 1. Objectif

Rouler n'importe où sans extrait régional (décision W-Q4) : les tuiles vectorielles OpenFreeMap (zoom 14) sont téléchargées pendant la balade et préchargées à l'avance autour des lieux de départ de l'historique du joueur (les plus fréquents et les plus récents d'abord), toujours dans la limite du cache de 5 Go. Elles remplissent la **même** base locale que l'extrait régional (schéma de W3), si bien que graphe et générateur ne voient aucune différence.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_W.md` §3.1, §3.2, §4, §7 (risque 2) et §8 (W-Q4), `LOT_W3_extrait_regional_sqlite.md` §4.1, `LOT_W2_cache_local_monde.md`.
2. Code : `worldgen/mvt.py` (W0), `worldgen/osmdb.py`, `worldgen/store.py`, `cache.py`.
3. Schéma OpenMapTiles : couches `transportation` (`class`, `subclass`, `brunnel`, `surface`, `oneway`), `building` (`render_height`), `landcover`, `landuse`, `water`, `waterway`, `poi`, `place`, `mountain_peak`.

## 3. Prérequis

W2 et W7 livrés (W0 pour le décodeur).

## 4. Travail demandé

- **Source :** URL des tuiles lue dans le TileJSON `https://tiles.openfreemap.org/planet` (jamais codée en dur), relue au plus une fois par jour ; `User-Agent` du projet ; au plus 4 requêtes simultanées ; reprises de `Downloader` ; fichiers dans `brut/tuiles/14/<x>/<y>.mvt`, enregistrés dans le cache (W2).
- **Conversion** (`worldgen/vector_tiles.py`) : chaque tuile décodée est versée dans une base `brut/osm/tuiles.sqlite` (schéma W3, `source = openfreemap`) :
  - `transportation` → `roads` : `class` motorway et trunk → `x` ; primary → `p` ; secondary → `s` ; tertiary → `t` ; minor et service → `m` ; path avec `subclass` cycleway → `c` ; track revêtue → `k` ; `surface = unpaved` → `x` ; `brunnel` → `bridge`, `tunnel` ;
  - nœuds : pas d'identifiant OSM dans les tuiles, identifiant synthétique négatif tiré des coordonnées quantifiées à 1e-7° ; les voies coupées au bord des tuiles sont recousues par leurs extrémités communes (même point quantifié) ;
  - `building` → `areas` (`height` = `render_height`), `landcover` wood, scrub, orchard → `areas`, `water` → `areas`, `waterway` → `lines`, `poi` et `place` → `points` ;
  - une tuile versée deux fois ne crée pas de doublon (table `tiles_loaded`).
- **Pendant la balade :** W8 demande les tuiles qui touchent un couloir de 2 km autour de la route engagée et des amorces, plus loin que l'horizon de 3 km quand le réseau le permet.
- **Préchargement (W-Q4) :** `prefetch_plan(history, cache)` : lieux de départ des séances passées en monde ouvert (index `seances/` du cache), classés par fréquence puis récence ; pour chacun, tuiles à moins de `prefetch_radius_km` (10 km) et tuiles de relief ; entrées marquées `prefetch` ; arrêt dès que le plafond moins 10 % serait dépassé. Lancé en tâche de fond par le générateur au démarrage d'OpenRide si `prefetch_history` est vrai et le réseau présent, jamais pendant une séance au détriment de l'horizon (priorité basse).
- **Attribution :** « © OpenMapTiles © contributeurs OpenStreetMap » ajoutée aux crédits (W11, W12).

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/worldgen/vector_tiles.py`, `compiler/tests/test_vector_tiles.py`.
- **Modifiés :** `worldgen/process.py` (appel des tuiles et du préchargement), `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest` passe dans `compiler/` sans réseau (tuiles encodées par le test, faux serveur).
2. Route coupée entre deux tuiles : une seule voie continue dans le graphe (W4) après recousage.
3. Classes et ponts traduits comme au §4 ; voie non revêtue exclue du graphe.
4. Même tuile versée deux fois : mêmes nombres de lignes.
5. Préchargement : trois départs passés (deux fois A, une fois B) → tuiles de A d'abord ; plafond respecté ; entrées `prefetch` évincées en dernier (W2).
6. TileJSON indisponible : message clair, la séance continue sur le cache.

**Sur le PC (le propriétaire) :** une balade sans extrait régional, puis la même zone hors ligne.

## 8. Hors périmètre

Hébergement d'un serveur de tuiles, zooms autres que 14.
