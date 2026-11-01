# Lot U6 – Engine : shader de terrain multi-biome à tableaux de textures

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Engine : shader de terrain multi-biome à tableaux de textures, budget de mémoire vidéo | GDScript + shader | U5, P20 | Grande | Livré le 28 octobre (PR #485), **version 3.0** |

## 1. Objectif

**Version 3.0.** Remplacer, quand le parcours a une couche `biome`, le mélange herbe, roche et neige d'un seul thème par un mélange de 3 à 4 biomes par tuile, chacun avec ses couches de sol, en gardant la projection triplanaire pour la roche et le budget de la GTX 1060 (U-Q4).

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §6 et §7 (U-Q4), `docs/lots/LOT_U1_contrat_biomes.md` §4.5, `docs/lots/LOT_U5_modele_biome_engine.md`, `docs/lots/LOT_P20_packs_textures_performance.md` (niveaux, budget de mémoire vidéo).
2. Code : `engine/shaders/terrain.gdshader`, `engine/scripts/terrain_material.gd`, `engine/scripts/terrain_tiles.gd`, `engine/scripts/texture_levels.gd` (P20), `engine/scripts/quality_presets.gd`.

## 3. Prérequis

U5 livré ; P20 livré.

## 4. Travail demandé

- **Textures :** un `Texture2DArray` par sorte de carte pour tout le parcours : carte A (couleur + rugosité dans l'alpha) et carte B (normale XY + occlusion), compressées en mémoire vidéo, mipmaps ; une couche par sol utilisé par les biomes présents ; tailles par préréglage (`low` et `medium` 1 024 px, `high` 2 048 px) ; sol sans texture → couleur unie (couche 1 × 1).
- **Par tuile :** une petite texture de poids 17 × 17 (RGBA = poids des 4 biomes, filtrage linéaire) et un `uniform ivec4` des indices de biome ; en `low`, le quatrième canal est ignoré.
- **Shader :** pour chaque biome actif, mélange de ses couches de sol par la pente et l'altitude (règle de L3 étendue), roche en triplanaire, puis mélange des biomes par les poids, avec une modulation par bruit pour casser les fondus réguliers. Le chemin actuel (thème 1.x, sans couche `biome`) reste le même, au pixel près.
- **Budget :** estimation de la mémoire vidéo des tableaux (mipmaps compris) dans `texture_levels.gd` ; au-delà de 1 Go, descente d'un niveau puis couleurs unies, avec une ligne de journal.
- **Tests de rendu** sans écran (comme E2) : deux biomes en bandes, vérification des teintes moyennes de chaque bande et de la transition.

## 5. Fichiers concernés

- **Nouveaux :** `engine/shaders/terrain_biomes.gdshader`, `engine/scripts/biome_textures.gd`, `engine/tests/unit/test_biome_textures.gd`, `engine/tests/render/test_terrain_biomes_render.gd`.
- **Modifiés :** `engine/scripts/terrain_material.gd`, `engine/scripts/terrain_tiles.gd` (texture de poids par tuile), `engine/scripts/texture_levels.gd`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd` (U17), `terrain.gdshader` hors des `uniform` neutres, core, compilateur, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier, rendu compris.
2. Parcours sans couche `biome` : images de référence d'E2 identiques.
3. Deux biomes en bandes (prairie et méditerranéen) : teinte moyenne de chaque bande à moins de 5 % de la couleur du thème ; transition sans ligne droite visible (écart de teinte le long du bord de tuile inférieur à 3 %).
4. `low` : au plus 3 biomes échantillonnés (vérifié par une tuile à 4 biomes dont le plus faible a une couleur témoin absente de l'image).
5. Mémoire estimée d'un pack de 6 biomes à 2 048 px au-dessus de 1 Go : niveau 1 024 retenu, journal explicite.
6. Coût par image du shader mesuré au banc simulé (`engine/tests/sim_bench.py`) et noté dans la PR.

**Sur le PC cible (le propriétaire, à la recette U18) :** 55 images/s ou plus en `low`.

## 8. Hors périmètre

Détails de sol (U8), mer (U9), variantes (U14), sols déformés (le relief reste celui du MNT).

## Livraison

PR #485, fusionnée le 28 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Oui (tests de rendu), recette visuelle interne, **version 3.0** (issue #336) ».
