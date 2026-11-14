# Lot DB3 – Parcours de démonstration « Route du Sud » et « Route du Grand Nord »

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Deux parcours de démonstration pour les neuf biomes qui n'en avaient pas : route de 12 km des oliviers au delta, boucle de 10 km de la taïga à la banquise | Python | DB1, DB2, O38 | Petite | En PR (14 novembre, version 6.0) |

Question du propriétaire du 14 novembre 2026 : « Il y a un parcours démo pour tous les types de biomes ? ». Étude de couverture (hors dépôt) : `/mnt/project-files/statut/COUVERTURE_BIOMES_DEMOS_2026-11-14.md`. Neuf biomes réels n'étaient montrés par aucune démonstration du jeu de base : méditerranéen (seulement dans le tour des six paysages, sorti du jeu de base par DB1), steppe, désert de sable, savane, jungle, zones humides, forêt boréale, toundra, polaire. Choix du propriétaire (carte, 6 h 34) : deux démonstrations, banc des neuf biomes d'abord ; précision à 6 h 35 : « le 6 km c'est court, fais une boucle » pour le Grand Nord ; 12 h 30 : commencer le code sans attendre le banc.

## 1. Objectif

Chaque biome réel du compilateur (`biomes.BIOMES`, hors `reef`, réservé au récif) est montré par au moins une démonstration du jeu de base, sans réseau.

## 2. Contraintes

- **Aucune donnée réelle** : trace, relief et décor inventés, origine fictive 45° N, 2° E, comme les autres démonstrations.
- **Pas d'exception** (principe du 27 octobre) : même générateur et même modèle que le tour des nouveaux paysages (blocs de 2 km, fondus de 300 m, un décor par bloc, `DEMO_SET`). La boucle du Grand Nord est une boucle de `LOOPS` comme le circuit et le volcan, à plusieurs blocs.
- Aucune révision du contrat IPC ni du format des parcours.
- Budgets GPU de #732 (low 8 ms, medium 13 ms, high 16 ms) ; la jungle est le biome le plus dense (environ 69 700 arbres en medium), à vérifier par le banc rBX puis par le banc des parcours.

## 3. Réalisation

- `compiler/src/openride_compiler/demo_biomes.py` :
  - `SUD` et `NORD`, au format de `PAYSAGES` ; `BLOCK_TOURS` réunit les trois tables, `tour_blocks(which)` donne les biomes et les variantes de n'importe quel parcours de `DEMO_SET` (remplace les cas particuliers de `write_demo_set` et de la ligne de commande).
  - **Route du Sud** (`demo-biomes-sud`, `--sud`) : méditerranéen, steppe, désert de sable, savane, jungle, zones humides, 12,1 km, environ 100 m de montée, de −3,4 à +5 %. Le point haut est à la fin de la savane, puis la route descend dans la jungle vers le delta.
  - **Route du Grand Nord** (`demo-biomes-nord`, `--nord`) : boucle de 10 km (`NORD_M`, lobes `NORD_LOBES`) en cinq blocs : taïga, toundra, banquise, toundra, taïga. La banquise est au point le plus éloigné du départ et le plus haut (`NORD_CLIMB_M` = 120 m, environ 130 m de montée avec les ondulations, pente de −6,2 à +5,4 %). Le relief `nord_relief` ne dépend que du point : la boucle revient à son altitude et rien ne fait de marche entre ses deux rives. Les flancs sont dans le relief (`sides` faux) : ceux de `SIDES` dépendent du bloc de la route la plus proche, ce qui ferait une marche à mi-chemin de deux blocs qui se font face.
  - Boucle à plusieurs blocs : `Plan` accepte une boucle de plusieurs biomes si les blocs de 2 km font toute la boucle (sinon `ValueError`) ; `Loop.decor` à `None` donne le décor de chaque bloc (`BLOCKS`).
  - **Correction** : le compilateur centre le repère du `.world` sur le départ de la trace, alors que la boucle fabriquée est centrée sur son milieu. `Plan.s_of_world` (décalage `Plan.offset`, nul sur la route ouverte) sert désormais pour la couche biome, la colonne `surface` et la mer. Sans lui, les tuiles d'une boucle à plusieurs blocs prenaient le biome d'un autre bloc (constaté : taïga à 1,5 % au lieu de 40 %). Sans effet sur le circuit et le volcan, qui n'ont qu'un biome.
  - Huit décors (`_steppe`, `_sand_desert`, `_savanna`, `_jungle`, `_wetland`, `_boreal`, `_tundra`, `_polar`) ; le méditerranéen garde le sien. Les arbres, la faune, les sons et les sols viennent du biome (engine) ; les éléments OSM ne posent que les zones, les maisons, l'eau et les lieux nommés (campement de yourtes, oasis, village de cases, belvédère de la canopée, village sur pilotis et mares du delta, hameau des trappeurs et lac, refuges de la toundra, station de la banquise).
  - `GRADE` et `SIDES` pour les neuf biomes (pentes de la route ouverte, aussi pour `--biome`).
