# Lot S1 – Ne pas dessiner ce que le cycliste ne voit pas

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Ne pas dessiner ce que le cycliste ne voit pas : étude mesurée au banc simulé, puis réductions sans changement visible | GDScript | O1, Q2 (mêmes fichiers) | Moyenne | Oui (essai sur la GTX 1060 par le propriétaire) ; issue #190. S1a (tuiles proches et arbres hors du champ, 28 octobre) mesuré sans gain, livré coupé par défaut (`--culling=on` pour l'essayer) ; S1b (occlusion) et S1c (décor hors vue) à suivre ; étude : `docs/ETUDE_RENDU_INVISIBLE.md` |

## 1. Objectif

Demande du propriétaire (25 octobre) : explorer l'optimisation du moteur graphique en ne modélisant pas ce qui est invisible pour l'utilisateur. En 1.0, la caméra regarde devant, le long de la route, à 1,4 m du sol ; en 2.0, le lot V12 ajoute trois autres vues (suivi proche, suivi éloigné en hauteur, latérale). Le brouillard et la distance de vue restent fixés par le préréglage de qualité. Une bonne partie de ce qui est construit, chargé ou dessiné ne se voit donc jamais : tuiles lointaines au-delà du brouillard, décor derrière le cycliste, arbres et bâtiments cachés par une colline, ombres hors du champ. Ce lot est d'abord une **étude mesurée**. Il recense ce qui est invisible, mesure ce que cela coûte, puis applique seulement les réductions qui font gagner des images par seconde sans aucun changement visible.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/RECETTE_E3_E4.md`, `docs/OUTILS_DE_TEST.md` §3 (banc simulé), `docs/lots/LOT_O1_preparation_arbres.md` (budget de préparation des arbres), `docs/lots/LOT_P20_packs_textures_performance.md` (budget de la 2.0).
2. Code : `engine/scripts/world_streamer.gd` (fenêtre de tronçons, tuiles proches à 1 500 m, tuiles lointaines à 12 km), `terrain_tiles.gd`, `tree_renderer.gd` (`visibility_range` des niveaux de détail), `osm_streamer.gd`, `quality_presets.gd` et `render_quality.gd` (distance de vue, brouillard, ombres), `main.gd` (ligne `[perf-rendu]`) ; `engine/project.godot` (rendu `forward_plus`, indication `mobile` pour le préréglage `low`).
3. Banc : `engine/tests/sim_bench.py` (courbe des images par seconde, appels de dessin par capture), `make_sim_world.py` (village simulé).

## 3. Prérequis

Aucun lot. Ne pas faire en même temps que O1 (`tree_renderer.gd`) ni que Q2 (`terrain_tiles.gd`, exagération du relief) : à faire après eux, ou l'un après l'autre.

## 4. Travail demandé

**Étape 1 – Mesure de référence (avant toute modification).**
- Ajouter au banc simulé un scénario `rendu_invisible` (parcours `village` puis `demo`, vitesse constante, 5 min, préréglages `low` et `medium`).
- Enrichir `[perf-rendu]` (mode test seulement, ou au niveau existant si le coût est nul) : objets dessinés, sommets dessinés, nombre de tuiles proches et lointaines chargées, nombre d'instances d'arbres actives, mémoire vidéo.
- Rapport `docs/ETUDE_RENDU_INVISIBLE.md` : pour chaque catégorie (tuiles lointaines, tuiles proches derrière la caméra, tronçons de route derrière, arbres, bâtiments, eau, ombres), ce qui est chargé, ce qui est dessiné, et la part qui est hors champ, au-delà du brouillard ou masquée par le relief.

