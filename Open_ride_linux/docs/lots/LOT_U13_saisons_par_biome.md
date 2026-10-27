# Lot U13 – Engine : calendriers de saisons par biome

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
