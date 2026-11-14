# Lot DJ1 – Parcours de démonstration Japon « Route des Érables »

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Parcours de démonstration du biome Japon livré avec le jeu, en plus de Hakone et du Fuji du pack Cols célèbres | Python | DB1, JP1–JP8, O37 | Petite | En PR (13 novembre, version 6.0, après DB1, avant NT1 et J9) |

Décision du propriétaire du 13 novembre 2026 à 22 h 26 (« Oui je veux un parcours demo en plus des cols ») : le jeu livre aussi une démonstration du Japon. Le plan de la série JP (lot JP8) disait « pas de monde démo Japon », puisque Hakone et le Fuji sont dans le pack ; le propriétaire a tranché le contraire.

## 1. Objectif

Un parcours court et lisible, livré avec le jeu sans réseau, qui montre le biome `japan` de la série JP : forêts de sugi, hinoki, momiji et bambous (JP5), maisons minka aux toits kawara (JP3), torii et lanternes (JP5), glissières blanches des virages (JP8), sol de roches volcaniques.

## 2. Contraintes

- **Aucune donnée réelle** : trace, relief et décor inventés, origine fictive au degré entier (45° N, 2° E, comme les autres démonstrations), aucun réseau, aucun FIT, GPX ni TCX réel.
- Pas d'exception (principe du 27 octobre) : une ligne de plus dans `DEMO_SET`, construite comme la « Montée alpine » (un biome, trois blocs de 2 km), installée par les contenus de départ comme les autres (une installation existante la reçoit à la prochaine installation des contenus, sans rien réécrire).
- Ni `main.gd`, ni révision du contrat IPC (1.17 reste libre).
- Le relief lointain reste borné comme pour DB1 (`test_far_relief_bounded`) : pas de grand volcan à l'horizon dans ce lot.

## 3. Réalisation

- `compiler/src/openride_compiler/demo_biomes.py` :
  - `DEMO_SET` : `("demo-japon", "Route des Érables", "japan", …, base=True)`, après le tour des nouveaux paysages.
  - Décor, pente et relief : ceux du bloc Japon du lot DB1 (`_japan`, `GRADE["japan"]`, `SIDES["japan"]`), répétés sur trois blocs : forêt sur les pentes, cultures, un village par bloc, un belvédère par bloc. 6,06 km, pente de 1 à 5 %, 201 m de montée, sommet à l'arrivée.
  - Noms inventés : villages « Village des Érables », « Hameau du Torii », « Village des Lanternes » ; belvédères « Belvédère des Cerisiers », « Belvédère du Lac », puis le sommet « Col des Cèdres ». « Fictif » en recette. Le bloc Japon du tour des nouveaux paysages garde ses noms (premier de chaque liste).
  - `BIOME_VARIANTS` et `biome_variants()` : un parcours d'un seul biome prend la variante régionale d'une vraie route de sa région ; pour `japan`, celle des zones `japon_*` de `data/regional_variants.toml` (sol `basalte`, toits `kawara`), vérifiée par le test contre `regional.variant_for`. Ligne de commande : `--biome japan`.
- `engine/tests/captures_demo.py` : `demo-japon` dans les parcours du jeu de base ; tout parcours en blocs de 2 km (et non plus seulement à plusieurs biomes) a ses captures à 150, 400 et 1 000 m de chaque bloc (les villages sont vers 1 000 m).
- `engine/tests/menu_scenarios/parcours_demo.json` et `contenus.json` : « Route des Érables » dans la liste et sur l'écran Prêt ; 4 parcours ajoutés au premier lancement.

## 4. Critères d'acceptation

1. `core/tests/test_biome_demo_world.py` (`test_japon_demo` et tests du jeu de base) : jeu de base = tour des nouveaux paysages, route des Érables, circuit ; 100 % `japan` ; variante basalte + kawara sur toutes les tuiles ; 6 km ± 2 %, pente 0,5 à 5,5 %, 150 à 260 m de montée, sommet à l'arrivée ; noms des villages et belvédères ; aucun « Fictif » ; relief lointain borné ; 0 contact des cyclistes du décor à 25, 40 et 50 km/h.
2. PC, par le fil de fusion (section 5) : banc low / medium / high dans les budgets GPU (8 / 13 / 16 ms), pire image < 100 ms ; **0 contact** sur la route.
3. **Planche de captures validée par le propriétaire avant fusion.**

## 5. Recette PC (≈ 1 h, sans le propriétaire)

Depuis `~/Games/lolo_python/Open_ride_linux`, branche du lot à jour.

```bash
cd ~/Games/lolo_python/Open_ride_linux
OUT=~/OpenRide/captures/dj1

# 1. Profil neuf : contenus de départ (4 parcours), liste des parcours (Col du lacet, Tour des nouveaux paysages, Route des Érables, Circuit des Prés)
python3 engine/tests/menu_bench.py --scenario contenus --scenario parcours_demo --captures ecrans --native --out $OUT/menus

# 2. Captures : 150, 400 et 1 000 m de chaque bloc, approche du sommet, en low, medium et high (≈ 15 min par qualité)
python3 engine/tests/captures_demo.py lancer --out $OUT --qualites low,medium,high --parcours demo-japon --native --sans-menus

# 3. Banc perf au milieu de chaque bloc (1 000, 3 000, 5 000 m), scénario nominal, sonde GPU
for q in low medium high; do
  python3 engine/tests/sim_bench.py --scenario nominal --world $OUT/routes/demo-japon.world \
    --quality $q --native --probe --speed-kmh 50 --duration 650 \
    --at-m 1000,3000,5000 --out ~/OpenRide/sim_bench/dj1_$q
done
```

À relever par qualité : GPU moyen et p99 par bloc (budgets **8 / 13 / 16 ms**), pire image (< 100 ms) ; contacts des cyclistes du décor sur la route : 0 attendu. Repère : le bloc Japon du tour des nouveaux paysages et Hakone (r855 : 5,37 / 8,61 / 10,39 ms). La planche `$OUT/planche.html` et les captures de menus vont au propriétaire.

## 6. Livraison

PR du 13 novembre (branche `claude/project-thread-lruwjz`), **partie de la branche de DB1 (#866)** dont elle reprend le décor et le relief Japon : à fusionner après #866, base remise sur `main` une fois #866 fusionnée. Reste : recette PC (section 5), validation de la planche par le propriétaire, puis go de fusion.
