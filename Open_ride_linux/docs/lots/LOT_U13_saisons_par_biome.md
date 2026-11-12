# Lot U13 – Engine : calendriers de saisons par biome

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Engine : calendriers de saisons par biome (sèche et des pluies, polaire, aucune) | GDScript | U5, P18 | Petite | **En PR** (12 novembre, **version 3.0**, issue #343) ; branchement dans la scène (poids des biomes passés par `main.gd`) à faire quand `main.gd` sera libre |

## 1. Objectif

**Version 3.0.** Remplacer les quatre saisons uniformes de P18 par un calendrier propre à chaque biome : quatre saisons plus longues ou plus courtes (hiver de la taïga, été court de la toundra), été sec et jaune en méditerranéen et en steppe, saison sèche et saison des pluies en savane et en jungle, presque aucun changement au désert et en polaire ; hémisphère sud inversé.

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §4, `docs/lots/LOT_U1_contrat_biomes.md` §4.5 (`seasons`), `docs/lots/LOT_P18_saisons.md`, `docs/lots/LOT_U5_modele_biome_engine.md`.
2. Code : `engine/scripts/season_model.gd` (P18), `engine/scripts/biome_model.gd` (U5).

## 3. Prérequis

U5 et P18 livrés.

## 4. Travail demandé

- `season_model.gd` : `season_for_biome(biome_def, date, lat) -> {season, progress}` selon `calendar` :
  - `four` : saisons de P18, bornes de mois décalées par `seasons.offset_months` et `seasons.lengths` (par exemple hiver de 6 mois en taïga) ;
  - `wet_dry` : `dry` et `wet`, mois du thème ; inversés au sud de l'équateur ;
  - `polar` : `polar_day`, `polar_night` et deux transitions, alignés sur P7 ;
  - `none` : saison neutre toute l'année ;
  - `season` imposée par le thème : l'emporte comme en P18.
- `params` des nouvelles saisons : herbe jaunie (`dry`), feuillage dense et sombre (`wet`), sol détrempé (`wet`, rugosité plus faible), neige permanente (`polar`).
- `biome_model.params` appelle désormais ce calendrier ; un mélange de biomes mélange les paramètres de leurs saisons respectives.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/season_model.gd`, `engine/scripts/biome_model.gd`, `engine/tests/unit/test_season_model.gd`, `engine/tests/unit/test_biome_model.gd`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd` (U17), core, compilateur, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe.
2. 15 juillet, latitude 12° : `savanna` en `wet` ; même date, latitude −12° : `dry`.
3. 15 février, latitude 62° : `boreal_forest` en `winter` ; 15 mai : encore `winter` si l'hiver dure 6 mois.
4. `sand_desert` : même saison toute l'année.
5. Biome `temperate_grassland` : résultats identiques aux tests de P18.
6. Transitions : aucune variation de teinte de plus de 5 % entre deux valeurs de `progress` distantes de 0,01 (critère de P18).

## 8. Hors périmètre

Données climatiques réelles, neige qui s'accumule.

## Livraison

Branche `claude/project-thread-wsem0b`, PR du 12 novembre 2026 (en revue).

- `engine/scripts/season_model.gd` : `season_for_biome(biome_def, month, day, lat, theme)` -> `{season, progress, calendar}` ; `four` : l'été centré sur le 16 juillet, durées `durations_months`, décalage `offset_months` (3, 3, 3, 3 : saisons de P18 au jour près au nord, avancement à 0,011 près au sud) ; `wet_dry` : saison des pluies centrée sur le 16 août ; `polar` : nuit polaire, retour du soleil, jour polaire, départ du soleil, d'après la déclinaison de P7 (`daylight_model.gd`) à la latitude, au moins 75° ; `none` : saison neutre. `params` couvre toutes ces saisons (paliers `WET_DRY_KEYS` et `POLAR_KEYS`, aucune marche au pas de 0,01) ; nouveau paramètre `ground_wet` (sol détrempé) ; `blend(weights, params_by_biome)`.
- Été sec et jaune (méditerranéen 0,8, steppe 0,7) : clé facultative `summer_dry` de la section `seasons` du thème par défaut (permise par le schéma, `additionalProperties`), herbe jaunie au cœur de l'été, nulle à ses bords ; `SeasonModel.biome_state` réunit saison et paramètres d'un biome.
- `engine/scripts/biome_model.gd` : `set_season_date(month, day, lat, snowy)` et `clear_season()` ; `params(biome)` rend la saison du calendrier du biome et `season_params` ; `blend` mélange les `season_params` des biomes présents.
- `engine/scripts/sky_cycle.gd` : réglage « Saisons » `date` : saison de chaque biome selon son calendrier, mélangée par les poids `weights` (argument facultatif de `season_state` et `evaluate`) ; sans poids, biome par défaut du thème (prairie : paramètres de P18, rendu de P19 inchangé).
- Sol détrempé : paramètre global `season_ground_wet` (`project.godot`, 0 par défaut), sol plus sombre hors neige (`terrain_shade.gdshaderinc`) et rugosité plus faible (`terrain.gdshader`, `terrain_biomes.gdshader`).
- Tests : `test_season_model.gd`, `test_biome_model.gd`, `test_sky_cycle.gd`.

**Écart au critère 3 :** avec l'été centré sur le 16 juillet, un hiver de 6 mois à 62° va du 1er novembre au 30 avril ; le 15 mai est au printemps (débourrement de la taïga). Le test vérifie ces bornes, et qu'un hiver de 6 mois et demi couvre encore le 15 mai. Le thème par défaut donne à la taïga un hiver de 5 mois (novembre à mars).

**Reste :** passer les poids des biomes au point du cycliste (`biome_model.weights_at`) à `SkyCycle.evaluate` dans `main.gd` (quelques lignes, après les lots TT et R22 qui occupent `main.gd`) ; jusque-là, le réglage « Saisons » suit le calendrier du biome par défaut du thème. Banc low, medium, high et captures à valider à ce moment-là.
