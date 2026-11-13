# Lot DB1 – Parcours de démonstration « Tour des nouveaux paysages »

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Parcours de démonstration des biomes et paysages de la 6.0, qui remplace au jeu de base le tour des six paysages, la route de la côte et la montée alpine | Python | O37, O38, AT1, JP1, HP1, U25 | Petite | En PR (13 novembre, version 6.0, avant PK1, NT1 et J9) |

Décision du propriétaire du 12 novembre 2026 à 21 h 51 (« on mettra col du lacet et un parcours avec nouveaux biomes », confirmée par carte) : le jeu final livre le Col du lacet et **un parcours qui montre les nouveaux biomes**. Il remplace le « Tour des six paysages », la « Route de la côte » et la « Montée alpine », gardés pour les bancs (`--recette`). Le vélodrome et le « Circuit des Prés » restent (modes Vélodrome et Grand Prix). Voir le bilan des parcours de démonstration du 12 novembre.

## 1. Objectif

Un parcours livré avec le jeu, sans réseau, qui fait traverser au joueur les biomes et les paysages ajoutés en 6.0 : Atlantique et landes (`atlantic_heath`, AT1), Japon (`japan`, JP1), hauts plateaux (`high_plateau`, HP1) et les quatre paysages du lot U25 (canyon, fjord, île volcanique, rizières).

## 2. Contraintes

