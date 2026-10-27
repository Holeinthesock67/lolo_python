# Lot W0 – Mesures du monde ouvert : volumes, temps de génération, débit

## 1. Objectif

Le plan de la série W (`docs/2.0/PLAN_SERIE_W.md` §3) repose sur des estimations : taille d'un extrait régional, nombre et poids des tuiles vectorielles, temps de calcul d'un carré de 1 km. Ce lot écrit un script de mesure, exécuté ensuite sur le PC cible par le propriétaire, qui remplace ces estimations par des chiffres avant de figer le contrat (W1). Il livre aussi un décodeur minimal de tuiles vectorielles (MVT), réutilisé par W13.

## 2. À lire

1. `docs/lots/00_INDEX.md` (règles communes, paragraphe « Série W »), `docs/2.0/PLAN_SERIE_W.md` §3, §4 et §9.
2. `docs/contracts/world_format_v1.md` §3 et §5 (repère, tuiles de terrain).
3. Code : `compiler/src/openride_compiler/cache.py` (`Downloader`), `elevation.py` (`CopernicusGlo30Provider`, `SyntheticProvider`), `frame.py` (`LocalFrame`, `utm_zone_of`), `terrain.py` (`RouteAxis`, `blend`, `tile_coords`), `constants.py`.
4. Spécification des tuiles vectorielles Mapbox (MVT 2.1) et schéma OpenMapTiles (couches `transportation`, `building`, `landcover`, `water`, `waterway`, `poi`).

## 3. Prérequis

Aucun. Le lot peut être fait avant la 1.0 : il n'ajoute qu'un outil, sans toucher au core ni à l'engine.

## 4. Travail demandé

### 4.1 Décodeur MVT minimal (`worldgen/mvt.py`)

