# Lot O38 – Circuit de démonstration en boucle

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Circuit en boucle livré avec le jeu (« Circuit des Prés », 3 km), pour les courses en tours et le Grand Prix des objets | Python | O37, GP2 | Petite | En PR (12 novembre, version 5.0, avant J9) |

Demande du propriétaire du 12 novembre 2026 (« Ok circuit demo grand prix »), à la suite du constat de la recette GP11 : le jeu de base ne livre aucun parcours en boucle, si bien que l'étape « circuit » de `docs/RECETTE_SERIE_GP.md` dépend d'une trace personnelle.

## 1. Objectif

Un parcours en boucle dans les contenus de départ, utilisable sans trace du joueur : course en tours du Grand Prix des objets (« tour 1 / N », rangées de boîtes aux mêmes endroits d'un tour à l'autre) et toute course en tours.

## 2. Contraintes

- **Aucune donnée réelle** (règle de confidentialité du 24 octobre) : trace, relief et décor synthétiques, origine fictive au degré entier (45° N, 2° E, comme les autres démonstrations), aucun FIT, GPX ou TCX réel, aucun réseau.
- Pas d'exception : le circuit est un parcours de plus du générateur des démonstrations (`DEMO_SET`), installé comme les autres par les contenus de départ.
- Ni `main.gd`, ni révision du contrat IPC : le mode Grand Prix gère déjà les boucles (`session._grandprix_course`).

## 3. Réalisation

- `compiler/src/openride_compiler/fake_osm.py` : deux formes de route de même interface (`xz`, `heading`, `point`, `locate`, `s_of`) : `SRoad`, les deux grands S vers le nord des parcours ouverts (inchangés), et `LoopRoad`, une boucle fermée étoilée (rayon modulé par des lobes, abscisse curviligne exacte, point le plus proche par arbre k-d). Tout le décor fabriqué (`Overpass.rect_along`, `band`, `point`) passe par la route au lieu de supposer la route en S.
- `compiler/src/openride_compiler/demo_biomes.py` : `--circuit` et l'entrée `demo-circuit` de `DEMO_SET`, nom au menu **« Circuit des Prés »**. Boucle de 3 000 m parcourue dans le sens horaire (intérieur à droite), un seul biome (prairie tempérée), départ au « Hameau des Prés ». Relief analytique `circuit_relief` sous la route et autour : la boucle revient forcément à son altitude de départ ; pente de −5 à +5 %, 37 m de montée par tour ; une courbe en S serrée (rayon d'environ 50 m) au troisième quart. Décor : hameau et église au départ, prés avec bétail, cultures et bois à l'extérieur, verger, broussailles, pré et étang à l'intérieur (bandes de 120 m au plus : l'autre rive est à plus de 450 m), deux fermes, deux éoliennes. Le compilateur reconnaît la boucle (fin sur le départ, `type` `loop`).
- Contenus de départ (`contents.py`) : le circuit s'ajoute aux parcours manquants à la prochaine installation des contenus de départ, comme tout parcours de `GAME_DEMOS` ; rien d'autre n'est réécrit. Le détail du menu dit « N parcours de démonstration ».
- `engine/tests/captures_demo.py` : le circuit fait partie des parcours capturés ; un circuit a en plus des captures aux quarts du tour.

## 4. Critères d'acceptation

1. Installation neuve : « Circuit des Prés » au menu des parcours, marqué circuit.
2. `test_biome_demo_world.py` : boucle fermée reconnue par le compilateur et par le core (`is_loop`), longueur 3 km à 5 m près, pente dans ±6 %, montée de 30 à 50 m par tour, virage le plus serré d'au moins 40 m, autre rive à plus de 400 m ; course du Grand Prix des objets en 2 tours sur le parcours livré, mêmes rangées de boîtes à chaque tour.
3. PC du propriétaire, séquencé par le fil de fusion : captures du circuit en `low`, `medium` et `high` (`captures_demo.py --parcours demo-circuit`) et banc `grand_prix` sur le circuit dans les trois préréglages, budgets GPU tenus (8 / 13 / 16 ms) ; **captures validées par le propriétaire avant fusion**.
4. Recette GP11, étape 3 : se fait sur « Circuit des Prés » (mise à jour de `docs/RECETTE_SERIE_GP.md` quand la PR GP11 est fusionnée).

## 5. Essais sur le PC

```bash
cd ~/Games/lolo_python/Open_ride_linux
python3 engine/tests/captures_demo.py lancer --out ~/OpenRide/captures/o38 --qualites low,medium,high --parcours demo-circuit --native
for q in low medium high; do
  python3 engine/tests/sim_bench.py --scenario grand_prix --world ~/OpenRide/captures/o38/routes/demo-circuit.world \
    --quality $q --native --probe --out ~/OpenRide/sim_bench/o38_$q
done
```
