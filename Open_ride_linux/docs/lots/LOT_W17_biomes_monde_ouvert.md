# Lot W17 – Biomes dans le monde ouvert

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Biomes dans le monde ouvert : couche biome calculée par le générateur, relue par l'engine en roulant, ligne « Biome » expliquée sur l'écran du cap | Python + GDScript | W8, W10, W11, U2, U4, U5, U16, U24 (livrés) | Moyenne | En revue (PR à valider : mesures low, medium, high et captures) |

## 1. Objectif

Le monde ouvert ne connaissait pas les biomes : le générateur n'écrivait pas de couche biome, le décor prenait le biome par défaut du thème (prairie tempérée) sauf réglage forcé. Demande du propriétaire du 12 novembre : faire suivre les biomes en monde ouvert, et expliquer le fonctionnement dans le menu du monde ouvert (biome automatique ou forcé, ce qui change à l'écran).

## 2. À lire

`docs/2.0/PLAN_SERIE_W.md`, `docs/contracts/world_format_v1.md` §8 quater et §13, `compiler/src/openride_compiler/biomes.py`, `regional.py`, `landcover.py`, `worldgen/process.py`, `worldgen/squares.py`, `worldgen/store.py`, `engine/scripts/biome_layer.gd`, `world_streamer.gd`, `world_menu_model.gd`, `world_menu_view.gd`.

## 3. Travail demandé

- **Générateur** (`worldgen/biome_tiles.py`) : une tuile de biome par carré de 1 km et par tuile lointaine de 5 km, avec la règle du compilateur (`biomes.classify_level`, `regional.assign_variants`) : WorldCover, broussailles et vergers de la base OSM du monde ouvert, altitude, carte de Köppen, variante régionale. Repère de la zone UTM : une tuile du cache sert à toute séance. Cache : `genere/<zone>/biome/near|far/`, entrées de sorte `biome` (éviction, reconstruction de l'index, `cache-clean`). Liée avant la tuile de terrain.
- **WorldCover** : lu pendant le préchargement pour le départ, puis en avance dans un fil (10 km autour du bout de la route engagée, comme le relief) ; ensuite le calcul ne lit que le cache. Une tuile faite sans WorldCover note `"landcover": "absent"` et se refait à la séance suivante.
- **Manifeste** : `layers.biome` dès l'ouverture (`present`, `forced: null`, sources, attribution WorldCover).
- **Engine** : `biome_layer.forget_missing`, appelé par `world_streamer.swap_route` pour chaque tuile de terrain arrivée : une absence notée trop tôt est oubliée.
- **Menu** : 4e ligne « Biome » de l'écran du cap, même réglage que Réglages › Graphisme › Biome du décor (`set_setting` de `render.biome`, aucune commande IPC nouvelle) ; explication sous les lignes, automatique ou forcé. Aide du réglage et guide §4 bis complétés.



## 4. Hors périmètre

- Couche biome de « Col du lacet » (accord du propriétaire, 12 novembre) : sortie de ce lot le 12 novembre, parce qu'elle change l'image du parcours de démonstration, donc les références des tests graphiques (SSIM, ciel en haut de l'image), et qu'elle demande des captures validées à part. Travail gardé dans `/mnt/project-files/patches/w17_col_du_lacet_biome.patch` (forêt tempérée et alpages, route en alpage, `synthetic_biome.py`), pour un lot suivant.
- Mer et plages (U3, U9 #844) : lot suivant, après la fusion de #844 (le générateur ignore encore l'océan).
- Horizon de 40 km du Japon (JP4). La zone Japon du classement (#841) suivra d'elle-même : même règle.
- Saisons (U13) : branchement dans `main.gd` prévu ailleurs.

## 5. Tests

`compiler/tests/test_worldgen_biome.py` (tuiles liées par séance et valides, même résultat que le calcul d'ensemble du compilateur, bords communs identiques, tuile lointaine, cache, WorldCover à l'ouverture puis cache seul, vergers OSM) ; `engine/tests/unit/test_biome_model.gd` (absence oubliée), `test_world_menu_model.gd`, `test_world_menu_view.gd` (ligne et explication).

## 6. Recette sur le PC

Scénario `engine/tests/menu_scenarios/w17_cap.json` (`menu_bench.py --native --scenario w17_cap --qualite low|medium|high --captures ecrans`) : recherche par nom, écran du cap, ligne Biome automatique puis forcée, 3 minutes de balade avec une capture par minute.
Mesures GPU en low, medium et high (budgets 8, 13 et 16 ms) sur `sim_bench.py --world ouvert` et en monde ouvert réel ; captures de l'écran du cap et d'une balade qui change de biome, validées par le propriétaire avant fusion.