- Poids : 2,6 Mo pour la Route du Sud et 1,9 Mo pour la Route du Grand Nord une fois générées, en quelques secondes au premier lancement. Rien n'est ajouté dans l'AppImage (code seulement).
- Contenus de départ : rien à changer dans `contents.py` (`GAME_DEMOS`) ; une installation existante reçoit les deux parcours à la prochaine installation des contenus de départ.
- `engine/tests/captures_demo.py`, `menu_scenarios/parcours_demo.json` et `contenus.json` : les deux parcours en plus.

## 4. Tests

1. `core/tests/test_biome_demo_world.py` : jeu de base à cinq parcours générés ; `test_every_biome_has_a_game_demo` (chaque biome réel est dans une démonstration du jeu de base, Col du lacet compris) ; `test_sud_route` (parts égales, pentes, point haut, eau du delta, aucune variante) ; `test_nord_loop` (boucle fermée, parts 40 / 40 / 20, banquise au point haut à mi-boucle, taïga au départ, relief continu et borné) ; `test_loop_blocks_must_fill_the_loop`.
2. PC, par le fil de fusion : banc rBX des neuf biomes (`/mnt/project-files/recettes/RECETTE_rBX_neuf_biomes_sans_demo.md`), puis banc low / medium / high des deux parcours dans les budgets GPU, pire image sous 100 ms, aucun contact sur la route, et planche des captures validée par le propriétaire.

## 5. Recette PC

```bash
cd ~/Games/lolo_python/Open_ride_linux
OUT=~/OpenRide/mesures/rDB3_$(date +%F_%H%M)
python3 -m openride_compiler.demo_biomes --out $OUT/routes --sud
python3 -m openride_compiler.demo_biomes --out $OUT/routes --nord
python3 engine/tests/captures_demo.py lancer --out $OUT --qualites low,medium,high --parcours demo-biomes-sud,demo-biomes-nord --native --sans-menus
for w in biomes-sud biomes-nord; do for q in low medium high; do
  python3 engine/tests/sim_bench.py --scenario nominal --world $OUT/routes/$w.world \
    --quality $q --native --probe --speed-kmh 40 --duration 1000 --out $OUT/bench_${w}_$q
done; done
```

À relever par qualité : GPU moyen et p99 par bloc (budgets **8 / 13 / 16 ms**), pire image (< 100 ms), bloc le plus lourd (jungle attendue), contacts des cyclistes du décor : 0 attendu. La planche va au propriétaire.

## 6. Livraison

En PR (14 novembre). PR empilée sur la branche de DB2 (#879), elle-même sur DB1 (#866) : se fusionne après elles ; DJ1 (#877) et SM1 (#878) touchent aussi `DEMO_SET` (conflit simple à résoudre à la remise à jour).
