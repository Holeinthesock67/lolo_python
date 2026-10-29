# Lot U8 – Engine : détails de sol (dunes, rides de sable, rochers épars, herbes hautes)

## 1. Objectif

**Version 3.0.** Ajouter ce qui fait reconnaître un biome au premier coup d'œil, sans changer le relief du MNT : rides de sable et dunes par cartes de normales, rochers épars, herbes hautes de savane, touffes de steppe, termitières.

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §6, `docs/lots/LOT_U6_shader_terrain_multi_biome.md`, `docs/lots/LOT_U7_vegetation_par_biome.md`.
2. Code : `engine/shaders/terrain_biomes.gdshader` (U6), `engine/scripts/vegetation_placer.gd`, `engine/scripts/quality_presets.gd`.

## 3. Prérequis

U6 livré ; U7 utile (même placement déterministe).

## 4. Travail demandé

- **Dunes et rides :** normales procédurales dans le shader (bruit orienté selon une direction de vent fixe du thème, longueur d'onde 0,3 m pour les rides, 40 m pour les dunes), seulement là où `sand_desert` ou `coast` dominent ; aucune modification de géométrie.
- **Rochers épars :** `MultiMesh` de rochers construits par code (3 formes, teinte de la variante régionale), densité par biome (`alpine`, `rock_desert`, `tundra`, `volcanic`), jamais sur la route ni à moins de 3 m du bord.
- **Herbes hautes :** touffes en croix (deux quads) pour `savanna` et `steppe`, balancées par le vent (P5), dans les 60 m autour de la caméra ; termitières en `savanna`, à moins de 30 m de la route pour être vues (15, 30, 50 selon la qualité).
- Budgets par préréglage (`ground_details` dans `quality_presets.gd`), tout se coupe par `living(preset)`.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/ground_details.gd`, `engine/tests/unit/test_ground_details.gd`, `engine/tests/render/test_ground_details_render.gd`.
- **Modifiés :** `engine/shaders/terrain_biomes.gdshader`, `engine/scripts/quality_presets.gd`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd` (U17), core, compilateur, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Aucun rocher ni touffe à moins de 3 m du bord de la route (test sur un parcours de 5 km).
3. Rides absentes hors du sable (image de rendu d'un sol `temperate_grassland` identique avec et sans le lot).
4. Budgets respectés en `low`, `medium` et `high` ; coût par image mesuré au banc simulé et noté dans la PR.

## 8. Hors périmètre

Dunes en relief réel, sable qui vole (particules : extension possible de P8).