**Étape 2 – Pistes à essayer, chacune mesurée seule (avant / après sur le banc) :**
1. **Au-delà du brouillard :** ne plus charger ni dessiner les tuiles lointaines au-delà de la distance où le brouillard est opaque (aujourd'hui 12 km chargés pour 3 km de vue en `low`), avec une marge pour l'horizon.
2. **Hors du champ de la caméra active :** le tri se fait sur le cône de vue de la caméra active (position, cap, champ de vision), jamais sur la position du cycliste seule, pour rester juste dans toutes les vues (spécification générale, 2.0-CAM-5) ; marge pour le tangage de Q2 et pour la transition entre deux vues (moins d'une demi-seconde). Tuiles et décor entièrement derrière : ni construits ni dessinés, sauf ce qui sert aux ombres visibles.
3. **Distances de visibilité :** `visibility_range_end` (avec fondu) sur les bâtiments, l'eau et les petits objets, réglées par préréglage dans `quality_presets.gd`.
4. **Masqué par le relief :** occlusion par le terrain. Godot 4.3 propose l'occlusion en `forward_plus` comme en `mobile` (`OccluderInstance3D`, réglage `rendering/occlusion_culling/use_occlusion_culling`). Essayer des occulteurs simples tirés des tuiles de terrain (crêtes), et mesurer le coût du calcul contre le gain. Alternative sans occulteur : test de ligne d'horizon par tuile depuis le profil de la route.
5. **Ombres :** distance des ombres limitée au champ réellement visible (150 m en `low`, 300 m en `medium`), cascades revues.
6. **Construction :** ne pas lancer le calcul des sommets (WorkerThreadPool) d'une tuile ou d'un tronçon qui sera invisible à son arrivée.

**Étape 3 – Garder ce qui gagne.** Une piste est retenue si elle fait gagner au moins 3 % d'images par seconde en moyenne ou 1 ms sur le temps d'image p99 sur le banc, sans aucun changement visible (comparaison des captures du banc avant et après, à la même position) et sans apparition d'objets à l'écran. Chaque piste retenue a son interrupteur dans `quality_presets.gd` pour pouvoir la couper.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/world_streamer.gd`, `terrain_tiles.gd`, `osm_streamer.gd`, `tree_renderer.gd` (après O1), `quality_presets.gd`, `render_quality.gd`, `main.gd` (ligne `[perf-rendu]` seulement) ; `engine/tests/sim_bench.py` ; `engine/tests/README.md`, `docs/OUTILS_DE_TEST.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `engine/tests/sim_bench_scenarios/rendu_invisible.json`, `engine/tests/unit/test_culling.gd` (choix de ce qui est chargé ou dessiné selon la position et le cap de la caméra, sans affichage), `docs/ETUDE_RENDU_INVISIBLE.md`.
- **Interdits :** le core, le contrat IPC, le format `.world`, les shaders du terrain et de la route (E2), les données des thèmes.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `run_engine_tests.sh` passe (hors échec connu `test_tree_renderer`, #119) ; `pytest` du core inchangé.
2. `test_culling.gd` : la fonction de tri reçoit la caméra active en paramètre ; avec la vue subjective puis avec une caméra placée 6 m derrière et 3 m au-dessus, une tuile entièrement hors du cône de la caméra donnée, ou au-delà de la distance de brouillard opaque plus la marge, n'est ni construite ni dessinée ; une tuile qui entre dans le champ (virage serré, épingle d'`essai-69`) l'est assez tôt pour être prête avant d'être visible (vérifié sur la trajectoire de la route, pas seulement sur la position).
3. Banc simulé, préréglages `low` et `medium`, avant et après : tableau des images par seconde (moyenne, p99), des objets et sommets dessinés et de la mémoire vidéo dans `docs/ETUDE_RENDU_INVISIBLE.md`, pour chaque piste essayée, retenue ou non.
4. Captures du banc avant et après à la même position : aucune différence visible (comparaison automatique avec un seuil, plus la planche dans le rapport).
5. Aucune apparition soudaine d'objet (« pop ») : le banc vérifie qu'aucun objet ne devient visible à moins de la distance de fondu.

**Sur le PC cible (le propriétaire) :** rouler `essai-69` en `low` puis en `medium` avec les pistes retenues ; comparer les lignes `[perf-rendu]` à celles de l'essai du 25 octobre (59,4 images/s en moyenne, p99 22 ms en `low`) et dire si quelque chose apparaît ou disparaît à l'écran.

## 8. Hors périmètre

- Changer le contenu ou la densité du décor (préréglages, thèmes, packs de textures P20).
- Changer de moteur de rendu (`forward_plus` vers `mobile`, ou l'inverse).
- La préparation des arbres sur le processeur (O1).
