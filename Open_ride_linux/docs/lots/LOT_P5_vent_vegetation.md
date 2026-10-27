# Lot P5 – Vent dans les arbres et touffes d'herbe

## 1. Objectif

Faire bouger la végétation avec le vent du modèle P4 : les arbres se balancent (fort à la cime, nul au pied), plus vivement sous les rafales ; en qualité moyenne et haute, des touffes d'herbe en bord de route ondulent avec le vent apparent (le vent qui suit la vitesse du cycliste). C'est le gain visuel le plus fort pour le moindre coût : tout se fait dans le shader de sommets, sans nouvelle instance en qualité basse.

## 2. À lire

1. `docs/lots/00_INDEX.md` (budget de la série P), `docs/lots/LOT_P4_modele_vent_engine.md`, `docs/lots/LOT_E3_ciel_arbres_hud.md` (arbres, LOD, budget d'instances), `docs/lots/LOT_O1_preparation_arbres.md`.
2. Code : `engine/scripts/tree_renderer.gd` (`_init_materials`, `build_lod0_mesh`, `build_lod1_mesh`, `add_tile`), `engine/scripts/vegetation_placer.gd`, `engine/shaders/terrain.gdshader` (style), `engine/tests/render/test_terrain_render.gd` (tests de rendu sous Xvfb).

## 3. Prérequis

P4 livré. O1 livré (même fichier `tree_renderer.gd`). Version 1.0 publiée.

## 4. Travail demandé

- Nouveau shader `engine/shaders/tree_sway.gdshader` (spatial, couleur des sommets comme les matériaux actuels) :
  - déplacement horizontal = `dir × strength × (hauteur relative)² × amplitude`, oscillation `sin(phase × fréquence + décalage par instance)` ; décalage tiré de la position de l'instance (aucune donnée ajoutée au `MultiMesh`) ;
  - rafale : amplitude et fréquence augmentées par `gust` ;
  - LOD1 (panneaux croisés) : même mouvement, amplitude réduite ;
  - paramètres globaux du shader (`global uniform`) `wind_dir`, `wind_strength`, `wind_gust`, `wind_phase`, mis à jour une fois par image par un seul appel (pas de boucle sur les tuiles).
- `tree_renderer.gd` : matériaux LOD0 et LOD1 en `ShaderMaterial` quand `living(preset).tree_sway` est vrai, `StandardMaterial3D` actuel sinon (rendu identique à aujourd'hui).
- Nouveau `engine/scripts/grass_tufts.gd` (nœud `Node3D` autonome) : touffes en `MultiMesh` (trois quads croisés), placées de façon déterministe sur une bande de 2 à 15 m de part et d'autre de la route autour de la caméra, hors bâtiments et eau, densité réduite avec la pente ; nombre borné par `living(preset).grass_tufts` (0 en `low` : nœud vide) ; même shader avec le vent apparent.
- Prévoir dans le shader un `uniform` de teinte du feuillage, neutre par défaut, que P18 (saisons, version 2.0) réglera.

## 5. Fichiers concernés

- **Nouveaux :** `engine/shaders/tree_sway.gdshader`, `engine/scripts/grass_tufts.gd`, `engine/tests/unit/test_grass_tufts.gd`, `engine/tests/render/test_tree_sway_render.gd`.
- **Modifiés :** `engine/scripts/tree_renderer.gd` (matériaux seulement), `engine/tests/unit/test_tree_renderer.gd`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd` (le branchement est fait par P16), `vegetation_placer.gd`, le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier, rendu compris (Xvfb).
2. Test de rendu : arbre seul, vent nul puis vent fort, deux images à 0,5 s d'écart : les pixels du pied de l'arbre ne bougent pas (à 2/255 près), ceux de la cime bougent ; vent nul : deux images identiques.
3. `tree_sway = false` : matériaux et rendu identiques à avant le lot (empreinte d'O1 inchangée, test de rendu identique).
4. Touffes : même position pour la même graine ; aucune touffe sur la route, l'eau ou un bâtiment ; nombre jamais au-dessus du budget ; 0 en `low`.
5. Coût CPU par image du lot (mise à jour des paramètres globaux et des touffes) sous 0,2 ms, mesuré dans le test.
6. Aucune image visuelle de référence ne change avec le vent nul (`engine/tests/run_visual_tests.sh`).

**Sur le PC cible (le propriétaire) :** séance de 10 min en `low` avec vent de 25 km/h : arbres qui se balancent sans clignotement ni déformation, ligne `[perf-rendu]` au-dessus de 55 images/s en moyenne, coût mesuré du lot sous 0,5 ms par image (avec et sans `tree_sway`).

## 8. Hors périmètre

- Herbe en brins sur tout le terrain, teintes et feuilles d'automne (P18, version 2.0), arbres qui plient sous la tempête.

## 9. Livraison (26 octobre 2026)

Livré sur la branche `lot-p5-vent-vegetation`, au-dessus de P4. O1 n'étant pas encore sur main, seul le choix des matériaux de `tree_renderer.gd` change (rien dans la préparation des arbres).

- **`tree_sway.gdshader`** : déplacement horizontal = direction × force × (hauteur relative)² × amplitude (0,45 m à la cime par 60 km/h), autour d'une légère inclinaison, phase décalée par la position de l'instance, rafales qui augmentent amplitude et fréquence ; `foliage_tint` neutre pour P18 ; vent propre au matériau (`use_local_wind`) pour l'herbe. Les quatre paramètres globaux sont déclarés dans `project.godot` (`[shader_globals]`) : les déclarer au lancement passe par une fonction réservée à l'éditeur, qui échoue dans le jeu.
- **`tree_renderer.gd`** : `set_preset(preset, living_enabled)` choisit le shader sur les deux LOD quand `living(preset).tree_sway` est vrai (le LOD 1 en copie `cull_disabled`, amplitude × 0,6), sinon les `StandardMaterial3D` d'origine ; `apply_wind(eval)` met à jour les quatre paramètres en un appel par image (à brancher par P16).
- **`grass_tufts.gd`** : nœud autonome, tronçons de 40 m (1 derrière, 6 devant), bande de 2 à 15 m du bord de la route, exclusions par polygones (bâtiments, eau), densité réduite avec la pente (`height_at`), remplissage étalé sur plusieurs images (120 places par image au plus, route échantillonnée une fois par tronçon), 0 touffe en `low`.
- **Tests** : `test_grass_tufts.gd` (16 vérifications, dont 0,07 ms par image pour 12 000 touffes avec le vent) ; `test_tree_sway_render.gd` (4, sous Xvfb). Les matériaux sont vérifiés dans `test_grass_tufts.gd`, ce qui laisse `test_tree_renderer.gd` inchangé pour O1.
- **Reste sur le PC (le propriétaire, avec P16)** : 10 min en `low` avec vent de 25 km/h, arbres sans clignotement, plus de 55 images/s.
