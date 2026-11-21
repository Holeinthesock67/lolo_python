# Lot EA3 – Grandes rivières en surface

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Grandes rivières cartographiées en surface (`water=river`, classe `river` des tuiles vectorielles) dessinées avec un niveau qui descend le long du cours, sol abaissé dessous, ruban coupé ; parcours compilés et monde ouvert (format 1.10) | Python, GDScript | EA1 | Moyenne | En revue (PR à valider : essai PC, mesures low, medium, high et captures) |

## 1. Objectif

Demande du propriétaire du 14 novembre (série EA, `docs/6.0/PLAN_SERIE_EA.md`), lancée le 16 novembre. Avant ce lot, une grande rivière (Rhône, Loire, Isère…) n'existait que par son axe `waterway=river` : un ruban de 6 m de large qui suit le relief, alors que son lit cartographié (`natural=water` + `water=river`, ou classe `river` de la couche `water` des tuiles OpenMapTiles) fait souvent 100 à 300 m. Ces surfaces étaient écartées, faute de niveau : un plan horizontal (règle des lacs) ne convient pas à une rivière qui descend de plusieurs mètres par kilomètre.

## 2. Règle (une seule, parcours compilés et monde ouvert)

`compiler/src/openride_compiler/river_surface.py` :

- **Niveau en un point** (`RiverLevels.at`) : nœuds d'une grille de 10 m (`RIVER_SAMPLE_M`) alignée sur le repère, dans l'eau de la rivière (îles exceptées) ; MNT brut à ces nœuds. Pour un point : nœuds à moins de 150 m (`RIVER_LEVEL_RADIUS_M`), plan ajusté à leurs altitudes (la pente du cours ne biaise rien), puis quart le plus bas des écarts au plan (`RIVER_LEVEL_QUANTILE`, écarte les nœuds de bord mêlés à la berge par l'interpolation du MNT). Le MNT Copernicus aplanit les grandes rivières en marches qui descendent : la fenêtre les lisse en une pente. Moins de trois nœuds : MNT au point. C'est la règle des lacs d'EA1 (MNT dans l'eau, valeur basse) sur une fenêtre glissante au lieu du plan d'eau entier.
- **Découpe** (`clip_to_rect`) : une rivière peut faire des dizaines de kilomètres ; elle est découpée par carré de 1 km de la grille du repère (`RIVER_CELL_M` : tuiles proches d'un parcours, carrés du monde ouvert). Découpe de Weiler-Atherton sur un rectangle : un bras qui sort et rentre donne deux morceaux, une île coupée par le bord devient une échancrure, sans côté dégénéré. Deux carrés voisins calculent exactement les mêmes points de coupe, et les côtés densifiés (`RIVER_EDGE_STEP_M`, 20 m) reçoivent les mêmes points dans les deux sens.
- **Surface** : aire `kind = river` du format 1.10, avec `outer_y` et `holes_y` (altitude de chaque sommet) ; `level_y` = médiane, pour un lecteur d'avant 1.10. L'engine (`water_mesh.gd`) pose chaque sommet à son altitude ; sans ces listes (ou de mauvaise taille), surface plane à `level_y`.
- **Sol** : abaissé sous la surface à `niveau − WATER_SINK_M` (1 m) comme sous un lac, chaussée hors pont gardée (`water_terrain.sink_grid`, niveau lu en chaque échantillon).
- **Ruban** : le cours d'eau en ligne s'arrête à l'entrée de la surface (un point dedans gardé, posé au niveau de la surface, pour qu'il la rejoigne) ; il reste pour les rivières sans surface.
- Tout ne dépend que des coordonnées, des polygones et du MNT : le niveau d'un point est le même quel que soit le carré qui le calcule (bords communs identiques au bit près, testé).

## 3. Branchements

