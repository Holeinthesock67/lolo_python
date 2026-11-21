# Lot EA2 – Eau au loin en monde ouvert

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Grands lacs (plus de 1 km²) écrits avec les tuiles lointaines de 5 km du monde ouvert, sol lointain abaissé dessous (règle EA1), dessinés au-delà des carrés proches | Python, GDScript | EA1 (en PR #881), W7, W10 | Moyenne | En revue (PR à valider : essai PC, mesures low, medium, high et captures) |

## 1. Objectif

Demande du propriétaire du 14 novembre (série EA, `docs/6.0/PLAN_SERIE_EA.md`). En monde ouvert, l'eau n'existe que dans les carrés de 1 km à moins de 1,5 km de la route, et l'engine ne lit leur couche eau qu'à 300 m des tronçons de route ; les tuiles lointaines de 5 km (rayon 12 km) n'ont que le relief. Un grand lac vu depuis une hauteur ou depuis l'autre rive disparaît donc au-delà de quelques centaines de mètres : on voit le fond du MNT (le lac aplati par Copernicus, sans surface).

## 2. Règle

- **Grand lac** (`squares.far_lakes`) : lacs, étangs et réservoirs de la base OSM de la séance (extrait régional ou tuiles vectorielles) dont l'aire, **morceaux réunis**, dépasse `FAR_LAKE_MIN_M2` (1 km²). Les tuiles vectorielles coupent un lac en morceaux qui se touchent au bord des tuiles : deux morceaux dont des sommets sont à moins de `FAR_LAKE_JOIN_M` (5 m) forment un même lac ; les morceaux sont cherchés jusqu'à `FAR_LAKE_SEARCH_M` (2 km) autour de la tuile lointaine. La mer n'est pas concernée (lots U9 et W23).
- **Niveau** : celui des carrés proches, `water_terrain.lake_level` sur le même polygone et le même MNT (lot EA1) ; un lac a donc la même altitude au loin et de près.
- **Sol lointain** : chaque échantillon de la tuile lointaine (pas de 50 m) dans un grand lac descend à `level_y − 1 m` au plus (`water_terrain.sink_grid`, comme EA1) ; l'engine le dessine ensuite `FAR_DROP_M` (2 m) plus bas, comme tout le lointain.
- **Fichier** : grille du niveau des lacs, 101 × 101 `float32` au pas de 50 m comme `terrain/far/`, NaN hors de l'eau, écrite à côté du relief (`genere/<zone>/far/<IX5>_<IN5>.water` du cache, supprimée avec lui) et liée dans la séance en `water/far/tile_<ix>_<iz>.f32` ; pas de fichier sans eau. Format : contrat `world_format_v1.md` §13 (ajout compatible).
- **Données** : avec les tuiles vectorielles, le générateur ne télécharge rien de plus pour l'eau lointaine (la file et les messages de la séance n'attendent pas le réseau) : il verse dans la base les tuiles déjà sur le PC de la tuile lointaine et de sa marge (`TileSource.load_present`), en plus de celles du graphe (cellules de 5 km à moins de 3 km de la route). S'il en manque, la tuile est écrite avec la version `"water": "partial"` et refaite à une séance suivante. Les versions d'une tuile lointaine comprennent désormais la base OSM (schéma, date, région) et `FAR_WATER_VERSION` : les tuiles du cache se refont à la séance suivante.

## 3. Dessin (engine)

`engine/scripts/far_water.gd`, appelé par `world_streamer.gd` dans la tâche de fond de chaque tuile lointaine : une cellule de 50 m dont un coin est dans l'eau reçoit un plan au niveau du lac, posé `FAR_WATER_DROP_M` (0,5 m) sous ce niveau. Ce plan est :

- au-dessus du sol abaissé, proche (`level − 1`) comme lointain (`level − 1 − 2`) : l'eau se voit aussi sur les carrés proches dont la couche eau n'est pas chargée ;
- sous la surface des plans d'eau proches (`level + 0,05`) : là où ils sont dessinés, ils le couvrent sans scintillement ;
- coupé par le relief à la rive : la rive lointaine est la ligne où le sol sort du plan (la cellule à moitié dans l'eau est entière, le relief de la berge la recouvre).

Les cellules voisines d'une même ligne au même niveau forment une bande : quelques dizaines de quadrilatères par tuile. Le plan est une seconde surface du maillage de la tuile lointaine (matériau des plans d'eau proches, reflets du lot P12 compris), libérée avec elle. Relief exagéré (lot Q2) : altitude passée par `display_y`.

## 4. Hors périmètre

- Parcours compilés : leur couche eau couvre déjà le couloir du parcours ; l'horizon (50 km) reste sans eau.
- EA3 (grandes rivières en surface), EA4 (ponts dessinés).
- La mer lointaine du monde ouvert (lot W23).

## 5. Tests

- `compiler/tests/test_far_water.py` : lac coupé en deux morceaux de moins de 1 km² chacun réuni en un grand lac, même niveau, sol lointain abaissé, aire mouillée ; étang seul écarté ; niveau lointain égal à celui des carrés proches ; tuile sans grand lac : relief intact et pas de fichier d'eau ; version `partial` refaite puis gardée ; lien dans la séance et suppression avec la tuile.
- `engine/tests/unit/test_far_water.gd` : bandes par ligne, aire des cellules mouillées, plan à `level − 0,5`, UV en coordonnées de la séance, faces vers le haut, deux niveaux, relief exagéré, fichier relu.

## 6. Recette sur le PC

- Suites `compiler` (pytest) et engine (`run_engine_tests.sh`).
- Monde ouvert au-dessus d'un grand lac : scénario `engine/tests/menu_scenarios/ea2_lac_loin.json` (gabarit `depart_monde_ouvert`, recherche « Sevrier », rive ouest du lac d'Annecy, même départ que `ea1_lac` : la rive est, à 2 ou 3 km, n'est dessinée que par l'eau lointaine ; 5 minutes, une capture par minute ; Montmin ne voyait pas le lac et Talloires mène à une route sans issue), `menu_bench.py --native --scenario ea2_lac_loin --qualite low|medium|high --captures ecrans`, sur la branche puis sur celle de EA1 (#881, base de la PR) ; GPU (budgets 8, 13 et 16 ms), temps des tâches `far` et `eau_lointaine` de la sonde, temps du générateur par tuile lointaine et tuiles vectorielles téléchargées.
- Captures validées par le propriétaire avant fusion.
