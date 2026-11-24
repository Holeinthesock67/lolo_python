# Lot AC6 – Premier affichage du monde à froid : une doublure de shader par image

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| À-coups (fil du 24 novembre) : au premier lancement à shaders froids, la première tuile proche et ses arbres ne sont plus dessinés d'un coup ; une doublure minuscule de chaque shader nouveau est dessinée une image à la fois avant le départ | GDScript | PI1, PI2, AC2 | Petite | **En revue** |

## 1. Objectif

Au tout premier lancement (installation, mise à jour du pilote : caches de shaders vides), les bancs rAC (DB1 low,
medium, high) et rACow (monde ouvert ea1_lac medium) du 23 novembre gardent avant le premier mètre une ou deux
images de **5,4 à 6,6 s** : la première tuile proche et ses arbres sont dessinés pour la première fois, avec 22 à 49
pipelines compilés dans la même image (étapes « tuile near:0:0 », « arbres near:0:0 », puis tuiles voisines). Cette
famille existe sur main sans AC2 (r940b, pi2). Shaders en cache, elle disparaît.

## 2. Cause (essais au cloud, Godot 4.7.2, Vulkan logiciel, 24 novembre)

24 matériaux de shaders différents :

| Cas | Image la plus longue |
| --- | --- |
| objets ajoutés et dessinés dans la même image (ce que fait `world_streamer.integrate`) | 5,1 s (26 pipelines de surface + 25 spécialisés) |
| objets ajoutés cachés, puis montrés tous ensemble 20 images plus tard | 0,5 s à la création (pipelines de surface en fond), puis 4,3 s au premier dessin (25 spécialisés) |
| doublures ajoutées cachées, puis montrées **une par image** | 30 à 720 ms par image ; le premier vrai dessin ne compile plus rien |

Banc du correctif (12 MultiMesh d'arbres + 12 maillages, ombres, caches vidés) : pire image **4,7 à 6,1 s → 0,6 à
0,7 s**, objets affichés au bout de 6,6 s au lieu de 6,1 s (27 images au lieu d'une).

## 3. Spécification

| # | Règle |
| --- | --- |
| AC6-1 | `shader_warm.gd` : `keys_of(objet)` donne un couple par surface (MeshInstance3D ou MultiMeshInstance3D, format des sommets, shader, ombres). Deux ShaderMaterial du même shader (un matériau dupliqué par tuile) donnent la même clé. |
| AC6-2 | `hold(objets)` : si un couple n'a jamais été dessiné, les objets sont cachés et une **doublure** est créée cachée par couple nouveau (même maillage et matériaux, une instance pour un MultiMesh, mêmes ombres, sans plage de visibilité). |
| AC6-3 | `step(caméra)` : deux images d'attente après une création (pipelines de surface en fond), puis une doublure dessinée par image, minuscule (échelle 0,001), 2 m devant la caméra. Les objets réapparaissent avec leur visibilité d'avant quand tous leurs couples sont dessinés. Chaque doublure est notée dans la sonde (étape « shaders doublure N »). |
| AC6-4 | `world_streamer.integrate` passe à `hold` chaque tuile ou tronçon créé et les MultiMesh de ses arbres (`tree_renderer.tile_nodes`). `pending()` s'ajoute à `pending_count()` : le départ attend la fin (start_wait_model, PI2-4). |
| AC6-5 | En séance (`session_state` RUNNING, `main.gd`) : `set_active(false)` rend tout visible et rien n'est plus caché (une tuile retardée pourrait se voir). Les couples jetés sont repris au chargement suivant. |
| AC6-6 | Garde-fou : sans caméra, tout redevient visible après 3 600 images. Réglage de test `shader_warm` (défaut vrai) pour couper le lot. |
| AC6-7 | Hors lot : tronçons OSM (AC2, #953), forêts lointaines (préchauffées par PI2), image du chargement lui-même (13 s à froid : écran de chargement, ciel, portiques), arbres « ombre seule ». |

## 4. Fichiers

- `engine/scripts/shader_warm.gd`, `engine/tests/unit/test_shader_warm.gd` ;
- `engine/scripts/world_streamer.gd` (`shader_warm`, `integrate`, `pending_count`), `engine/scripts/tree_renderer.gd`
  (`tile_nodes`), `engine/scripts/main.gd` (création, séance).

## 5. Critères d'acceptation

- Tests unitaires `test_shader_warm` et suite de l'engine verts en CI.
- Recette PC (shaders froids, `--shaders froid`) : DB1 low, medium, high et monde ouvert ea1_lac medium : plus
  d'image de plus de 1,5 s portant « tuile near » ou « arbres near » avant le premier mètre ; étapes « shaders
  doublure » visibles dans saccades.csv ; départ pas plus tardif de plus de 2 s qu'avant. Shaders chauds : pas de
  différence de départ notable.

## 6. Livraison

À remplir à la fusion.
