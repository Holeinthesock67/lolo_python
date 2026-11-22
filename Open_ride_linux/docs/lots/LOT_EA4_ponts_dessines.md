# Lot EA4 – Ponts dessinés : tablier, garde-corps et piles

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Ponts dessinés (tablier, garde-corps, piles sous un grand pont), profil en ligne droite et terrain non fondu sous le pont, parcours compilés et monde ouvert | Python, GDScript | EA1, W4, W7, U20 (livrés ou en revue) | Moyenne | **Livré le 20 novembre** (PR #916) |

## 1. Objectif

Demande du propriétaire du 14 novembre (série EA, `docs/6.0/PLAN_SERIE_EA.md`), lancée le 16 novembre (« Lance les lots ea »). Avant ce lot, un pont n'était qu'une route droite d'une culée à l'autre (monde ouvert) ou une route qui suivait le MNT au fond de la vallée (parcours compilés) : rien n'était dessiné, le terrain était fondu avec la route sous le pont (remblai ou route posée au fond du ravin).

## 2. Règle (une seule, parcours compilés et monde ouvert, `compiler/src/openride_compiler/bridges.py`)

- **Portions en pont.** Monde ouvert : les `spans` « bridge » des arêtes (lot W4, balise `bridge` d'OSM ou `brunnel=bridge` des tuiles vectorielles). Parcours compilé : les points de la route accrochés à une voie OSM `bridge=*` (hors `no`) par la règle d'accrochage de la surface (lot U20, `surface.match_ways`, désormais commune aux deux usages : voie à moins de 15 m, cap à moins de 30°, première voie gardée à égalité de distance) ; portion `[s − 5 m, s + 5 m]` des bouts d'une suite de points en pont, portions à moins de 20 m rejointes, moins de 8 m ignorées.
- **Profil.** Route en ligne droite (en altitude) sur la portion prolongée de 10 m de chaque côté, bouts ramenés aux points du profil, posée sur l'altitude brute `alt_raw_m` puis lissée, pente recalculée : ce sont les étapes 3 et 4 du profil d'arête du monde ouvert (`edge_profile`), appliquées au parcours compilé (la règle rejouée ne change rien ; sans `alt_raw_m`, sur l'altitude lissée). Premier rendu : posée après le lissage, la vallée tirait encore les abords du pont (bosse de 8 % avant la culée).
- **Terrain.** Pas de fondu de la route sous un pont (`terrain.PiecesAxis`, même règle que `squares.axis_pieces`) ; sous un lac (EA1), le sol abaissé ne garde pas la chaussée sous un pont.
- **Objet dessiné.** Axe du tablier aux points du profil (y = chaussée), demi-chaussée, piles d'un pont de 30 m et plus, également espacées d'au plus 30 m, là où le tablier est à 4 m au moins du sol, pied enterré de 1,5 m.

## 3. Branchements

- **Format** 1.9 (ajout compatible, `docs/contracts/world_format_v1.md` §8 septies, schéma `bridges.schema.json`, entrée `layers.bridges`).
- **Compilateur** : couche `bridges` de `--layers` (couche OSM) ; dans `build`, les voies du couloir sont lues avant le terrain (même requête ensuite pour la surface), le profil est redressé avant la fiche, les segments et le terrain ; `add-layer bridges` refait route, fiche, terrain (sol sous l'eau compris) et couche, comme `build` ; `add-layer terrain` et `add-layer water` relisent les portions du manifeste ; `verify` contrôle la couche (axe sur la route, piles, compte).
- **Monde ouvert** : `squares.square_bridges`, fichier `bridges.json` du carré, lié en `bridges/tile_<ix>_<iz>.json` dans la séance ; `WORLDGEN_VERSION` 3 (carrés du cache refaits à la séance suivante).
- **Engine** : `bridge_mesh.gd` (tablier de 1 m d'épaisseur, dessus 12 cm sous la chaussée, rives à 0,9 m au-delà de la demi-chaussée, garde-corps ajouré : bordure en béton de 30 cm, main courante métallique à 1 m et montants tous les 2,5 m, pour voir la vallée depuis la selle (un premier muret plein de 1 m la cachait), bouts fermés, piles en caisson de 1,2 × 4 m, normales plates, couleur par sommet, un matériau, ombre portée) ; `osm_layers.gd` lit et valide la couche ; `osm_streamer.gd` en fait un septième nœud par tronçon (`osm_bridges_<k>`, étape `osm_ponts` des mesures de tâches), relief exagéré appliqué.

## 4. Hors périmètre

- Tunnels (toujours tracés comme du terrain ordinaire) ; talus du ruban de route (lot du 4 novembre) gardé sur le pont, caché par le tablier.
- Ponts des routes non suivies en monde ouvert : dessinés (leur route ne l'est pas) ; à juger sur les captures.
- Styles de pont par biome ou par type (`bridge:structure`) : un seul modèle en béton.

## 5. Tests

`compiler/tests/test_bridges.py` : portions (marge, jonction, longueur minimale), profil en ligne droite, piles seulement sur un pont long et haut, `build` sur une vallée de 30 m (portion trouvée, pont perpendiculaire ignoré, profil droit, vallée gardée sous le pont, une pile au fond, `verify` et schémas), sans la couche rien ne change, `add-layer bridges` identique à `build` et rejouable ; monde ouvert : gorge de 40 m, pont dans le carré de son milieu, tablier à plat, gorge non comblée. `engine/tests/unit/test_bridge_mesh.gd` : rien au-dessus de la chaussée, garde-corps des deux côtés, pieds des piles, normales et sens des faces, pile ignorée près du sol, pont en courbe, lecture et validation de la couche, coordonnées du monde vivant, relief exagéré, triangles par pont.

## 6. Recette sur le PC

- Suites `compiler`, `run_engine_tests.sh` et tests graphiques.
- Parcours compilé avec ponts : un parcours du PC qui passe un pont, recompilé avec `--layers route,terrain,biome,water,bridges` (ou `add-layer <nom>.world bridges`), `sim_bench.py --world <dossier> --at-m <début du pont − 300>` en low, medium et high, branche et `main` : GPU (budgets 8, 13 et 16 ms), captures du pont vu de la route et de la vallée.
- Monde ouvert : départ près d'un grand pont (banc des menus, scénario `ea4_pont`), low, medium et high, temps par carré du générateur (carrés refaits : `WORLDGEN_VERSION` 3).
- Captures validées par le propriétaire avant fusion.

## 7. Livraison

Fusionné le 20 novembre 2026 (PR #916 : ponts dessinés (tablier, garde-corps, piles)). Détail des écarts et de la recette : description de la PR.
