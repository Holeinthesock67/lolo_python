# Lot I4 – Compilateur : couches points d'intérêt et eau

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Compilateur : couches points d'intérêt et eau | Python | I3 | Petite | **Livré le 23 octobre** (PR #23) |

## 1. Objectif

Ajouter les couches facultatives `poi` et `water` du format `.world`, tirées d'OpenStreetMap avec le client et le cache du lot I3. Partie compilateur du sprint 6 de la SRS (ambiances sonores, eau).

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/SRS_v1.1.md` §8 (audio : sources 3D sur les points d'intérêt) et §10 (couches).
3. `docs/contracts/world_format_v1.md` §2, §3, §8 (en entier), §10, §12.
4. Le code livré par le lot I3 : `osm.py`, `osm_layers.py`, `cli.py`, `verify.py`.

## 3. Prérequis

**Lot I3 livré.** Partir de `main` à jour.

## 4. Travail demandé

### 4.1 Requêtes

Étendre la requête Overpass du lot I3 (même découpage, même cache, même `--offline`) aux objets :

| `kind` (§8) | Étiquettes OSM retenues |
| --- | --- |
| `church_bell` | `amenity=place_of_worship` avec `building=church` ou `building=chapel` |
| `village` | `place=village`, `place=hamlet`, `place=town` |
| `viewpoint` | `tourism=viewpoint` |
| `livestock` | `landuse=meadow` avec `animal=*`, ou `landuse=farmyard` (centroïde) |
| `river` (point) | point de passage d'un `waterway=river` ou `stream` à moins de 50 m de la route |
| Eau, lignes | `waterway=river`, `stream`, `canal` |
| Eau, zones | `natural=water` (`lake`, `pond`, `reservoir` d'après `water=*`), `landuse=reservoir` |

### 4.2 Couches (§8)

- **`poi/chunk_<k>.json`** : `x`, `z` dans le repère du monde ; `y` = altitude du terrain au point ; `radius_m` par défaut selon `kind` (constantes nommées : par exemple 300 m pour une cloche, 150 m pour une rivière) ; `name` tiré de `name` s'il existe.
- **`water/chunk_<k>.json`** :
  - `lines` : points (x, z, y) avec `y` = altitude du terrain ; `width_m` tiré de `width`, sinon 2 m (règle du §8), sinon une valeur par type documentée (rivière 6 m, ruisseau 2 m, canal 8 m) ;
  - `areas` : `level_y` = minimum du terrain sur le contour ; `outer` antihoraire, `holes` horaires, comme pour les bâtiments.
- Objets à plus de 400 m de la route exclus ; une rivière longue est coupée par tronçon de 1 km.
- Manifeste : `present`, `version`, compteurs, comme dans le lot I3.

### 4.3 Ligne de commande

- `--layers …,poi,water` et `add-layer <world> poi|water`.
- `verify` contrôle ces couches (`kind` connus, anneaux, rattachement aux tronçons).

## 5. Fichiers concernés

- **Nouveaux :** `compiler/tests/test_osm_poi_water.py`, réponses enregistrées supplémentaires dans `compiler/tests/data/osm/`, `docs/contracts/world/poi.schema.json`, `docs/contracts/world/water.schema.json`.
- **Modifiés :** `osm.py`, `osm_layers.py`, `cli.py`, `verify.py`, `writer.py`, `constants.py`, `README.md` et `CLAUDE.md` (commandes), `docs/contracts/world_format_v1.md` §12 (une ligne), `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Ajouts compatibles seulement : schémas JSON des deux couches, conformes au §8 ; compteurs du manifeste ; ligne au journal des changements. La correspondance étiquettes OSM ↔ `kind` du §4.1 est une proposition : si un `kind` du §8 n'a pas d'équivalent OSM raisonnable, le signaler au lieu d'inventer.

## 7. Critères d'acceptation

1. `cd compiler && pytest -q` passe en entier sans réseau.
2. Sur les réponses enregistrées : nombre de points et d'objets d'eau attendu par `kind` ; un lac avec île donne un `holes` correct.
3. Une rivière de 2,5 km parallèle à la route est coupée en 3 morceaux rattachés aux bons tronçons.
4. `width_m` : `width=4` donne 4 ; un `stream` sans étiquette donne 2.
5. Recompilation `--offline` identique octet pour octet ; `add-layer … water` ne touche pas aux autres couches.
6. `verify` rejette un `kind` inconnu dans `poi` (ou l'ignore avec un avertissement, selon la règle du §10 : à appliquer telle qu'écrite).

## 8. Hors périmètre

- Sons, rendu de l'eau et affichage des noms dans l'engine.

## 9. Livraison (23 octobre 2026, PR #23)

- Extension de `osm.py` et `osm_layers.py` aux couches `poi` (`church_bell`, `village`, `viewpoint`, `livestock`, `river` à ≤ 50 m de la route) et `water` (`lines` découpées par tronçon de 1 km et `areas` avec îles).
- Schémas `poi.schema.json` et `water.schema.json`, extension de `cli.py` et `verify.py`, tests `compiler/tests/test_osm_poi_water.py`.
