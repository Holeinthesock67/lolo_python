# Lot Y5 – Arbres lointains en imposteurs, écrits par nous

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Arbres lointains en imposteurs (notre propre version, sans extension), feuillage en alpha scissor | GDScript + shader | O1, Y2 | Moyenne | Oui (aspect validé par le propriétaire) ; issue #361 |

## 1. Objectif

Série Y (fin de projet, `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §4, techniques T5 et T10). Aujourd'hui (`tree_renderer.gd`), un arbre est un modèle bas poly avec ombre jusqu'à 450 m (LOD 0), deux quadrilatères croisés sans ombre jusqu'à 1 500 m (LOD 1), puis plus rien : au-delà de 1,5 km, les forêts disparaissent alors que le brouillard ne se ferme qu'à 4, 6 ou 9 km (Y1). Ce lot ajoute un troisième niveau :

- un **imposteur** par arbre au-delà de 1 500 m : un seul quadrilatère tourné vers la caméra, dont l'image est choisie dans un atlas capturé sous plusieurs angles ;
- des forêts visibles jusqu'au brouillard, pour quelques sommets par arbre ;
- la densité réglée par `visible_instance_count` sans reconstruire les `MultiMesh`.

Décision du propriétaire du 27 octobre (§0, question 9) : **notre propre version** (un shader et un petit outil de capture), sans l'extension externe *Octahedral Impostors* ; l'aspect est validé par le propriétaire.

## 2. À lire

1. `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §4 (T5, T10) ; documentation de Godot « Using MultiMesh », « MultiMesh » (`visible_instance_count`, `custom_aabb`), « Mesh LOD ».
2. `docs/lots/LOT_O1_preparation_arbres.md`, `LOT_E3_ciel_arbres_hud.md`, `LOT_P5_vent_vegetation.md` (shader `tree_sway`).
3. Code : `engine/scripts/tree_renderer.gd` (`build_lod0_mesh`, `build_lod1_mesh`, cases de 250 m, budget), `vegetation_placer.gd`, `quality_presets.gd` (`tree_budget`, `fog_end_m`), `engine/shaders/tree_sway.gdshader`.

## 3. Prérequis

O1 et Y2 livrés ; Y3 et Y4 utiles (mêmes mesures de base).

## 4. Travail demandé

- **Outil de capture** (nouveau `engine/tools/bake_impostors.gd`, lancé à la main ou par `run_engine_tests.sh` en mode vérification) : rend le modèle LOD 0 de chaque sorte d'arbre (feuillus, conifères, verger si différents) sous 8 angles autour de l'axe vertical et 2 hauteurs de vue (0° et 30°), sur fond transparent, éclairage neutre, dans un atlas de 2 048 × 512 au plus avec sa carte de normales ; écrit `engine/assets/impostors/trees.png` et `trees_normal.png`, déterministes (même modèle, mêmes pixels à ± 1 niveau près). Les images sont générées par notre outil depuis nos modèles : aucune image externe.
- **Shader** (nouveau `engine/shaders/tree_impostor.gdshader`) : quadrilatère tourné vers la caméra autour de l'axe vertical, image choisie d'après l'angle de vue (fondu entre les deux images voisines), éclairage par la carte de normales, couleur par instance (même variation que les LOD 0 et 1), `alpha scissor` (pas de mélange transparent), balancement léger du vent repris de `tree_sway` (amplitude réduite).
- **Troisième niveau** (`tree_renderer.gd`) : par case, un `MultiMeshInstance3D` de plus pour les imposteurs, de `LOD1_MAX_DIST_M` à la fin des tuiles proches chargées ; au-delà, sur les tuiles lointaines, imposteurs seulement dans les forêts de la couche `vegetation` (densité réduite, `FAR_FOREST_FACTOR` 0,25), jusqu'à `fog_end_m`. Sans ombre. `visible_instance_count` règle la densité par préréglage ; `custom_aabb` posé pour éviter le calcul des boîtes.
- **Feuillage** des LOD 0 et 1 en `alpha scissor` s'il utilise de la transparence aujourd'hui (sinon rien à changer).
- **Budget** : `tree_budget` du préréglage compte les trois niveaux ; nouvelle clé `impostor_budget` dans `quality_presets.gd` (proposition 20 000 / 60 000 / 120 000, à mesurer).
- **Mesures** : banc simulé avec la sonde X13, monde OSM boisé, en `medium` puis `low` ; captures avant et après au même instant pour la recette de l'aspect.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/tree_renderer.gd`, `quality_presets.gd` ; `engine/tests/unit/test_tree_renderer.gd`, `test_quality_presets.gd`, `engine/tests/perf_budgets.json` (`tree_tile_high`) ; ce cahier, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `engine/tools/bake_impostors.gd`, `engine/shaders/tree_impostor.gdshader`, `engine/assets/impostors/trees.png`, `trees_normal.png`, `engine/tests/unit/test_tree_impostor.gd`.
- **Interdits :** `vegetation_placer.gd` (placement inchangé), le compilateur, le core, les contrats ; extensions externes.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier ; l'outil de capture redonne le même atlas.
2. Choix de l'image : pour un angle de vue de 0°, 45°, 90°… l'image attendue de l'atlas ; fondu continu entre deux angles.
3. Aucun arbre à moins de 1 500 m en imposteur ; aucun imposteur au-delà de `fog_end_m` ; budgets tenus ; temps de construction d'une case dans `tree_tile_high`.
4. Banc simulé en `medium` : forêts visibles jusqu'au brouillard pour moins de 1 ms de GPU de plus, ou mieux ; sinon, distance réduite jusqu'à tenir ce coût.

**Sur le PC cible (le propriétaire) :** séance en `medium` sur un parcours boisé : forêts qui restent jusqu'à l'horizon, aucun arbre qui « tourne » visiblement en s'approchant, passage imposteur → quadrilatères croisés peu visible. **Accord du propriétaire sur l'aspect** avant la fusion (décision du 27 octobre).

## 8. Hors périmètre

- Nouvelles espèces d'arbres (U7, version 3.0) ; arbres en saison (P18, version 2.0) ; buissons et haies.
