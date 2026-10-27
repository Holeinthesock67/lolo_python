# Lot W3 – Extrait régional OpenStreetMap converti en base locale SQLite

## 1. Objectif

Télécharger une fois un extrait régional Geofabrik (`.osm.pbf`) et le convertir en une base SQLite compacte et indexée, qui ne garde que ce dont le monde ouvert a besoin. La même base, remplie par les tuiles vectorielles (W13), est la seule source de routes et de décor pour le graphe (W4) et le générateur (W7).

## 2. À lire

1. `docs/2.0/PLAN_SERIE_W.md` §3.1, §4 et §7 (risques 1, 2, 10), `LOT_W1_contrat_monde_vivant.md` §4.5 (routes admises), `LOT_W2_cache_local_monde.md`.
2. Code : `compiler/src/openride_compiler/osm.py` (`User-Agent`, règles d'usage), `osm_layers.py` (balises lues pour bâtiments, végétation, eau, points d'intérêt : `compute_building_height`, `_vegetation_kind_and_density`, `_water_area_kind`, `_poi_kind_and_radius`).
3. Documentation de `pyosmium` (classe `SimpleHandler`, `apply_file` avec `locations=True`, assemblage des multipolygones par `area`).

## 3. Prérequis

W2 livré.

## 4. Travail demandé

### 4.1 Schéma de la base (version 1, utilisé aussi par W13)

- `meta(key TEXT PRIMARY KEY, value TEXT)` : `schema_version` = `1`, `source` (`geofabrik` ou `openfreemap`), `region`, `osm_date`, `bbox` (`min_lon,min_lat,max_lon,max_lat`), `created`.
- `roads(id INTEGER PRIMARY KEY, osm_id INTEGER, highway TEXT, road_class TEXT, surface TEXT, bridge INTEGER, tunnel INTEGER, layer INTEGER, oneway INTEGER, name TEXT, nodes BLOB, coords BLOB)` : `nodes` = identifiants de nœuds `int64` petit-boutistes ; `coords` = paires (lon, lat) `float64` petit-boutistes ; `road_class` selon W1 §4.5. Les voies exclues (autoroutes, voies rapides, non revêtues, interdites) sont gardées avec `road_class` = `x` pour le dessin de la carte, jamais pour le graphe.
- `areas(id INTEGER PRIMARY KEY, osm_id TEXT, kind TEXT, tags TEXT, geom TEXT)` : `kind` dans `building`, `wood`, `scrub`, `orchard`, `water` ; `tags` = JSON des seules balises utiles (`height`, `building:levels`, `building`, `colour`, `natural`, `landuse`, `water`, `name`) ; `geom` = JSON `{"outer": [[lon, lat], …], "holes": [[…]]}` (un multipolygone donne une ligne par anneau extérieur).
- `lines(id INTEGER PRIMARY KEY, osm_id TEXT, kind TEXT, tags TEXT, coords BLOB)` : cours d'eau `river`, `stream`, `canal`.
- `points(id INTEGER PRIMARY KEY, osm_id TEXT, kind TEXT, name TEXT, lon REAL, lat REAL)` : points d'intérêt des types du format (§8) et, pour la recherche du menu, `place` (`city`, `town`, `village`, `hamlet`) et `mountain_pass`.
- Index R-tree : `roads_rt`, `areas_rt`, `lines_rt`, `points_rt` (`id, min_lon, max_lon, min_lat, max_lat`).
- Module `worldgen/osmdb.py` : création du schéma, `OsmDb(path)` en lecture seule, requêtes par emprise (`roads_in(bbox)`, `areas_in(bbox, kinds)`, `lines_in`, `points_in`, `search_places(text, limit)` insensible à la casse et aux accents).

### 4.2 Conversion (`worldgen/region.py`)

- Téléchargement par `Downloader` (reprises, fichier temporaire) de `https://download.geofabrik.de/<region>-latest.osm.pbf` vers `brut/osm/` ; somme MD5 vérifiée avec le fichier `.md5` voisin publié par Geofabrik.
- Lecture par `pyosmium` en un passage (nœuds avec positions, chemins, relations multipolygones par le gestionnaire d'aires), écriture par lots de 10 000 lignes dans une base temporaire, index créés à la fin, `VACUUM`, puis renommage atomique en `brut/osm/<region>.sqlite`.
- Le `.osm.pbf` est supprimé après conversion, sauf `--keep-pbf`. Mémoire maximale visée : 2 Go pour une région française (positions des nœuds en index fichier `sparse_file_array` si nécessaire).
- Enregistrement dans le cache (W2) avec `region` et les versions (`schema_version`, `osm_date`).
- Commandes : `openride-compiler region-add <region> [--keep-pbf]` et `openride-compiler region-update <region>` (retélécharge si Geofabrik publie un fichier plus récent, jamais pendant une séance) ; `region-list`.
- Dépendance : `osmium` (pyosmium) dans un extra `worldgen` de `compiler/pyproject.toml`, importé seulement par `region.py` ; message clair si l'extra n'est pas installé. Ajout à `constraints.txt` avec une version qui a des roues pour Python 3.11 à 3.14.

## 5. Fichiers concernés

- **Nouveaux :** `worldgen/osmdb.py`, `worldgen/region.py`, `compiler/tests/test_osmdb.py`, `compiler/tests/test_region.py`, `compiler/tests/data/mini_region.osm` (fichier XML de quelques dizaines d'objets inventés, lu aussi par pyosmium).
- **Modifiés :** `compiler/pyproject.toml`, `constraints.txt`, `compiler/src/openride_compiler/cli.py`, `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** core, engine, contrats.

## 6. Modifications de contrat autorisées

Aucune (la base est interne au générateur).

## 7. Critères d'acceptation

1. `pytest` passe dans `compiler/` sans réseau ; les tests qui demandent `osmium` sont sautés proprement s'il n'est pas installé, et passent quand il l'est.
2. Conversion de `mini_region.osm` : nombre attendu de lignes par table ; une autoroute et un chemin `surface=gravel` ont `road_class = x` ; un bâtiment multipolygone avec trou donne `outer` et `holes` ; balises inutiles absentes.
3. Requête par emprise : renvoie exactement les objets qui la touchent (comparé à un filtre en Python pur).
4. `search_places("evian")` trouve « Évian-les-Bains » (insensible aux accents).
5. Base écrite de façon atomique : une conversion interrompue (exception injectée) ne laisse ni base partielle ni fichier temporaire.
6. Faux serveur : somme MD5 fausse → erreur claire, rien d'écrit.

**Sur le PC (le propriétaire) :** `region-add europe/france/provence-alpes-cote-d-azur` : durée, mémoire maximale et taille de la base notées dans la PR de recette.

## 8. Hors périmètre

Graphe (W4), tuiles vectorielles (W13), mise à jour automatique.
