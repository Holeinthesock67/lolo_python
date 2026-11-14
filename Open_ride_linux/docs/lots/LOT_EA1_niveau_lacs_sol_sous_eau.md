# Lot EA1 – Niveau commun des lacs et sol abaissé sous l'eau

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Niveau d'un plan d'eau pris dans le MNT du lac (même niveau pour tous ses morceaux), sol abaissé sous l'eau, parcours compilés et monde ouvert | Python | I4, W7, U3 (livrés) | Petite | En revue (PR à valider : essai PC, mesures low, medium, high et captures) |

## 1. Objectif

Demande du propriétaire du 14 novembre (série EA, `docs/6.0/PLAN_SERIE_EA.md`). Deux défauts vus dans le code des plans d'eau :

- **Marches dans un grand lac en monde ouvert.** Les tuiles vectorielles (zoom 14, environ 1,7 km) découpent un lac en morceaux ; chaque morceau prenait pour niveau le minimum du terrain sur **son** contour, donc des niveaux différents.
- **Sol qui perce la surface.** Le niveau était le point le plus bas de la rive : un exutoire, le pied d'un barrage ou l'interpolation du MNT à 30 m tirait tout le lac vers le bas, et le relief (jamais modifié sous l'eau) dépassait de la surface, surtout près des rives.

## 2. Règle (une seule, parcours compilés et monde ouvert)

`compiler/src/openride_compiler/water_terrain.py` :

- **Niveau** (`lake_level`) : médiane du MNT **brut** (pas le relief fondu avec la route) sur une grille de 30 m alignée sur le repère, aux points du plan d'eau à plus de 30 m de toute rive (îles comprises). Le MNT Copernicus aplatit les lacs : tous les morceaux d'un même lac trouvent la même valeur. Plafond : quart le plus bas des altitudes de la rive (pas de 10 m), pour ne jamais poser l'eau au-dessus de la berge ; un exutoire seul ne compte plus. Plan d'eau trop étroit pour un point loin de la rive : tous les points dedans ; aucun point dedans (étang de quelques mètres) : minimum de la rive, comme avant (lot I4).
- **Sol** (`sink_grid`) : chaque échantillon du relief dans le plan d'eau (hors îles) descend à `level_y − 1 m` au plus (`WATER_SINK_M`) ; jamais remonté. La chaussée est gardée : moins de `BLEND_INNER_M` (4 m) du bord d'une route, hors ponts (les ponts ne sont pas dans l'axe des routes du carré) ; une route sur digue garde donc sa digue, une route sur pont passe au-dessus de l'eau.
- La décision ne dépend que des coordonnées de l'échantillon et du polygone : deux tuiles voisines abaissent leur bord commun à l'identique.
- **La mer n'est pas concernée** : niveau 0, MNT déjà à 0, surface posée 0,2 m au-dessus par U9 (images validées le 13 novembre). Elle pourra suivre la même règle de sol si les captures le demandent.

## 3. Branchements

- **Parcours compilés** : `osm_layers.water_level_y` (remplace `compute_contour_min_y` pour les aires) ; `cli.py` abaisse les niveaux proche et lointain (`sink_route_tiles`, pas l'horizon) dans `build` avec la couche eau, dans `add-layer terrain` (d'après la couche eau déjà là) et dans `add-layer water` (terrain relu, abaissé, réécrit). `add-layer water` donne le même terrain que `build` avec l'eau.
- **Monde ouvert** : `squares.square_water` (aires à moins de 1 km du carré, niveau calculé une fois) sert au sol (`square_terrain`) et à la couche eau (`square_layers`, aire du carré qui contient son centre) ; `WORLDGEN_VERSION` passe à 2 : les carrés du cache sont refaits à la séance suivante.
- Format `.world` inchangé (ligne au journal du contrat, §8).

## 4. Hors périmètre (lots suivants de la série EA)

- EA2 : eau au loin en monde ouvert (lacs dessinés sur les tuiles lointaines, sol lointain abaissé).
- EA3 : grandes rivières en surface (`water=river`, classe `river` des tuiles vectorielles).
- EA4 : ponts dessinés (tablier, garde-corps).

## 5. Tests

`compiler/tests/test_water_terrain.py` : point dans un polygone à île ; lac aplati coupé en deux morceaux (même niveau) ; exutoire qui ne tire plus le lac ; étang en pente plafonné à la rive basse ; petit étang (minimum de la rive) ; sol abaissé dedans seulement, jamais remonté, chaussée et île gardées, mer ignorée ; bord commun identique entre tuiles de parcours ; monde ouvert : deux morceaux d'un lac à cheval sur deux carrés, même niveau, sol abaissé, bord commun identique. `test_osm_poi_water.py` : `add-layer water` refait le même terrain que `build`, et rejouée ne change rien.

## 6. Recette sur le PC

- Suites `compiler` (pytest) et tests graphiques (`run_visual_tests.sh`) : le « Circuit des Prés » a un étang, ses références peuvent bouger un peu (niveau de l'étang).
- Monde ouvert au bord d'un lac : scénario `engine/tests/menu_scenarios/ea1_lac.json` (recherche « talloires », rive est du lac d'Annecy, 5 minutes, une capture par minute ; en-têtes `reseau` et `caches_reels` du banc des menus, repris du lot W17), `menu_bench.py --native --scenario ea1_lac --qualite low|medium|high --captures ecrans`, sur la branche puis sur `main` ; GPU (budgets 8, 13 et 16 ms) et temps par carré du générateur.
- Parcours compilé : Irohazaka du pack « Cols célèbres » (arrivée au lac Chūzenji, exutoire des chutes de Kegon) compilé avec `--layers route,terrain,biome,water`, `sim_bench.py --world <dossier> --at-m …` sur les derniers 600 m, low, medium et high, branche et `main`.
- Captures validées par le propriétaire avant fusion.
