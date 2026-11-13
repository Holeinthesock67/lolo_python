# Lot DB2 – Parcours de démonstration « Volcan en flammes »

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Boucle de démonstration de 8 km dans un volcan en éruption : paysage `volcan_actif` (lave, braises, fumées, gerbes, lueur) et parcours `demo-volcan` | GDScript, Python | DB1, O38, U25, P35 | Moyenne | En PR (13 novembre, version 6.0) |

Demande du propriétaire du 13 novembre 2026 à 22 h 29 : « un parcours démo exagéré feu et flammes dans un parcours volcanique ». Plan validé le même soir (carte, « plan complet ») : `/mnt/project-files/plans/PLAN_DEMO_VOLCAN_FLAMMES.md` hors dépôt. Précision à 22 h 31 : « un parcours en boucle si ça ne fait que 8 km ».

## 1. Objectif

Un parcours spectaculaire livré avec le jeu, sans réseau : on roule entre des coulées et des lacs de lave, dans les braises et la fumée, jusqu'à la crête d'un cratère qui crache des gerbes de lave, puis on redescend au départ. En boucle, pour les courses en tours.

## 2. Contraintes

- **Aucune donnée réelle** : trace, relief et décor inventés (origine fictive 45° N, 2° E, comme les autres démonstrations).
- **Pas d'exception** (principe du 27 octobre) : le feu n'est pas un réglage de la démo mais un **paysage** du thème, au même titre que les canyons ou les fjords (lot U25). N'importe quel parcours dont une tuile porte le paysage `volcan_actif` s'affiche de la même façon. Aucune zone réelle de la table des variantes régionales ne le pose : le Teide et l'Etna restent sobres.
- Pas d'heure imposée par la démo : le jeu reste à l'heure choisie par le joueur ; la lave brille de jour comme de nuit, la nuit encore plus.
- Aucune révision du contrat IPC (1.17 reste libre). Contrat des parcours : ajout compatible 1.9.
- Budgets GPU de #732 (low 8 ms, medium 13 ms, high 16 ms) : si un niveau dépasse, on réduit ce niveau.
- La lave ne touche jamais la route : bord de la lave et évents à au moins 14 m de l'axe, sur tout le parcours.

## 3. Conception

### 3.1 Contrat et thème

- `variant.landscape` (format des parcours §8 quater) : valeur `volcan_actif` ajoutée à l'énumération (révision 1.9, schémas `biome.schema.json` et `theme.schema.json`, `regional.LANDSCAPES`, `biome_ids.gd`).
- Thème §9 : membre facultatif `fire` d'un paysage, `{lava, lava_hot, crust, smoke, glow, density}`. Un paysage qui en a un est en feu. Le thème par défaut donne `landscapes.volcan_actif` : sol de scories noires et de basalte rougeoyant pour le biome `volcanic`, presque aucune plante, et le feu.
- `theme_loader.gd` (`_validate_fire`) et le schéma refusent une couleur invalide, une densité hors de 0 à 2 et une clé inconnue.

### 3.2 Engine : `volcano_fx.gd`

Nœud du décor vivant (`living_world.gd`, comme `ground_details.gd`) :

- **Coulées** : rubans de 14 à 34 m de large et de 70 à 100 m de long, à peu près parallèles à la route, à 14 m au moins de l'axe (jusqu'à 100 m) ; **mares** de 10 à 30 m de rayon jusqu'à 190 m de la route, **grands lacs** de 30 à 65 m de rayon jusqu'à 370 m (fond du cratère, plaine), en anneaux concentriques qui épousent le terrain ; **évents** jusqu'à 230 m. Densité du thème par défaut : 1,5 (« exagéré »). Placement déterministe par tronçon de 100 m (3 derrière, 14 devant la caméra), coupé là où il passerait trop près d'une autre portion de la route (épingles, boucles : `road_clearance.gd`). Les rubans épousent le terrain.
- **Lave** : un maillage par tronçon, shader `lava.gdshader` (croûte noire en plaques, fissures orange à jaunes qui pulsent, courant), émissif, posée 0,5 m au-dessus du terrain et rapprochée de la caméra de 1,5 % de sa distance (3 m au plus) pour ne jamais s'enfoncer entre les triangles du terrain.
- **Braises** autour du cycliste, **panaches** de fumée sur les évents les plus proches, **gerbes** de lave sur les grands lacs (rayon ≥ 14 m), **lumières** orange sur la lave la plus proche.
- **Lueur** : `fire_level` (0 à 1, montée en 2 s) rougit la brume de l'horizon, la lumière du soleil et l'horizon du ciel, assombrit de cendre le haut du ciel et les nuages (`atmosphere_view.gd`, `set_fire`).
- Règle unique dans `biome_model.gd` (`fire_of`, `fire_at`) : une tuile dont le paysage a un feu est en feu. `grass_tufts.gd` n'y pose aucune touffe d'herbe (rien ne pousse sur la lave).

