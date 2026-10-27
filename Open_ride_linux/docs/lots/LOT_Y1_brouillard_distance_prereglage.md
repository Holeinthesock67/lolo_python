# Lot Y1 – Brouillard, distance de la caméra et tuiles lointaines par préréglage

## 1. Objectif

Décision du propriétaire du 27 octobre (réponses aux questions de `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md`, question 3 : lot avancé, à faire tout de suite). Aujourd'hui, quel que soit le préréglage, la caméra voit à 12 km (`camera.far`), le brouillard de profondeur ne devient opaque qu'à 12 km et les tuiles lointaines du terrain sont chargées sur 12 km (`WorldStreamer.FAR_RADIUS_M`). Le propriétaire trouve le brouillard trop lointain (essai du 25 octobre) et tout ce qui est au-delà du brouillard opaque est du travail perdu.

Valeurs décidées (question 4) : brouillard opaque à **4 km en `low`, 6 km en `medium`, 9 km en `high`**. Le préréglage utilisé au quotidien par le propriétaire est `medium` (question 6) : c'est la mesure de référence de ce lot.

Ce lot reprend la piste 1 du lot S1 (« au-delà du brouillard ») ; S1 garde les autres pistes.

## 2. À lire

1. `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` (§2, §4 T1, §8) ; `docs/lots/LOT_S1_rendu_invisible.md` ; `docs/OUTILS_DE_TEST.md` (banc simulé, sonde X13).
2. Code : `engine/scripts/quality_presets.gd`, `render_quality.gd` (`CAMERA_FAR_M`, `FOG_TERRAIN`, `FOG_FLAT`, `apply_preset`, `apply_fog`), `world_streamer.gd` (`FAR_RADIUS_M`, sélection des tuiles lointaines, plan d'eau de `2 × FAR_RADIUS_M`), `main.gd` (appels d'`apply_fog`), `perf_probe.gd`.
3. Tests : `engine/tests/unit/test_quality_presets.gd`, `test_render_quality.gd`.

## 3. Prérequis

Aucun lot à attendre : la sonde X13 (`perf_probe.gd`) est sur `main`. Ne pas travailler en même temps que S1 sur `world_streamer.gd`, `quality_presets.gd` et `render_quality.gd` : Y1 d'abord, S1 ensuite.

## 4. Travail demandé

1. **Mesure de référence**, avant toute modification : banc simulé (`engine/tests/sim_bench.py`, parcours `village` puis `demo`) avec la sonde X13, en `low` puis en `medium`. Garder les fichiers CSV et les captures.
2. **Préréglages** : ajouter à chaque préréglage de `quality_presets.gd` une clé `fog_end_m` (4 000 / 6 000 / 9 000 m) et une fonction `fog_end_m(name)` sur le modèle de `shadow_distance_m`. Le début du brouillard (`fog_depth_begin`) est une fraction fixe de cette fin, à choisir pour que le relief proche reste net (point de départ : 40 %), documentée en commentaire.
3. **Caméra** : `camera.far` = `fog_end_m` plus une petite marge (5 % au plus) pour que rien ne soit coupé net avant d'être entièrement dans le brouillard. Le ciel ne doit pas changer.
4. **Tuiles lointaines** : le rayon de chargement des tuiles lointaines suit `fog_end_m` plus la taille d'une tuile lointaine (marge contre l'apparition d'une tuile), au lieu de `FAR_RADIUS_M` fixe. Même chose pour la taille du plan d'eau et du sol plat. `FAR_RADIUS_M` reste le plafond (12 km).
5. **Sans relief** (`FOG_FLAT`, 300 m à 3 km) : inchangé, sauf si la fin du préréglage est plus courte.
6. **Couleur et thème** : la couleur du brouillard (`horizon`) et la densité du thème (brouillard volumétrique en `high`) ne changent pas.
7. **Clé inutilisée** : retirer la clé `renderer_hint` des préréglages (lue nulle part ; le choix du moteur Mobile pour `low` est l'essai Y7), avec son test s'il en a un.
8. **Mesure après**, mêmes scénarios, et rapport.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/quality_presets.gd`, `render_quality.gd`, `world_streamer.gd`, `main.gd` (si l'appel d'`apply_fog` doit recevoir le préréglage) ; `engine/tests/unit/test_quality_presets.gd`, `test_render_quality.gd` ; `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` (résultats, §8), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** le core, le contrat IPC, le format `.world`, les shaders du terrain et de la route, les données des thèmes.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `run_engine_tests.sh` passe (hors échec connu `test_tree_renderer`, #119) ; `pytest` du core inchangé.
2. Tests unitaires : `fog_end_m` vaut 4 000, 6 000 et 9 000 m ; un nom inconnu donne `low` ; `camera.far` est compris entre `fog_end_m` et `fog_end_m × 1,05` ; une tuile lointaine au-delà de `fog_end_m` plus une tuile n'est pas chargée, une tuile en deçà l'est.
3. Banc simulé avant et après, en `low` et en `medium` : images/s (moyenne, p99), appels de dessin, primitives, VRAM et tuiles lointaines chargées (colonnes de la sonde X13), dans le rapport.
4. Captures avant et après à la même position : seul l'horizon change (plus proche, comme décidé) ; aucune tuile ne surgit au bord du brouillard.

**Sur le PC cible (le propriétaire) :** rouler `essai-69` en `medium`, puis en `low`, et dire si l'horizon convient et si quelque chose apparaît d'un coup au loin. Comparer les lignes `[perf-rendu]` à celles du 25 octobre (59,4 images/s, p99 22 ms en `low`).

## 8. Hors périmètre

- Les autres pistes de S1 (derrière la caméra, occlusion par le relief, ombres, construction des tuiles).
- Changer de version de Godot (Y2) ou de moteur de rendu (Y7).
- Modifier la densité du décor ou les préréglages autres que la distance.