- Bibliothèque standard seulement (lecture protobuf « varint », champs de longueur, `zigzag`), sans dépendance nouvelle.
- `decode_tile(data: bytes) -> dict[str, Layer]` ; `Layer(name, extent, features)` ; `Feature(id, kind, tags, geometry)` avec `kind` dans `point`, `line`, `polygon` et la géométrie en coordonnées de tuile (entiers de 0 à `extent`). Les anneaux de polygone gardent leur sens (extérieur, trous) selon l'aire signée.
- `tile_to_lonlat(z, x, y, extent, px, py) -> (lon, lat)` (Web Mercator).
- Données compressées en gzip acceptées (détection de l'en-tête `1f 8b`).

### 4.2 Script de mesure (`worldgen/measure.py`, commande `openride-compiler world-measure`)

Arguments : `--lat`, `--lon` (départ), `--heading` (cap en degrés, 0 par défaut), `--km` (longueur du couloir, 10 par défaut), `--region <chemin Geofabrik>` (facultatif, par exemple `europe/france/provence-alpes-cote-d-azur`), `--out <dossier>` (par défaut `~/OpenRide/Cache/monde/mesures/<date>/`), `--offline` (tout depuis le cache, aucune requête), `--synthetic` (relief analytique et routes synthétiques, sans réseau : sert aux tests).

Le script mesure, dans cet ordre, et écrit chaque résultat dès qu'il est connu :

1. **Relief :** tuile(s) Copernicus GLO-30 couvrant le couloir, via `CopernicusGlo30Provider` (cache existant `~/.cache/openride/dem/`) : taille, temps de téléchargement, débit ; « déjà en cache » si présente.
2. **Tuiles vectorielles :** liste des tuiles OpenFreeMap zoom 14 qui touchent un couloir de 2 km de large autour de la ligne droite partant du départ au cap donné, sur `--km` ; URL lue dans le TileJSON `https://tiles.openfreemap.org/planet` (champ `tiles`), jamais codée en dur ; téléchargement séquentiel avec l'en-tête `User-Agent` du compilateur, au plus 4 requêtes par seconde ; nombre, taille totale, taille moyenne et maximale, temps, débit ; décodage par `mvt.py` et nombre d'objets par couche. Fichiers rangés dans `<cache>/brut/tuiles/14/<x>/<y>.mvt` (arborescence du plan §4).
3. **Extrait régional (seulement avec `--region`) :** téléchargement de `https://download.geofabrik.de/<region>-latest.osm.pbf` dans `<cache>/brut/osm/` ; taille, temps, débit. Pas de conversion (lot W3). Le script affiche la taille annoncée par l'en-tête `Content-Length` et demande confirmation au-delà de 1 Go, sauf `--yes`.
4. **Génération :** pour chaque carré de 1 km traversé par la ligne (grille fixe de la zone UTM, plan §4), dans un repère dont l'origine est le coin de la grille de 5 km le plus proche du départ :
   - grille proche de 101 × 101 points interpolée dans le relief ;
   - routes du carré (couche `transportation` des tuiles vectorielles, ou routes synthétiques) projetées dans le repère, densifiées à 10 m, altitude tirée du relief ;
   - fondu du terrain avec toutes les routes du carré (`RouteAxis` et `blend` de `terrain.py`, demi-largeur 3 m) ;
   - lecture des bâtiments, forêts et eau du carré ;
   - écriture des fichiers dans un dossier temporaire du dossier de sortie (mêmes formats que le `.world`).
   Temps mesurés par étape et au total, par carré : médiane, 95e centile, maximum ; taille écrite par carré.
5. **Grille lointaine :** une tuile de 5 km (101 × 101 à 50 m) : temps et taille.

Rapport : `rapport.json` (toutes les valeurs, versions de Python, numpy et du compilateur, nombre de cœurs) et `rapport.md` en français, qui reprend les tableaux du plan §3.2 et §3.3 avec les valeurs mesurées et le rapport entre temps de calcul et temps disponible à 30 km/h et à 70 km/h. Aucune coordonnée n'est écrite dans le dépôt ; le rapport reste dans `--out`.

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/worldgen/__init__.py`, `worldgen/mvt.py`, `worldgen/measure.py`, `compiler/tests/test_mvt.py`, `compiler/tests/test_world_measure.py`.
- **Modifiés :** `compiler/src/openride_compiler/cli.py` (sous-commande `world-measure`), `docs/OUTILS_DE_TEST.md` (une ligne), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** le core, l'engine, les contrats.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `(cd compiler && python -m pytest -q)` passe en entier, sans réseau.
2. `test_mvt.py` : une tuile encodée dans le test (encodeur de test de quelques lignes) avec un point, une ligne et un polygone à trou est décodée à l'identique (identifiants, balises, coordonnées, sens des anneaux), compressée ou non ; `tile_to_lonlat` redonne les coins de la tuile à 1e-9 près.
3. `world-measure --synthetic --km 3 --out <tmp>` écrit `rapport.json` et `rapport.md`, avec au moins 3 carrés générés, des temps positifs et des tailles égales à celles des fichiers écrits.
4. Avec un faux serveur (fonction de téléchargement injectée), `--offline` ne fait aucune requête et relit le cache ; une tuile déjà en cache n'est pas retéléchargée.
5. Aucun fichier n'est écrit hors de `--out` et des dossiers de cache (vérifié par le test avec des dossiers temporaires et la variable `OPENRIDE_DEM_CACHE`).

**Sur le PC (le propriétaire) :** `openride-compiler world-measure --lat 44.174 --lon 5.279 --heading 90 --km 10` (Mont Ventoux), puis la même commande avec `--region europe/france/provence-alpes-cote-d-azur`. Le rapport est relu et ses chiffres reportés dans le plan §3 par le lot W1.

## 8. Hors périmètre

- Conversion de l'extrait en base SQLite (W3), graphe routier (W4), profils d'arêtes (W5).
- Toute mesure de rendu (W16).