- **Parcours compilés** : `osm_layers.build_osm_layers` met de côté les rivières, puis `river_surface.add_route_rivers` les découpe par carré de 1 km près de la route (bande `OSM_BAND_M`), range chaque morceau au tronçon le plus proche de son centre, calcule les altitudes et coupe les rubans. `cli._sink_under_water` reçoit le MNT brut pour abaisser le sol des rivières (`build`, `add-layer terrain`, `add-layer water`).
- **Monde ouvert** : sorte d'aire `river` dans la base OSM (`osmdb.area_kind`, extraits Geofabrik : base à refaire avec `region-add` pour voir les rivières) et dans la base des tuiles vectorielles (classe `river` ; `CONVERT_VERSION` 2 : la base `tuiles.sqlite` est revidée au premier lancement et reversée depuis les tuiles du cache, sans téléchargement ; les surfaces y sont maintenant découpées au bord de la tuile par la même découpe). `squares.square_water` découpe chaque rivière à la fenêtre du carré élargie de 170 m (nœuds du niveau), `square_terrain` abaisse le sol, `square_layers` écrit les morceaux du carré et coupe les rubans ; `WORLDGEN_VERSION` 4 (3 pris par EA4). Un générateur d'avant EA3 ne lit pas la sorte `river` : une base déjà convertie ne change rien à `main`.
- **Format** 1.10 (`FORMAT_VERSION`), schéma `water.schema.json`, contrat §8 et journal ; `verify` accepte `river`.

## 4. Hors périmètre

- EA2 : eau au loin en monde ouvert (lacs et rivières sur les tuiles lointaines).
- EA4 : ponts dessinés.
- Canaux en surface (`water=canal`), eaux intermittentes : non dessinés en surface (questions ouvertes du plan).
- Bateaux sur les rivières : aucun (les boucles de `boat_model.gd` restent sur les lacs et la mer).

## 5. Tests

`compiler/tests/test_river_surface.py` : découpe (bras qui sort et rentre, île coupée, somme des morceaux de toutes les cases égale au polygone sur 60 polygones tirés au hasard, points de coupe et densification identiques entre voisins) ; niveau qui descend le long d'une vallée en marches, sous les berges, indépendant de la fenêtre ; ruban coupé ; parcours compilé (`build` avec une rivière de 3,8 km le long de la route : morceaux par carré, schéma, `verify`, altitudes qui descendent, plus de ruban dedans, sol abaissé, route intacte ; `add-layer water` rejoué ne change rien) ; monde ouvert (deux carrés voisins : mêmes sommets et mêmes altitudes au bord commun, sol identique au bord, ruban coupé, version 3) ; tuiles vectorielles (classe `river` gardée, base d'avant EA3 revidée). `engine/tests/unit/test_water_mesh.gd` : aire `river` acceptée, sommets à leur altitude, île ouverte, repli plan si les listes ne correspondent pas.

Coût mesuré (générateur, sans écran) : rivière sinueuse de 40 km et 40 000 sommets, 300 m de large, dans un carré : 0,5 s (découpe, nœuds, altitudes et sol), contre 0,05 s pour un carré sans rivière.

## 6. Recette sur le PC

- Suites `compiler`, `core` et tests du moteur (`run_engine_tests.sh`), tests graphiques (`run_visual_tests.sh`).
- Monde ouvert au bord d'une grande rivière : scénario `engine/tests/menu_scenarios/ea3_riviere.json` (recherche « tournon », Tournon-sur-Rhône, route en rive droite du Rhône, 5 minutes, une capture par minute ; en-têtes `reseau` et `caches_reels`), `menu_bench.py --native --scenario ea3_riviere --qualite low|medium|high --captures ecrans`. **Sur `main` d'abord, puis sur la branche** (la branche revide et reverse la base des tuiles du cache ; `main` ne lit pas la nouvelle sorte, l'ordre inverse marche aussi, mais `main` d'abord montre l'avant sans rien changer). GPU (budgets 8, 13 et 16 ms), temps par carré du générateur (journal du générateur).
- Captures validées par le propriétaire avant fusion.
