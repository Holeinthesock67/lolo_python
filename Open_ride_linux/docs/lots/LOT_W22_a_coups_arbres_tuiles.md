# Lot W22 – À-coups des arbres à l'entrée d'une tuile proche

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| À-coups du monde ouvert avec biomes : arbres d'une tuile proche instanciés sans calcul par arbre sur le fil principal | GDScript | W17 (livré) | Petite | **Livré le 15 novembre** (PR #906) |

## 1. Objectif

Supprimer l'image lente qui apparaît quand une tuile proche de 1 km entre dans la fenêtre : la sonde rW17g du 15 novembre (monde ouvert avec biomes, départ de Sarre-Union) montre l'étape « arbres near:x:y » à 100–157 ms en une seule image. Résultat : 3,8 images lentes par minute en medium (seuil 3), pire image 133 ms ; 131 ms en high (seuil 100 ms) ; low dans les seuils.

## 2. Cause

`tree_renderer.add_tile`, appelé par `world_streamer.integrate` sur le fil principal, calculait encore chaque arbre de la tuile (jusqu'à 10 000 en forêt dense) : groupement par espèce, rotation et teinte tirées de la position, deux `set_instance_transform` et deux `set_instance_color` par arbre (un appel au serveur de rendu à chaque fois), carrés d'ombre. Seul le placement (`prepare_tile`) tournait dans la tâche de fond.

## 3. Correction

- `prepare_tile` (tâche de fond) appelle `build_cells` : par case non vide, centre, nombre d'arbres et une partie par espèce (`build_part`) avec le tampon complet de `MultiMesh.buffer` (16 flottants par arbre : transformation 3×4 puis couleur, `BUF_STRIDE`, même format que les arbres « ombre seule ») et les carrés d'ombre.
- `add_tile` ne fait plus que créer les deux `MultiMeshInstance3D` de chaque partie et copier le tampon d'un bloc (`mm.buffer = buf`, un seul appel par MultiMesh). Mêmes arbres, transformations et couleurs qu'avant.
- Pas d'étalement sur plusieurs images : au cloud, `add_tile` d'une tuile dense (10 133 arbres) passe de 14–25 ms à 0,4–0,6 ms (rendu factice, avant/après) ; à étudier seulement si le banc PC montre encore des images lentes « arbres ».

## 4. Tests

`engine/tests/unit/test_tree_renderer.gd` (`_test_add_tile_main_thread`) : budget `tree_add_tile` de `perf_budgets.json` (4 ms, 12 ms en CI) pour une tuile dense, avec et sans limite d'ombre ; tampon identique à la formule de l'ancien `_make_part` (rotation, échelle, teinte), carrés d'ombre présents seulement avec la limite. Empreintes des arbres (`FINGERPRINTS`) inchangées.

## 5. Recette sur le PC

Sonde de la rW17g rejouée en low, medium et high (scénario `w17_cap`, départ de Sarre-Union, `OPENRIDE_PERF_PROBE`) : images lentes par minute (≤ 3 de plus de 50 ms, aucune de plus de 100 ms), étape « arbres » dans `saccades.csv`, budgets GPU 8, 13 et 16 ms inchangés.

## Livraison

Branche `claude/project-thread-vtfee2`, PR #906. Banc PC rW19 du 15 novembre (nom donné avant la renumérotation du lot ; tête 91380469, `w17_cap`, sonde ; fichiers dans la bibliothèque du projet, `w19_a_coups.tar.gz`) :

| Qualité | GPU médian (budget) | Images lentes/min, avant → après | Pire image, avant → après | Saccades > 50 ms, avant → après |
| --- | --- | --- | --- | --- |
| low | 5,47 ms (8) | 0,3 → 0 | 71 → 50 ms | 22 → 6 |
| medium | 7,46 ms (13) | 3,8 → 0 | 133 → 40 ms | 109 → 7 |
| high | 8,41 ms (16) | 2,0 → 0,3 | 131 → 68 ms | 32 → 32 |

Plus aucune saccade « arbres ». Reste en high 25 saccades « herbe » (18 avant) : sujet d'un lot suivant.
