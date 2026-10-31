# Lot Y4 – Ombres : ce qui en porte, jusqu'où, et à quel coût

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Ombres : objets qui en portent, distance et répartition des cascades par préréglage (la qualité des ombres est dans Y13) | GDScript | Y2 | Petite | Oui ; issue #360 |

## 1. Objectif

Série Y (fin de projet, `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §4, technique T4). Avec PSSM, un objet présent dans plusieurs cascades est dessiné une fois par cascade pour les ombres, plus une fois pour l'image. La **qualité** des ombres (atlas, filtre, nombre de cascades) est réglée par l'étape 1 du cahier Y13 (PR #446) ; ce lot s'occupe du **coût** :

- quels objets portent une ombre (petits objets, objets lointains, objets en mouvement) ;
- jusqu'où le soleil projette des ombres dans chaque préréglage, et comment les cascades se partagent cette distance.

Règle de la série : une piste n'est gardée que si elle gagne au moins 3 % d'images/s ou 1 ms de p99 au banc simulé, sans changement visible non voulu ; mesures en `medium`, puis en `low`.

## 2. À lire

1. `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §4 (T4) ; documentation de Godot « Lights and shadows » ; cahier Y13 (PR #446) §5 et §8 ; `docs/lots/LOT_S1_rendu_invisible.md` (piste 5).
2. Code : `engine/scripts/render_quality.gd` (soleil, distance des ombres), `quality_presets.gd`, et chaque script qui crée des objets 3D : `tree_renderer.gd`, `osm_streamer.gd`, `roadside_props.gd`, `fauna_renderer.gd`, `traffic_renderer.gd`, `crowd_renderer.gd`, `wind_turbines.gd`, `flags.gd`, `bots_view.gd`, `segment_markers.gd`, `grass_tufts.gd` ; `engine/scripts/perf_probe.gd`.

## 3. Prérequis

Y2 livré ; étape 1 de Y13 fusionnée (sinon, faire d'abord sa partie ombres).

## 4. Travail demandé

- **Inventaire** (dans ce cahier) : pour chaque sorte d'objet, s'il porte une ombre aujourd'hui, sa taille, sa distance d'affichage ; mesure du temps GPU des ombres au banc (sonde X13 avec et sans ombres du soleil).
- **Règles proposées**, chacune mesurée seule puis gardée ou non :
  1. aucune ombre pour les objets de moins de 1 m de haut (touffes d'herbe, bornes, petits panneaux, lièvres, oiseaux) ;
  2. aucune ombre au-delà de la distance des ombres du préréglage pour les objets placés par case (arbres de LOD 1, bâtiments lointains : déjà en partie fait) ;
  3. véhicules lointains et objets du ciel sans ombre (P25, P26) ;
  4. distance des ombres du soleil : 150 / 300 / 600 m aujourd'hui, essai de 120 / 250 / 500 m ; répartition des cascades (`directional_shadow_split_1` à `_3`) resserrée près de la caméra, « Blend Splits » coupé ;
  5. ombres des bots et du cycliste toujours gardées (repère de vitesse et de position).
- Chaque règle gardée a son interrupteur dans `quality_presets.gd` (table `SHADOWS`, distinct de la table d'image de Y13), pour pouvoir la couper si un défaut apparaît.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/quality_presets.gd`, `render_quality.gd` et les scripts de rendu du §2.2 (une ligne `cast_shadow` chacun au plus) ; `engine/tests/unit/test_quality_presets.gd`, `test_render_quality.gd` ; ce cahier, `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` (résultats), `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** atlas, filtre et nombre de cascades (Y13), le compilateur, le core, les contrats.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier ; `test_quality_presets.gd` vérifie la table `SHADOWS` (distances croissantes de `low` à `high`, bots et cycliste toujours avec ombre).
2. Tableau du banc par règle (gain en images/s et en p99, temps GPU des ombres) en `medium` et en `low` ; seules les règles qui gagnent restent actives.
3. Captures avant et après au même instant : ombres des arbres proches, des maisons, des bots et du cycliste présentes.

**Sur le PC cible (le propriétaire) :** séance de 15 min en `medium` : aucune ombre qui saute à la limite de distance, ombres sous les arbres toujours visibles.

## 8. Hors périmètre

- Qualité des ombres (atlas, filtre, cascades) : Y13 ; ombre des nuages au sol : Y12.
