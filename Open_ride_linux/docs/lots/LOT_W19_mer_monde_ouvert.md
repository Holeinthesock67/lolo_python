# Lot W19 – Mer et plages en monde ouvert

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Mer, côte et plages du monde ouvert : le générateur écrit la mer et la couche côte de chaque carré, comme le compilateur | Python | W7, W13, U3, U9 (livrés) | Moyenne | En PR (banc PC à faire en low, medium et high) |

## 1. Objectif

Les parcours compilés au bord de la mer ont, depuis U3 et U9, une mer animée jusqu'à l'horizon, l'écume le long du rivage et des plages. En monde ouvert, rien de tout cela : la base locale ne gardait ni la côte ni les plages, et les carrés n'avaient pas de couche `coast`. Une balade au départ d'une ville côtière montrait un terrain plat à 0 m à la place de la mer.

## 2. À lire

`compiler/src/openride_compiler/coast.py` (U3), `worldgen/osmdb.py` (W3), `worldgen/vector_tiles.py` (W13), `worldgen/squares.py` (W7), `docs/contracts/world_format_v1.md` §8 quinquies et §13, `engine/scripts/osm_layers.gd` (`load_chunk_live`) et `osm_streamer.gd` (mer, écume, plages, `sea_horizon`).

## 3. Travail

- **Base locale, schéma 2** (`osmdb.py`) : mêmes tables, sortes en plus : lignes `coastline` (la mer à droite, règle d'OSM) et `cliff`, surfaces `beach` (`natural=beach` ou `natural=sand`, étiquette `surface` gardée). Extrait régional (`region.py`) : les étiquettes d'OSM. Une base de schéma 1 est refusée : un extrait se met à jour par `region update`, la base des tuiles est refaite depuis les tuiles du cache (sans réseau).
- **Tuiles vectorielles** (`vector_tiles.py`) : le schéma OpenMapTiles n'a pas de ligne de côte, mais la mer (`water`, classe `ocean`). Ses contours, découpés à la tuile, donnent des lignes `coastline`, sans les côtés qui longent le bord de la tuile, orientés la mer à droite (`coast_runs`) ; le sable `landcover` (`beach`, `sand`) donne les plages. La base reçoit donc la même chose qu'avec un extrait.
- **Carrés** (`square_coast.py`, appelé par `square_layers`) : les lignes de côte à moins de 5 km sont recollées (bouts soudés à moins de 3 m, coupure des tuiles), coupées au carré, et la mer se referme comme une cellule du compilateur (`close_sea`). Un carré que la côte ne traverse pas est en mer si son centre est du côté mer de la côte la plus proche (pseudo-normale au plus près d'un sommet), sinon à terre. Le rivage (`classify_shore`, `shore_runs`) et les plages qui touchent la côte suivent les règles du compilateur. Résultat : aires `sea` (niveau 0) dans `water.json`, couche `coast.json` (éventuellement vide) dans chaque carré ; nombres `sea`, `coast_lines`, `beaches` dans `meta.json`.
- **Séance** (`process.py`, `store.py`) : `coast/tile_<ix>_<iz>.json` lié comme les autres couches ; `layers.coast` présent dans le manifeste dès l'ouverture ; une ligne du journal par carré avec mer ou côte (« carré … : mer (n aire(s)), m tronçon(s) de côte, p plage(s) »).
- **Engine** : rien à changer. `load_chunk_live` lisait déjà `coast` et décalait ses coordonnées ; la mer, l'écume, les plages et l'anneau d'horizon viennent de U9.
- Contrat : ajout compatible au §13 du format (`coast/` des mondes vivants, mer découpée au carré), sans changement des schémas.

## 4. Tests

- `compiler/tests/test_world_coast.py` : lignes de côte d'une tuile (bord retiré, orientation), lignes et plages versées dans la base, base de schéma 1 refaite, étiquettes d'un extrait, soudure et côté mer, carré à cheval sur deux tuiles (une seule aire de mer, surface attendue à 2 % près, côte vers l'est, plage de sable), carré en pleine mer, carré à terre, carré sans côte (couche vide), séance complète sur tuiles vectorielles (manifeste, liens, mer et côte).
- `engine/tests/unit/test_live_world.gd` : mer et côte d'un carré relues aux positions absolues, couche `coast` présente au manifeste.

## 5. Recette

Sur le PC, avec le réseau (tuiles OpenFreeMap et relief Copernicus de la côte basque) : `python3 engine/tests/menu_bench.py --native --scenario w19_mer --qualite low` (puis `medium`, `high`), sonde de performance comprise. Le scénario cherche « biarritz » dans la liste des villes, accepte le départ et le cap, attend « Monde ouvert prêt » et une ligne « mer ( » du générateur, puis capture le départ et trois vues de la balade. Juger : mer animée et écume visibles, plage au bord, horizon marin, budgets GPU (8, 13 et 16 ms) et images de plus de 50 et 100 ms.

## 6. Hors périmètre

Ports, digues et jetées ; marées ; ferries (une route sur la mer de plus de 5 km de la côte reste à terre).