Budgets (`quality_presets.gd`, `living`) :

| Qualité | Braises | Panaches | Gerbes | Lumières |
| --- | --- | --- | --- | --- |
| low | 80 | 1 | 0 | 0 |
| medium | 300 | 3 | 1 | 3 |
| high | 800 | 6 | 2 | 6 |

La lave au sol (shader seul) est à toutes les qualités. Décor vivant coupé : ni lave ni particules.

### 3.3 Parcours `demo-volcan`

`openride_compiler.demo_biomes` : la table `LOOPS` réunit les boucles de démonstration (« Circuit des Prés » du lot O38 et « Volcan en flammes »), chacune avec sa longueur, ses lobes, son relief, son décor et la variante de ses tuiles. `--volcan` écrit la boucle seule.

- 8 km, biome `volcanic`, variante `{basalte, —, volcan_actif}` sur toutes les tuiles.
- Profil : départ au plus bas dans la plaine de cendres, montée régulière de 220 m (9,6 % au plus) jusqu'à la crête du cratère à mi-boucle, descente par l'autre flanc. Loin de la route, un cône centré sur le cratère (620 m de la route à mi-boucle, à l'intérieur de la boucle), creusé de 150 m : parois raides sur 140 m, fond plat de 920 m de diamètre où la lave fait des lacs. La route tourne du même côté que la crête et la longe à moins de 90 m sur 1,2 km ; fondu sur 220 m entre le profil de la route et le cône.
- Décor OSM : « Hameau des Scories » au départ (maisons de basalte), « Belvédère des Coulées », refuge et « Cratère du Brasier » sur la crête.
- Jeu de base : installé par les contenus de départ, comme les autres démonstrations.

## 4. Tests

- `engine/tests/unit/test_volcano_fx.gd` : thème par défaut valide, `fire` invalide refusé, coulées, lacs et évents posés dans le paysage, aucun à moins de 14 m de l'axe sur une épingle (portion d'en face comprise), placement déterministe, maillage, lueur (et scène figée), rien hors du paysage ni sur `ile_volcanique`, budgets par qualité.
- `core/tests/test_biome_demo_world.py` : `test_volcan_loop` (boucle de 8 km, pente ≤ 10 %, 200 à 240 m de montée, sommet à mi-boucle, variante sur toutes les tuiles, cratère creusé, relief borné jusqu'à 40 km) ; jeu de base à trois parcours générés.
- `compiler/tests/test_contract_biome.py` : `volcan_actif` accepté par le contrat.
- Scénarios de menus `parcours_demo` et `contenus` : « Volcan en flammes » dans la liste et sur l'écran Prêt.

## 5. Recette sur le PC

1. Banc low, medium et high (GPU, budgets 8 / 13 / 16 ms) sur `demo-volcan`, et contacts des cyclistes du décor (0 attendu).
2. Captures : `python3 engine/tests/captures_demo.py lancer --parcours demo-volcan --qualites low,medium,high` (début, quarts du tour dont la crête du cratère).
3. Planche validée par le propriétaire avant fusion.

## Livraison

- 13 novembre : PR ouverte (partie de la branche de #866, DB1). Reste : recette PC et validation des captures.
