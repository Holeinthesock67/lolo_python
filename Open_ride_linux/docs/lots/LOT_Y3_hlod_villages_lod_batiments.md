# Lot Y3 – Villages au loin en un seul bloc (HLOD) et niveaux de détail des bâtiments

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| HLOD des villages et niveaux de détail des bâtiments | GDScript | Y2, S1 | Moyenne | Oui ; issue #359 |

## 1. Objectif

Série Y (fin de projet, `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §4, techniques T3 et T9). Aujourd'hui chaque bâtiment OSM d'un tronçon est dessiné de près comme de loin jusqu'à `visibility_range_end` (1,5 / 2,5 / 4 km selon le préréglage), puis disparaît d'un coup ; un village lointain coûte autant d'objets que de près. Ce lot :

- regroupe les bâtiments de chaque village en un **bloc simplifié** affiché au loin, à la place des maisons séparées (`visibility_parent`, exemple même de la documentation de Godot) ;
- fait passer d'un niveau à l'autre **sans transparence** (mode de fondu « Disabled » avec une marge, plutôt que « Self ») ;
- permet de garder les villages visibles jusqu'au brouillard (Y1) pour moins d'appels de dessin qu'aujourd'hui.

Règle de la série : une piste n'est gardée que si elle gagne au moins 3 % d'images/s ou 1 ms de p99 au banc simulé, sans changement visible non voulu ; mesures en `medium` (préréglage de référence du propriétaire) puis en `low`.

## 2. À lire

1. `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §4 (T3, T9) ; documentation de Godot « Visibility ranges (HLOD) » et « Mesh LOD ».
2. `docs/lots/LOT_S1_rendu_invisible.md` (piste 3, distances de visibilité : S1 fait d'abord les réglages simples) et son rapport `docs/ETUDE_RENDU_INVISIBLE.md` s'il existe ; `docs/lots/LOT_E4_osm_eau_sons.md`, `LOT_L1_maillage_batiments.md`.
3. Code : `engine/scripts/osm_streamer.gd` (`_build_chunk_job`, `visibility_range_end`, ombres), `building_mesh.gd`, `quality_presets.gd`, `perf_probe.gd` ; `engine/tests/sim_bench.py`.

## 3. Prérequis

Y2 (Godot 4.7, LOD générés plus propres en 4.6) et S1 livrés.

## 4. Travail demandé

- **Regroupement** (`building_mesh.gd`, sans nœud) : les bâtiments d'un tronçon sont regroupés en grappes par une grille de 200 m (une grappe = les bâtiments dont le centre tombe dans la même case) ; une grappe d'au moins 6 bâtiments reçoit un **bloc** : un seul maillage fait de la boîte englobante orientée de chaque bâtiment (murs et toit plat, 12 triangles par bâtiment, mêmes couleurs), sans les cours ni les trous.
- **Affichage** (`osm_streamer.gd`) : par grappe, un nœud parent qui porte le bloc et des enfants qui portent les maisons détaillées ; maisons de 0 à `HLOD_NEAR_M` (600 / 800 / 1 000 m en `low` / `medium` / `high`), bloc de `HLOD_NEAR_M` jusqu'à la distance des bâtiments du préréglage, qui peut alors monter jusqu'à `fog_end_m` (Y1) si la mesure le permet ; `visibility_range_fade_mode` « Disabled » et une marge de 10 % (hystérésis) ; aucun bloc pour une grappe de moins de 6 bâtiments (maisons isolées : elles gardent leur distance actuelle). Le bloc ne porte pas d'ombre.
- **LOD des maisons détaillées** : seuil des LOD automatiques par préréglage (`mesh_lod_threshold`, déjà réglé par l'étape 1 de Y13 si elle est fusionnée ; sinon dans ce lot) ; LOD générés pour les maillages construits par code si `ImporterMesh.generate_lods()` est disponible dans un jeu lancé hors de l'éditeur (à vérifier en 4.7 ; sinon, garder le bloc seul).
- **Construction** : le bloc est calculé dans la même tâche de fond que les maisons (`WorkerThreadPool`), sans travail de plus sur le fil principal.
- **Mesures** : banc simulé avec la sonde X13, monde OSM avec villages, en `medium` puis `low` : appels de dessin, primitives, temps CPU et GPU, p99 ; captures avant et après au même instant (aucune maison qui surgit ni qui clignote au passage de `HLOD_NEAR_M`).

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/building_mesh.gd`, `osm_streamer.gd`, `quality_presets.gd` (`HLOD_NEAR_M`, distance des bâtiments) ; `engine/tests/unit/test_building_mesh.gd`, `test_quality_presets.gd`, `engine/tests/test_osm_streamer.gd`, `engine/tests/perf_budgets.json` ; ce cahier (mesures), `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` (résultat), `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** toits et façades (Y8), arbres (Y5), le compilateur, le core, les contrats.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Regroupement déterministe ; une grappe de 6 bâtiments a un bloc de 72 triangles, une grappe de 5 n'en a pas ; le bloc couvre l'emprise de chaque bâtiment (boîte englobante) et a ses couleurs.
3. À `HLOD_NEAR_M` − 5 % : maisons seules ; à + 15 % : bloc seul ; aucun matériau transparent pendant le passage.
4. Banc simulé en `medium` : au moins 3 % d'images/s ou 1 ms de p99 gagnés, ou des villages visibles plus loin à coût égal ; sinon, le lot le dit et ne garde que ce qui gagne.

**Sur le PC cible (le propriétaire) :** traverser un parcours avec des villages en `medium` : aucun village qui saute ou clignote au loin ; avis sur la distance d'affichage des villages.

## 8. Hors périmètre

- Toits à pans et façades (Y8) ; occlusion par le relief (S1) ; arbres en imposteurs (Y5).
