# Lot I3 – Compilateur : couches OpenStreetMap bâtiments et végétation

## 1. Objectif

Ajouter au compilateur les couches facultatives `buildings` et `vegetation` du format `.world`, tirées d'OpenStreetMap par l'API Overpass, avec un cache brut réutilisable. C'est la partie compilateur du sprint 5 de la SRS ; le rendu (triangulation, arbres) viendra dans un lot engine.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/SRS_v1.1.md` §7 (étape 6, cache brut `~/.cache/openride/osm/`, durées, découpage des requêtes) et §10 (couches).
3. `docs/contracts/world_format_v1.md` : §2 (conteneur, tronçons `chunk_<k>`, écriture atomique), §3 (repère), §6 (bâtiments), §7 (végétation), §10 (lecture et compatibilité), §12.
4. Code du compilateur : `cli.py` (`build`, `add-layer`, option `--layers`), `writer.py`, `verify.py`, `cache.py` (`Downloader` du lot B2 : délais, reprises, cache), `terrain.py` (altitude du sol, pour `base_y`), `frame.py` (`LocalFrame`).

## 3. Prérequis

Lot B2 livré. Partir de `main` à jour.

## 4. Travail demandé

### 4.1 Client Overpass : `compiler/src/openride_compiler/osm.py` (nouveau)

- Requêtes découpées le long de la route : une boîte englobante par tronçon de 1 km, élargie de 400 m (§6), regroupées par paquets pour limiter le nombre d'appels.
- Requête Overpass QL : `way` et `relation` (multipolygones) avec `building`, `landuse=forest`, `natural=wood`, `natural=scrub`, `landuse=orchard` ; sortie `geom`.
- Cache brut : `~/.cache/openride/osm/<sha256 de la requête>.json` ; une requête en cache n'appelle jamais le réseau ; `--offline` interdit tout appel (erreur claire si une réponse manque).
- Réutiliser le `Downloader` du lot B2 (délais d'attente, reprises à délai croissant, réponse 429 respectée). Point d'accès configurable, défaut `https://overpass-api.de/api/interpreter`, avec un `User-Agent` identifiant OpenRide.
- Aucun appel réseau dans les tests : réponses Overpass enregistrées dans `compiler/tests/data/osm/` (petits extraits écrits ou réduits à la main, quelques bâtiments et une forêt avec un trou).

### 4.2 Couches : `compiler/src/openride_compiler/osm_layers.py` (nouveau)

**Bâtiments (§6)** :
- projection dans le repère du monde ; `outer` antihoraire vu du dessus, trous horaires ; premier point non répété ;
- multipolygones : anneaux extérieurs et intérieurs assemblés (ways reliés bout à bout) ;
- `height_m` : `height` (unités « m » tolérées), sinon `building:levels` × 3, sinon valeur stable entre 4 et 10 m dérivée de `id` (hachage, pas d'aléatoire global) ;
- `base_y` : minimum du terrain sous l'empreinte (terrain proche du `.world`, ou altitude du MNT si la couche terrain manque) ;
- bâtiment rattaché au tronçon `k` du point de route le plus proche de son centroïde ; bâtiments à plus de 400 m de la route exclus ;
- polygones dégénérés (moins de 3 points, aire nulle, auto-intersection détectable simplement) ignorés et comptés dans le manifeste.

**Végétation (§7)** : `kind` parmi `wood`, `scrub`, `orchard` ; `density` par défaut 0,8 pour `wood`, 0,4 pour `scrub`, 0,5 pour `orchard` (constantes nommées) ; `vegetation.source` = `osm` dans le manifeste, ou `none` si aucun polygone.

**Manifeste** : `present`, `version`, nombre d'objets, nombre d'objets ignorés, date de la réponse Overpass la plus ancienne utilisée.

### 4.3 Ligne de commande

- `build --layers route,terrain,buildings,vegetation` ; défaut inchangé (`route,terrain`) pour ne pas rendre la compilation dépendante d'Overpass sans le demander.
- `add-layer <world> buildings|vegetation`, écriture atomique de la seule couche (§2).
- `verify` contrôle aussi ces couches : JSON conforme, anneaux fermés implicitement, sens antihoraire, `k` cohérent avec la position.

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/osm.py`, `osm_layers.py`, `compiler/tests/test_osm.py`, `compiler/tests/data/osm/*.json`, `docs/contracts/world/buildings.schema.json`, `docs/contracts/world/vegetation.schema.json`.
- **Modifiés :** `cli.py`, `verify.py`, `writer.py` (manifeste), `constants.py`, `README.md` et `CLAUDE.md` (commandes), `docs/contracts/world_format_v1.md` §12 (une ligne), `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Ajouts compatibles seulement : schémas JSON des deux couches, conformes aux §6 et §7 ; compteurs ajoutés au manifeste de chaque couche ; une ligne au journal des changements. Si un cas réel ne rentre pas dans le format (bâtiment à cheval sur deux tronçons, forêt immense couvrant toute la route), s'arrêter et poser la question.

## 7. Critères d'acceptation

1. `cd compiler && pytest -q` passe en entier sans réseau.
2. Sur les réponses enregistrées : nombre de bâtiments et de zones attendu ; un multipolygone avec trou donne un `outer` et un `holes` corrects ; tous les `outer` sont antihoraires.
3. `height_m` : `height="12 m"` donne 12 ; `building:levels=3` donne 9 ; sans étiquette, la même valeur entre 4 et 10 à chaque compilation.
4. `base_y` égale le minimum du terrain sous l'empreinte à 1 cm près, sur un terrain synthétique incliné.
5. Une seconde compilation avec le même cache et `--offline` produit des fichiers identiques octet pour octet.
6. `add-layer … buildings` sur un `.world` existant ne modifie ni `route.json` ni le terrain (sommes SHA-256 comparées).
7. `verify` rejette un `chunk` dont un anneau est horaire.
8. Un test marqué `network` (désélectionné par défaut, comme celui de Copernicus) interroge réellement Overpass sur une petite zone ; il est lancé une fois et sa sortie figure dans le rapport.

## 8. Hors périmètre

- Rendu des bâtiments et des arbres dans Godot (lot engine à rédiger).
- Toits à deux pans, couverture du sol ESA WorldCover.
- Points d'intérêt et eau (lot I4).

## 9. Livraison (23 octobre 2026, PR #22)

- Client Overpass `osm.py` (cache `~/.cache/openride/osm/<sha256>.json`, découpage par tronçon de 1 km élargi de 400 m, `--offline`).
- Couches `buildings` et `vegetation` dans `osm_layers.py` (assemblage des multipolygones, anneaux `outer` antihoraires et `holes` horaires, `height_m` déterministe, `base_y`).
- Schémas `buildings.schema.json` et `vegetation.schema.json`, extension de `cli.py` et `verify.py`, tests `compiler/tests/test_osm.py` (dont l'essai réseau réel Overpass).
