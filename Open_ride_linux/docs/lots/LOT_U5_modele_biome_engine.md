# Lot U5 – Engine : modèle de biome sans affichage (poids, transitions, saison, variante)

## 1. Objectif

**Version 3.0.** Un modèle pur, sans nœud ni affichage, qui répond pour tout point du monde : quels biomes, avec quels poids, et quels paramètres de rendu (sol, végétation, eau, ciel, sons, faune) pour la saison et la variante du moment. Tous les lots de rendu U6 à U14 s'appuient sur lui.

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §4 et §6, `docs/lots/LOT_U1_contrat_biomes.md` §4.1, §4.3, §4.5 et §4.6.
2. Code : `engine/scripts/theme_loader.gd`, `engine/scripts/theme_render_params.gd`, `engine/scripts/terrain_tiles.gd`, `engine/scripts/season_model.gd` (P18), `engine/scripts/quality_presets.gd`.

## 3. Prérequis

U1 et P18 livrés ; U19 utile pour les données de test.

## 4. Travail demandé

- `engine/scripts/biome_layer.gd` : lecture des tuiles `biome/near` et `biome/far` (JSON), validation légère, cache par tuile ; tuile absente → biome par défaut.
- `engine/scripts/biome_model.gd` (`extends RefCounted`) :
  - `weights_at(x, z) -> Dictionary` : interpolation bilinéaire dans la grille 17 × 17, somme ramenée à 1 ;
  - `top_biomes(ix, iz, max_n)` : les `max_n` biomes les plus forts d'une tuile (3 en `low`, 4 sinon, d'après `quality_presets.gd`), renormalisés ;
  - forçage : `config.biome` de `hello_ack` (IPC 1.6) autre que `auto` remplace tous les poids ;
  - `params(biome, season, progress, variant) -> Dictionary` : paramètres tirés du thème 2.0 (ou du thème 1.x pour `temperate_grassland` et pour tout biome absent), mélangés par la saison (calendrier du biome : rôle de U13 ; ici, appel à `season_model.gd` pour `four` et valeurs neutres pour les autres) ;
  - `blend(weights, params_list)` : mélange numérique des couleurs et des densités pour un point.
- Thème 2.0 dans `theme_loader.gd` : lecture de `biomes`, `variants` et `surfaces`, repli sur les clés 1.x ; erreurs de thème signalées sans arrêter la séance.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/biome_layer.gd`, `engine/scripts/biome_model.gd`, `engine/tests/unit/test_biome_layer.gd`, `engine/tests/unit/test_biome_model.gd`.
- **Modifiés :** `engine/scripts/theme_loader.gd`, `engine/scripts/quality_presets.gd` (clé `max_biomes`), `engine/tests/unit/test_theme_loader.gd`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd` (U17), shaders, core, compilateur, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe.
2. Tuile à deux biomes 50/50 en dégradé : poids continus, aucune marche de plus de 2 % entre deux points distants de 1 m, y compris à travers un bord de tuile.
3. `top_biomes` en `low` sur une tuile à 4 biomes : 3 biomes, somme 1.
4. Forçage `savanna` : poids 1 en `savanna` partout.
5. Thème 1.x seul : `params("temperate_grassland", "summer", …)` égal aux paramètres de `theme_render_params.gd` actuels ; tout autre biome prend les mêmes valeurs.
6. Parcours sans couche `biome` : modèle muet, rendu inchangé (tests existants inchangés).
7. `weights_at` coûte moins de 5 µs par appel (mesuré dans le test, seuil indicatif).

## 8. Hors périmètre

Shader (U6), espèces (U7), calendriers propres aux biomes (U13).
