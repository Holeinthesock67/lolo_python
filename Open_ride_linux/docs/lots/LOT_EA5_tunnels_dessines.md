# Lot EA5 – Tunnels dessinés : colline gardée, tube, portails et lampes

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Tunnels dessinés (colline gardée au-dessus, terrain non dessiné dans le tube, piédroits, voûte, portails, murs d'approche, lampes), parcours compilés et monde ouvert | Python, GDScript, shader | EA4, #936 (garde-fou de la chaussée) | Moyenne | En revue (PR à valider : essai PC, mesures low, medium, high et captures) |

## 1. Objectif

Choix du propriétaire du 20 novembre (fil du garde-fou de la chaussée, #936) : « garder la colline » au-dessus des vrais tunnels, pas de tranchée (à Sevrier, un tunnel passe sous 39 m de colline) ; dessiner les tunnels dans un lot à part, lancé le même jour (« Démarre tout de suite sauf installateur »). Avant ce lot, l'engine ne dessinait aucun tunnel : la route traversait la colline, on voyait le ciel à l'intérieur (terrain à une face) et, à l'entrée, la pente de la colline recouvrait la route sur 10 à 20 m. Les parcours compilés taillaient au contraire une tranchée au-dessus de la route (garde-fou `terrain.clear_road` sur toute la route).

Étude : `/mnt/project-files/plans/ea5/ETUDE_EA5_TUNNELS.md` (dossier partagé du projet). Retoucher le relief seul ne suffit pas : la grille de 10 m fait toujours une rampe d'herbe en travers de l'entrée entre un sommet abaissé et un sommet gardé.

## 2. Règle (une seule, parcours compilés et monde ouvert, `compiler/src/openride_compiler/tunnels.py`)

- **Portions en tunnel.** Monde ouvert : les `spans` « tunnel » des arêtes (lot W4). Parcours compilé : les points accrochés à une voie OSM `tunnel=*` (hors `no`) par la règle des ponts (`surface.match_ways`, `bridges.spans_from_flags`).
- **Profil.** Ligne droite d'un portail à l'autre (étape 3 du profil d'arête ; `bridges.apply_bridge_profile` sur les portions en pont et en tunnel réunies d'un parcours compilé).
- **Terrain.** Colline gardée : ni fondu ni garde-fou de la chaussée sur une portion en tunnel (`terrain.build_terrain(…, tunnels=…)`, `terrain.open_pieces` ; monde ouvert : `axis_pieces` sans les spans, #936). Sans la couche, la règle d'avant reste.
- **Trou du terrain.** Le shader du terrain (`terrain.gdshader`, `terrain_biomes.gdshader`) ne dessine pas ce qui est dans le volume du tube et de l'approche des portails (`engine/shaders/tunnel_cut.gdshaderinc`) : piédroits jusqu'à 4,3 m, voûte en demi-ellipse de 2 m (bornée au milieu de la coque : le bord du trou reste caché dans le béton), de 0,5 m sous la chaussée. Registre `engine/scripts/tunnel_cut.gd` : les 64 tronçons les plus proches de la caméra, texture globale `tunnel_cut_data`, nombre `tunnel_cut_count`, boîte `tunnel_cut_box` (test rapide), réécrits quand le registre change ou que la caméra a bougé de 4 m. Le trou n'est compilé que dans la variante `TUNNEL_CUT` des deux shaders (`TunnelCut.shader_for`), donnée par `world_streamer.gd` aux seules tuiles proches qui touchent un tunnel enregistré (`TunnelCut.touches`, revu à chaque changement du registre, sans refaire les maillages) : un `discard` fait exécuter tout le fragment dans les passes de profondeur et d'ombre, et alourdissait tout le terrain même loin des tunnels (CI du 25 novembre : gel de 9 à 21 s au chargement du tour « flancs », tour sans tunnel).
- **Objet dessiné** (`engine/scripts/tunnel_mesh.gd`) : trottoirs de 1 m, piédroits verticaux, voûte, coque de 0,6 m (là où la colline est plus basse que la voûte, le tube sort du sol comme une tranchée couverte), tête de portail à chaque bout (3 m au-delà de la coque, 1,5 m au-dessus, 0,8 m d'épaisseur), murs d'approche sur 10 m devant chaque portail (de la clé de voûte à 1 m), lampes sur deux rangées sous la naissance de la voûte tous les 12 m (matériau non éclairé, pas de vraies lumières : budget GPU). Ombre portée du tube (intérieur dans l'ombre dans la distance des ombres).

## 3. Branchements

- **Format** 1.11 (ajout compatible, `docs/contracts/world_format_v1.md` §8 octies, schéma `tunnels.schema.json`, entrée `layers.tunnels`).
- **Compilateur** : couche `tunnels` de `--layers` (couche OSM, même requête des voies que les ponts et la surface) ; `add-layer tunnels` (et `add-layer bridges`) refait route, fiche et terrain en gardant les portions de l'autre couche ; `add-layer terrain` et `add-layer water` relisent les deux ; `verify` contrôle la couche (axe sur la route, compte).
- **Monde ouvert** : `squares.square_tunnels`, `tunnels.json` du carré, lié en `tunnels/tile_<ix>_<iz>.json` dans la séance ; `WORLDGEN_VERSION` 10 (carrés du cache refaits à la séance suivante).
- **Engine** : `osm_layers.gd` lit et valide la couche ; `osm_streamer.gd` en fait deux nœuds par tronçon (`osm_tunnels_<k>`, `osm_tunnel_lamps_<k>`, étape `osm_tunnels` des mesures de tâches), relief exagéré appliqué, et enregistre la découpe du tronçon.

## 4. Hors périmètre

- Éclairage réel de l'intérieur (lumières ponctuelles) et assombrissement des personnages dans le tunnel hors de la distance des ombres : à juger sur les captures.
- Styles de portail par biome ou par pays : un seul modèle en béton.
- Tunnels des routes non suivies en monde ouvert : dessinés (et le terrain y est découpé).

## 5. Tests

`compiler/tests/test_tunnels.py` : balise, réunion des portions, axe du tube, `build` sous une colline de 40 m (portion trouvée, tunnel perpendiculaire ignoré, profil droit, colline gardée, chaussée dégagée à ciel ouvert, `verify` et schémas), sans la couche le garde-fou d'avant, ponts et tunnels ensemble, `add-layer tunnels` identique à `build` et `add-layer terrain` qui garde la colline ; monde ouvert : tunnel dans le carré de son milieu, colline gardée, `WORLDGEN_VERSION` 10. `engine/tests/unit/test_tunnel_mesh.gd` : gabarit de la route libre, clé de voûte, portails et approches aux deux bouts, normales et sens des faces, lampes, volume de découpe, registre (tronçons les plus proches, boîte, mise à jour), lecture de la couche, coordonnées du monde vivant, triangles par mètre. `engine/tests/render/test_tunnel_render.gd` (Forward+) : entrée du tunnel ouverte, flanc et colline gardés, sans tunnel enregistré le flanc ferme l'entrée.

## 6. Recette sur le PC

- Suites `compiler`, `run_engine_tests.sh` et tests graphiques.
- Monde ouvert : scénario `ea5_tunnel` du banc des menus (départ de Sevrier, cache séparé), low, medium et high, branche et `main` : GPU (budgets 8, 13 et 16 ms), temps par carré du générateur (carrés refaits : `WORLDGEN_VERSION` 10), captures de l'approche, de l'intérieur et de la sortie.
- **Captures sûres d'un tunnel (22/11)** : la balade de Sevrier ne passe pas forcément le tunnel (le premier carrefour décide ; banc du 22/11 sans tunnel). Monde d'essai sans réseau `engine/tests/make_tunnel_world.py` (tunnel de 300 m sous une crête de 45 m, km 1,35 à 1,65, parcours compilé, aucun cache du monde ouvert) : `sim_bench.py --world tunnel --at-m 1150,1320,1500,1630 --quality low|medium|high`, plus `--camera follow_far --at-m 1800` pour la crête gardée au-dessus de la sortie. Test `compiler/tests/test_make_tunnel_world.py`.
- Parcours compilé réel avec un tunnel (facultatif) : `add-layer <nom>.world tunnels`, `sim_bench.py --world <dossier> --at-m <portail − 300>`.
- Captures validées par le propriétaire avant fusion.

## 7. Livraison

- PR #940 : couche `tunnels` (format 1.11), `WORLDGEN_VERSION` 10 après la règle sol / route, `tunnel_mesh.gd`, trou du terrain `tunnel_cut.gd` en variante `TUNNEL_CUT` des seules tuiles qui touchent un tunnel (25 novembre). Reste : banc PC `ea5_tunnel` (low, medium, high) et captures validées.
