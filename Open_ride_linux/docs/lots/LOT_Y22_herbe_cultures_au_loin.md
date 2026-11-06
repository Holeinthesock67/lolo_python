# Lot Y22 – Herbe et cultures allégées au loin

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série Y (rendu) : niveau de détail de l'herbe du bord de route selon la distance (gerbe simplifiée au-delà de 40 m, un MultiMesh par tronçon écarté hors du champ, fondu fini à 120 m au lieu de 150) et des rangs de vigne des cultures (modèle lointain au-delà de 200 m, en haie d'un rang), prés plus ou moins mûrs peints sur le sol en plaques de 90 à 250 m | GDScript + shader | Y11, U7, P5 | Petite | **En PR** (lancé le 5 novembre) ; banc PC en low, medium et high et captures avant/après à valider |

## 1. Objectif

Le biome cultures (farmland) dépasse le budget GPU d'environ 4 ms en medium et en high même avec le MSAA 2× ; en low il est à 7,9 ms pour 6 (recette U18 du 5 novembre, `/mnt/project-files/mesures/2026-11-06-optim/`). L'étude `docs/ETUDE_OPTIMISATION_RENDU_2026-11-05.md` (§3.2, §4 point 6) a mesuré que la moitié des touffes d'herbe gagne 0,27, 0,77 et 0,96 ms (low, medium, high) : le coût des touffes est réel, mais une touffe à 80 m n'a pas besoin de ses douze brins de 3,5 cm, plus fins qu'un pixel.

## 2. Ce qui change

| # | Règle |
| --- | --- |
| Y22-1 | Touffes d'herbe (`grass_tufts.gd`) : deux MultiMesh par tronçon de 40 m, la gerbe complète (12 brins, 108 sommets) jusqu'à `LOD_SWITCH_M` = 40 m et une gerbe simplifiée (5 brins d'un triangle, deux fois plus larges, 15 sommets) au-delà. Le passage se fait touffe par touffe dans `tree_sway.gdshader` (`lod_begin_m`, `lod_end_m`), en fondu de taille sur ± 4 m : pas de front visible. |
| Y22-2 | Chaque MultiMesh a la boîte de son tronçon (`custom_aabb`) : le tronçon derrière la caméra et ceux hors du champ ne sont plus dessinés (avant : un seul MultiMesh pour toute la fenêtre, jamais écarté). Sa plage de visibilité (distance au centre de la boîte) écarte la gerbe complète d'un tronçon dont toutes les touffes sont au-delà du passage. |
| Y22-3 | Le tirage du fondu vient de la touffe (`INSTANCE_CUSTOM.x`, `pick_of`) au lieu d'un hachage de sa position dans le shader : la gerbe lointaine ne reçoit que les touffes que le fondu montre encore au-delà du passage, même choix côté CPU et GPU. |
| Y22-4 | Fondu de l'herbe : essayé à 120 m le 5 novembre, remis à 150 m le 6 (« l'herbe ne va pas assez loin »). Bande large en plus : places de 15 à 40 m du bord (`WIDE_BAND_MAX_M`), budget `grass_tufts_wide` = 1 000, 5 000, 12 000 (low, medium, high), environ un tiers de la densité du bord ; au-delà de 40 m de la caméra elles sont en gerbe simplifiée. |
| Y22-5 | Rangs de vigne des cultures (`tree_species.gd`, `lod0_m` = 200 m) : modèle lointain au-delà de 200 m au lieu de 450, arbre par arbre dans le shader ; l'ombre portée s'arrête au même endroit (distance à la caméra principale, `MAIN_CAM_INV_VIEW_MATRIX`, aussi dans la passe d'ombre). Le modèle lointain d'un rang devient une haie pleine (10 triangles) au lieu de deux panneaux croisés de 6 m qui barraient le rang en travers. Les arbres gardent le passage par case à 450 m (demande du 1er novembre). |
| Y22-7 | Sol (demande du propriétaire, 6 novembre : « l'herbe n'est plus satisfaisante », touffes 3D seulement au bord de la route) : prés plus ou moins mûrs peints par `terrain_shade.gdshaderinc` (`macro_variation` = 0,6, plaques de 90 à 250 m, jusqu'à ±18 % sur le rouge, plus claires et jaunes ou plus sombres et vertes ; le premier réglage, 0,35 sur 230 et 600 m, ne se voyait pas sur les captures du 6 novembre), sur tous les matériaux de terrain (`TerrainMaterial.apply_shared`). Variante « terrain_macro » de l'étude, ≈ 0 ms en medium. |
| Y22-8 | Touffes peintes sur le sol (6 novembre : « le but est d'avoir une illusion d'herbe sur l'ensemble du paysage ») : `terrain_shade.gdshaderinc` assombrit les creux et éclaircit (plus jaune) les gerbes, bruits de 0,6 et 2 m, effacés quand leur pas devient plus fin qu'un pixel (`sd_visible`, dérivées hors des branches) ; suit le relief de l'herbe. Le sol lit comme de l'herbe bien au-delà des touffes 3D. |
| Y22-9 | Tests graphiques : la bande large remplit une fenêtre de touffes deux fois plus grande, au plus 120 par image ; sous Vulkan logiciel (CI) la vue fixe était capturée avant la fin et la scène figée changeait encore 2 s plus tard (SSIM 0,993 en low). Les captures portent `decor_pending` (tronçons d'herbe pas encore remplis et forêts lointaines en attente, `main.gd`) et `visual_check.py` reprend une scène de référence tant qu'il n'est pas à 0, comme `streaming_pending`. |
| Y22-6 | Budgets de touffes du bord (1 500, 8 000, 20 000) et distances d'ombre inchangés ; seul `grass_tufts_wide` s'ajoute. |

## 3. Fichiers

- `engine/scripts/grass_tufts.gd`, `engine/shaders/tree_sway.gdshader`
- `engine/scripts/tree_species.gd`, `engine/scripts/tree_renderer.gd`
- `engine/shaders/terrain_shade.gdshaderinc`, `engine/scripts/terrain_material.gd` (`test_terrain_material` §9)
- `engine/tests/unit/test_grass_tufts.gd` (`_test_far_lod`), `engine/tests/unit/test_vegetation_biomes.gd` (`_test_vine_lod`)

## 4. Recette (PC, via le fil de fusion)

1. Tests du moteur (`engine/tests/run_engine_tests.sh`) : `test_grass_tufts`, `test_vegetation_biomes`, `test_living_world`, `test_herbe_route`.
2. `cout_rendu.py` sur le biome cultures, base contre cette branche, en low, medium et high (budgets 6, 12 et 14 ms), avec le nombre d'images de plus de 50 et 100 ms.
3. Captures avant/après en low, medium et high : herbe du bord de route de 20 à 120 m (pas de front au passage de 40 m), rangs de vigne de 150 à 300 m (pas de saut à 200 m). Fusion après validation des captures par le propriétaire.

Pistes laissées pour plus tard : même passage propre pour les buissons nains et les roseaux (`lod0_m`), et pour les herbes hautes de `ground_details.gd` (savane, steppe).
