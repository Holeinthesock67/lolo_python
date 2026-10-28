# Lot P22 – Format .world 1.5 : prés, champs et routes voisines

## 1. Objectif

Demande du propriétaire du 27 octobre (« ça manque de vie : animaux, oiseaux, véhicules sur terre et dans le ciel »), deuxième lot de la deuxième vague du décor vivant (P22 à P27, dossier du 27 octobre, validé le même soir). Le format `.world` ne connaît que les forêts, les broussailles et les vergers, et seulement la route du parcours : les animaux (P24) n'ont pas de pré où paître, les tracteurs (P25) pas de champ, et les voitures, camions et bus (P25) pas d'autre route que celle du cycliste. Ce lot ajoute au format, sans rien afficher de neuf :

- trois terrains ouverts dans la couche `vegetation` : `meadow` (pré), `farmland` (champ cultivé) et `grassland` (prairie ou lande), toujours de densité 0 ;
- une couche facultative `roads` : les routes OpenStreetMap du couloir de 400 m, hors de la route du parcours, avec leur sorte, leur nombre de voies, leur sens unique et leur vitesse.

C'est le seul changement de contrat de la deuxième vague : aucun changement IPC, aucune touche.

## 2. À lire

1. `docs/contracts/world_format_v1.md` (§2, §7, §8, §10 et §12), `docs/lots/LOT_I3_osm_batiments_forets.md`, `docs/lots/LOT_I4_osm_poi_eau.md`, `docs/lots/LOT_K4_lecture_couches_osm_godot.md`.
2. Code : `compiler/src/openride_compiler/osm.py`, `osm_layers.py`, `verify.py`, `cli.py`, `writer.py`, `constants.py` ; `engine/scripts/osm_layers.gd`, `vegetation_placer.gd`, `tree_renderer.gd`.

## 3. Prérequis

I3, I4, K4 et T1 (format 1.3) livrés ; W1 a pris la 1.4 (monde vivant), ce lot prend la 1.5.

## 4. Travail demandé

- **Requête Overpass** (`osm.py`) : `landuse` = `meadow`, `farmland` ou `grass`, `natural` = `grassland` ou `heath` (ces deux lignes remplacent la recherche des prés à animaux de P11, déjà comprise), et `highway` parmi les huit sortes de `ROAD_KINDS`. La requête change, donc sa somme de contrôle : la première compilation d'une couche OSM après ce lot télécharge de nouveau les données du parcours, une fois.
- **Terrains ouverts** (`osm_layers.py`) : `landuse=meadow` donne `meadow`, `landuse=farmland` donne `farmland`, `landuse=grass`, `natural=grassland` et `natural=heath` donnent `grassland`, tous de densité `DENSITY_OPEN` (0). Le tronçon d'une zone est celui de son centre (`vegetation_chunk_and_y`) ; un terrain ouvert dont le centre est hors du couloir, mais qui y entre par un bord, prend le tronçon du sommet de son contour le plus proche de la route.
- **Routes voisines** (`osm_layers.py`, section « 2 bis ») : chaque voie OSM est découpée tous les 25 m, coupée à moins de `ROAD_ROUTE_GAP_M` (20 m) de la route du parcours et hors du couloir, puis par tronçon ; un morceau n'est gardé que s'il a au moins deux points et s'éloigne d'au moins `ROAD_PARALLEL_M` (35 m) de la route (une route qui double celle du parcours disparaît). `lanes` vient de la balise `lanes` (1 à 8), sinon 4 sur `motorway` et `trunk`, 1 sur `track` ou un sens unique, 2 ailleurs ; `oneway` est vrai pour `oneway=yes` et toute `motorway` ; `speed_kmh` vient de `maxspeed` en km/h (5 à 150), sinon de `ROAD_DEFAULT_SPEED_KMH`. `y` est le sol sous chaque point.
- **Ligne de commande** (`cli.py`, `writer.py`) : couche `roads` dans `--layers` de `build` et `build-all`, `add-layer <nom>.world roads`, manifeste `layers.roads` (`present`, `version`, `count`, `osm_date`), `{"present": false}` par défaut. Les couches par défaut ne changent pas dans ce lot.
- **Vérification** (`verify.py`) : sorte de végétation parmi les six, densité 0 exacte pour un terrain ouvert et de plus de 0 à 1 sinon, tronçon d'après la même règle que le compilateur ; pour `roads`, identifiant, sorte, voies de 1 à 8, booléen `oneway`, vitesse de plus de 0 à 150, au moins deux points `[x, z, y]`, aucun point à moins de 20 m de la route du parcours, extrémités dans leur tronçon.
- **Contrat** : `world_format_v1.md` §7, nouveau §8 ter, §10, ligne 1.5 du journal ; schémas `vegetation.schema.json` (sortes, densité 0 des terrains ouverts), nouveau `roads.schema.json`, entrée `roads` de `manifest.schema.json`.
- **Engine** (`osm_layers.gd`) : lecture et validation de `roads` (`lines`, coordonnées rendues absolues dans un monde vivant comme les rivières) et des terrains ouverts. Rien ne les affiche encore : `vegetation_placer.gd` n'y plante aucun arbre (sorte absente de `KIND_FACTOR`) et `tree_renderer.gd` y retire les arbres du bruit de fond, comme dans une forêt d'OSM ; P24 et P25 s'en serviront.

