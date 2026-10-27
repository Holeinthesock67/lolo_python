# Lot U10 – Engine : atmosphère par biome (brume de chaleur, humidité, lumière polaire)

## 1. Objectif

**Version 3.0.** Faire varier le ciel, le brouillard et la lumière selon le biome où roule le cycliste : brume de chaleur au désert, air lourd et lumière diffuse en jungle, lumière rasante et ciel pâle en polaire, ciel net en montagne.

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §2 et §6, `docs/lots/LOT_U1_contrat_biomes.md` §4.5 (`sky`), `docs/lots/LOT_U5_modele_biome_engine.md`, `docs/lots/LOT_P7_heure_soleil.md`, `docs/lots/LOT_P8_meteo_legere.md`.
2. Code : `engine/scripts/theme_render_params.gd`, `engine/scripts/daylight_model.gd` (P7), `engine/scripts/weather_model.gd` (P8).

## 3. Prérequis

U5 et P7 livrés.

## 4. Travail demandé

- `engine/scripts/atmosphere_model.gd` (modèle pur) : `params_at(weights, daylight, weather) -> Dictionary` : densité et couleur du brouillard, teinte de la lumière, intensité de la brume de chaleur, humidité ; moyenne glissante sur environ 500 m de route pour qu'un changement de biome se fasse en douceur ; la météo de P8 garde la priorité (pluie et brume l'emportent).
- Brume de chaleur : léger effet de distorsion en écran près de l'horizon, seulement en `sand_desert`, `rock_desert` et `savanna` l'après-midi, coupé en `low`.
- Lumière polaire : hauteur du soleil limitée et teinte froide au-delà de 66° de latitude (avec P7, qui gère déjà la nuit et le jour polaires).

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/atmosphere_model.gd`, `engine/shaders/heat_haze.gdshader`, `engine/tests/unit/test_atmosphere_model.gd`.
- **Modifiés :** `engine/scripts/theme_render_params.gd`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd` (U17), core, compilateur, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe.
2. Passage de `temperate_grassland` à `sand_desert` sur 1 km : densité de brouillard continue, aucune variation de plus de 2 % par 10 m.
3. Pluie de P8 en désert : la pluie l'emporte sur la brume de chaleur.
4. Préréglage `low` : brume de chaleur coupée.
5. Biome `temperate_grassland` : paramètres égaux à ceux d'aujourd'hui.

## 8. Hors périmètre

Ciel volumétrique, tempêtes de sable.