- **Aucune donnée réelle** (règle du 24 octobre) : trace, relief et décor inventés, origine fictive au degré entier (45° N, 2° E, comme les autres démonstrations), aucun réseau, aucun FIT ni GPX réel.
- Pas d'exception (principe du 27 octobre) : un parcours de plus du générateur des démonstrations (`DEMO_SET`), installé comme les autres par les contenus de départ.
- Ni `main.gd`, ni révision du contrat IPC (1.17 reste libre).
- Les anciennes démonstrations installées chez un joueur ne sont jamais enlevées (seules celles d'avant le lot O37 le sont, comme avant).

## 3. Réalisation

- `compiler/src/openride_compiler/demo_biomes.py` :
  - `PAYSAGES` : sept blocs de 2 km, chacun `(biome, paysage, sol, toits)` : fjord sur `coast` (schiste sombre, bois peint, **mer** le long du bloc), landes sur `atlantic_heath` (granit, ardoise), rizières sur `farmland` (latérite), Japon sur `japan` (toits `kawara`), île volcanique sur `volcanic` (basalte), canyon sur `rock_desert` (grès rose), hauts plateaux sur `high_plateau`. 14,15 km, 285 m de montée, pente de −2,5 à +6,5 %, sommet à l'arrivée (« Col des Lamas »).
  - Variante régionale **par bloc** : `Plan.variants`, `tile_variant` pose dans chaque tuile de la couche biome la variante du bloc qui couvre le plus de ses points ; les tuiles proches de 1 km tombent chacune dans un seul bloc. L'ordre des blocs est choisi pour que deux blocs voisins ne partagent aucun biome de base de leurs paysages (section `landscapes` du thème) : la transition de 300 m d'un bloc ne prend jamais le paysage du voisin (vérifié par le test).
  - Décor par paysage ou par biome (`Plan.decor`, `BLOCKS`) : village de bois peint et bois au bord du fjord, landes de bruyère et hameau de granit, cultures et village des rizières, forêt et village japonais, prairies et maisons blanches du volcan, broussailles et ranch du canyon, herbes rases et maisons de terre du plateau ; noms de lieux inventés (`PLACE_NAMES`), « Fictif » en recette.
  - `DEMO_SET` : `demo-biomes-paysages` (« Tour des nouveaux paysages ») au jeu de base ; `demo-biomes-tour`, `-cote` et `-alpin` passent `base=False` (recette seule, comme le tour gravel). Ligne de commande `--paysages`.
  - `generate` refuse un bloc sans décor (message « biome sans décor de démonstration »).
- Contenus de départ : rien à changer dans `contents.py` ; le jeu neuf installe le tour des nouveaux paysages et le circuit, une installation existante garde ses anciennes démonstrations (les démonstrations sorties du jeu de base ne sont enlevées que si elles datent d'avant le lot O37).
- `engine/tests/captures_demo.py` : parcours du jeu de base (`demo`, `demo-biomes-paysages`, `demo-circuit`) ; un tour à plusieurs biomes a des captures à 150, 400 et 1 000 m de chaque bloc.
- `engine/tests/menu_scenarios/parcours_demo.json` et `contenus.json` : liste du jeu de base, anciens noms absents.
- `engine/tests/run_engine_tests.sh` : le contrôle « rien du paysage sur la chaussée » prend aussi le nouveau tour (même motif `demo-biomes-*`).

## 3 bis. Correctifs après le banc r866 (13 novembre)

Le banc r866 (tête 553119a3) : GPU 5,51 / 8,85 / 10,91 ms (dans les budgets), menus bons, mais deux défauts.

- **Ciel zébré de grandes bandes grises en éventail.** Le relief synthétique (`make_terrain`) ajoutait `far_slope × (d − 162 m)` sans borne : à 5 km (tuiles lointaines) 5,8 km d'altitude, à 40 km (horizon du lot JP4) 27,6 km, vus comme des murs dans le ciel. La pente lointaine s'adoucit désormais jusqu'à un palier (`_soft_cap`, `FAR_RISE_M` = 800 m : 360 m en montagne, 440 m pour les parois du canyon) ; même borne pour la pente est-ouest du circuit au-delà de 900 m (`circuit_relief`), la route et ses abords proches ne changent pas. Après : au plus 940 m sur tous les niveaux, horizon compris (le −361 m de l'horizon est la courbure terrestre du lot JP4, voulue). Test `test_far_relief_bounded`.
- **Milliers de contacts entre cyclistes du décor** (2 558 / 2 971 / 4 143 au banc, surtout core/core). Reproduits dans le core (`RoadCyclists` sur le tour : 1 436 core/core, 18 core/cycliste) ; trois causes, corrigées à l'identique dans `road_cyclists.py` et `road_cyclists_model.gd` (relevé de parité régénéré) :
  1. un groupe ralentissait pour celui qui le suivait (`slowest` prenait aussi ceux de derrière) : `limit` ne prend que ceux de devant ;
  2. le suiveur se réglait sur la vitesse annoncée du premier et non sur son allure réelle (gêné lui-même dans une montée) : `pace()` / `_pace()`, vitesse du dernier pas ;
  3. un `overtake` rabattu puis gêné devant le cycliste repassait à gauche en traversant sa ligne juste devant lui : il ne passe à gauche qu'avec la place de finir son écart (`FILE_GAP_M + (v − v_cycliste) × CROSS_S`, 3 s), sinon il se laisse distancer ; à hauteur ou devant, il reste à droite et se laisse doubler.
  Après : 0 contact core/core et core/cycliste sur toutes les démonstrations (jeu de base et recette) à 25, 40 et 50 km/h. Test `test_decor_cyclists_never_touch` (il échoue sur l'ancien modèle).

Banc r866b (tête db9f2b4e) : ciel propre, GPU 5,21 / 8,31 / 10,44 ms, mais encore 96 / 191 / 108 contacts au banc (104 / 138 / 351 aux captures), à 2,2–2,5 m de l'axe. Cause : la liste `riders` du contrat donne au plus 6 cyclistes (`maxItems`) ; sur le tour, plus de 6 sont à moins de 60 m environ 5 % du temps (montées à 50 km/h, groupes rattrapés). Liste pleine, l'engine gardait **toutes** ses copies des cyclistes absents de la liste, à des places périmées, y compris tout près, et les faisait rouler au travers de ceux du core. Correctif engine (`sync_core`, `_still_on_road`) : liste pleine, un cycliste absent de la liste est forcément plus loin que le plus loin de la liste ; une copie plus près (marge `FILE_GAP_M`) quitte la route, celles d'au-delà roulent comme avant. Imitation Python de `sync_core` sur le tour à 50 km/h : 274 contacts à moins de 55 m avant, 0 après (25, 35 et 50 km/h, tour et tour des six paysages). Test de l'engine `test_road_cyclists_core.gd` mis à jour. Contrat inchangé (la révision 1.17 reste libre).

## 4. Critères d'acceptation

1. `core/tests/test_biome_demo_world.py` : jeu de base = tour des nouveaux paysages + circuit ; recette = en plus tour, gravel, côte, alpin ; parts des sept biomes égales (14,3 % ± 0,6) ; variante de chaque tuile proche = celle de son bloc ; les quatre paysages présents ; aucun paysage sur le biome d'un bloc voisin ; mer le long du fjord ; sommet au dernier bloc, 200 m de montée au moins ; aucun « Fictif » ; anciennes démonstrations O37 laissées telles quelles chez le joueur.
2. PC, par le fil de fusion (section 5) : banc low / medium / high dans les budgets GPU (8 / 13 / 16 ms), pire image < 100 ms ; aucun contact sur la route.
3. **Planche de captures validée par le propriétaire avant fusion.**

## 5. Recette PC (≈ 1 h 30, sans le propriétaire)

Depuis `~/Games/lolo_python/Open_ride_linux`, branche du lot à jour.

```bash
cd ~/Games/lolo_python/Open_ride_linux
OUT=~/OpenRide/captures/db1

# 1. Profil neuf : contenus de départ, liste des parcours (Col du lacet, Tour des nouveaux paysages, Circuit des Prés)
python3 engine/tests/menu_bench.py --scenario contenus --scenario parcours_demo --captures ecrans --native --out $OUT/menus

# 2. Captures : une image à 150, 400 et 1 000 m de chaque bloc, approche du sommet, en low, medium et high (≈ 50 min par qualité)
python3 engine/tests/captures_demo.py lancer --out $OUT --qualites low,medium,high --parcours demo-biomes-paysages --native --sans-menus

# 3. Banc perf au milieu de chaque bloc (1 000, 3 000 … 13 000 m), scénario nominal, sonde GPU
for q in low medium high; do
  python3 engine/tests/sim_bench.py --scenario nominal --world $OUT/routes/demo-biomes-paysages.world \
    --quality $q --native --probe --speed-kmh 50 --duration 1150 \
    --at-m 1000,3000,5000,7000,9000,11000,13000 --out ~/OpenRide/sim_bench/db1_$q
done
```

À relever par qualité : GPU moyen et p99 par bloc (budgets **8 / 13 / 16 ms**), pire image (< 100 ms), le bloc le plus lourd ; contacts des cyclistes du décor sur la route : 0 attendu (comme `rAS7b`). La planche `$OUT/planche.html` et les captures de menus vont au propriétaire.

## 6. Livraison

PR du 13 novembre (branche `claude/project-thread-aj6qj0`), main remise après #849 et #865. Banc r866 rejoué après les correctifs de la section 3 bis. Reste : recette PC (section 5), validation de la planche par le propriétaire, puis go de fusion.