## 5. Fichiers concernés

- **Modifiés :** `compiler/src/openride_compiler/constants.py`, `osm.py`, `osm_layers.py`, `verify.py`, `cli.py`, `writer.py` ; `compiler/tests/test_cli_world.py`, `test_terrain.py`, `test_segments_layer.py` (version 1.5) ; `docs/contracts/world_format_v1.md`, `docs/contracts/world/vegetation.schema.json`, `manifest.schema.json` ; `engine/scripts/osm_layers.gd`, `engine/tests/test_osm_layers.gd`, `engine/tests/make_osm_world.py` ; `README.md`, `CLAUDE.md`, `docs/SUIVI_AVANCEMENT.md`, `docs/lots/00_INDEX.md`, `engine/tests/README.md`.
- **Nouveaux :** `compiler/tests/test_osm_open_roads.py`, `compiler/tests/data/osm/sample_open_roads.json` (données inventées, sans lieu réel), `docs/contracts/world/roads.schema.json`.
- **Interdits :** le core, le contrat IPC, `worldgen/` (monde ouvert, série W), `crowd_renderer.gd`, `fauna_renderer.gd`.

## 6. Modifications de contrat autorisées

Format `.world` 1.5, ajout compatible : un `.world` 1.3 reste valide et lisible, un lecteur 1.3 ignore les nouvelles sortes (§7) et la couche inconnue (§10).

## 7. Critères d'acceptation

1. `pytest -q` passe dans le compilateur et `engine/tests/run_engine_tests.sh` passe en entier.
2. Sur les données de test : un pré, un champ et deux prairies (lande et `landuse=grass`), tous de densité 0 ; le champ dont le centre est à 600 m de la route mais le bord à 300 m est gardé au tronçon 1 ; un champ à 1,5 km est écarté.
3. Une route secondaire parallèle à 100 m sur 2,4 km donne trois morceaux (tronçons 0, 1, 2) à 70 km/h ; une rue qui croise la route donne deux morceaux, de part et d'autre ; une route qui suit celle du parcours à 3 m et une piste qui n'en sort pas de 35 m ne donnent rien ; un chemin piéton est ignoré ; autoroute à sens unique et à 3 voies (étiquette), tertiaire à sens unique à 1 voie ; points tous les 25 m au plus, jamais à moins de 20 m du parcours, altitude du sol.
4. `verify` refuse un pré boisé (densité 0,5), une route à 0 voie et un point sur la route du parcours ; `add-layer roads` ne touche pas aux autres couches.
5. L'engine lit les cinq couches du `.world` de test avec les nombres du compilateur, accepte les trois terrains ouverts et ignore une route d'une sorte inconnue, à 0 voie, au sens unique non booléen ou à un point sans altitude.

**Sur le PC cible (le propriétaire) :** rien à voir avant P24 et P25 ; à la première compilation d'un parcours avec les couches OSM, un téléchargement Overpass de plus (la requête a changé), puis `verify` sans problème.

## 8. Hors périmètre

- Affichage des prés et des champs (texture de sol, cultures), des routes voisines et de leur trafic : P24 et P25.
- Couches OSM compilées par défaut au lancement (`DEFAULT_LAYERS`) : décision à part, demandée au propriétaire le 27 octobre.
- Monde ouvert (`worldgen/`, série W) : ses carrés pourront recevoir ces sortes plus tard, sans changer ce lot.

## 9. Livraison

Livré sur la branche `claude/project-thread-rh8cbl`.

- Tests : `compiler/tests/test_osm_open_roads.py` (6 tests, 401 tests collectés dans le compilateur) ; `test_osm_layers.gd` (31 vérifications).
- Reste sur le PC cible : la vérification du §7, à la prochaine compilation d'un parcours avec OSM.
