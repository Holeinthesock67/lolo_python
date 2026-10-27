# Lot U7 – Engine : végétation par biome (nouvelles espèces, densités, limites)

## 1. Objectif

**Version 3.0.** Peupler chaque biome de ses espèces : conifères, palmiers, acacias, baobabs, cactus, oliviers, cyprès, pins parasols, fougères arborescentes, roseaux, arbustes nains, vignes en rangs, avec les densités et les limites (limite des arbres, oasis) du thème 2.0.

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §2 et §6, `docs/lots/LOT_U1_contrat_biomes.md` §4.5 (`vegetation.species`), `docs/lots/LOT_U5_modele_biome_engine.md`, `docs/lots/LOT_K3_placement_vegetation.md`, `docs/lots/LOT_O1_preparation_arbres.md`.
2. Code : `engine/scripts/vegetation_placer.gd`, `engine/scripts/tree_renderer.gd`, `engine/shaders/tree_sway.gdshader` (P5, P18), `engine/scripts/quality_presets.gd` (budgets d'arbres).

## 3. Prérequis

U5 livré ; O1 livré (préparation des arbres sous 150 ms).

## 4. Travail demandé

- **Espèces construites par code** (aucun fichier externe), une fonction par espèce dans `engine/scripts/tree_species.gd` : tronc et houppier en peu de triangles (moins de 300 par arbre en `low`), variantes de taille et de teinte par graine ; `kind` parmi `oak`, `beech`, `spruce`, `pine`, `birch`, `larch`, `olive`, `holm_oak`, `cypress`, `stone_pine`, `palm`, `acacia`, `baobab`, `cactus`, `tree_fern`, `reed`, `dwarf_shrub`, `vine_row`.
- **Placement :** `vegetation_placer.gd` tire l'espèce en chaque point selon les poids de biome (`biome_model.gd`) puis les `weight` des espèces du biome ; densité = mélange des `max_density_per_ha` ; limite des arbres par biome ; rangs de vigne alignés sur la plus longue arête des zones `landuse=vineyard` ; palmiers seulement près de l'eau en désert (oasis).
- **Rendu :** un `MultiMesh` par espèce et par tuile, sous le budget d'arbres actuel de chaque préréglage (le total ne change pas) ; balancement par le shader de P5 ; saisons de P18 seulement pour les feuillus.
- Déterminisme : même graine, même forêt.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/tree_species.gd`, `engine/tests/unit/test_tree_species.gd`, `engine/tests/unit/test_vegetation_biomes.gd`, `engine/tests/render/test_species_render.gd`.
- **Modifiés :** `engine/scripts/vegetation_placer.gd`, `engine/scripts/tree_renderer.gd`, `engine/shaders/tree_sway.gdshader` (masque des espèces sans feuillage saisonnier), tests existants de ces scripts, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd` (U17), core, compilateur, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Chaque espèce : maillage valide, moins de 300 triangles dans sa forme `low`, boîte englobante plausible (cactus de 1 à 6 m, baobab de 8 à 20 m).
3. Tuile 100 % `mediterranean` : plus de 80 % d'oliviers, chênes verts, cyprès et pins parasols ; tuile `sand_desert` sans eau : aucun palmier ; avec un lac : palmiers à moins de 80 m de la rive seulement.
4. Parcours sans couche `biome` : placement identique à aujourd'hui (même liste d'arbres).
5. Nombre total d'instances jamais au-dessus du budget du préréglage ; temps de préparation d'une tuile sous 150 ms (seuil d'O1).

## 8. Hors périmètre

Herbes hautes et détails de sol (U8), faune (U12).
