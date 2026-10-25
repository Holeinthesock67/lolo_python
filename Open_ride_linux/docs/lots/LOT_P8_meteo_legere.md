# Lot P8 – Météo légère : brume de vallée, pluie, neige

## 1. Objectif

Ajouter quelques ambiances météo peu coûteuses, réglées par le thème 1.2 (`weather`) : brume dans les fonds de vallée, pluie fine ou neige légère autour de la caméra, chacune poussée par le vent du modèle P4. Le nombre de particules suit `living(preset).weather_particles`.

## 2. À lire

1. `docs/lots/00_INDEX.md` (budget de la série P), `docs/lots/LOT_P1_contrat_vent_decor.md` §4.4, `docs/lots/LOT_P4_modele_vent_engine.md`. Le lever de la brume avec l'heure et les feuilles d'automne viendront en 2.0 avec P7 et P18.
2. Code : `engine/scripts/render_quality.gd` (`apply_fog`, brouillard volumétrique en `high`), `engine/scripts/theme_render_params.gd`, `engine/scripts/quality_presets.gd`.

## 3. Prérequis

P4 livré. Version 1.0 publiée.

## 4. Travail demandé

- Nouveau modèle `engine/scripts/weather_model.gd` (`extends RefCounted`) :
  - `evaluate(weather, rider_alt_m, valley_alt_m, wind_eval, solar_hour = NAN) -> Dictionary` : `{fog_boost, fog_height_m, rain, snow, wetness}` ;
  - brume de vallée : intensité `morning_mist` du thème, constante en 1.x ; plus dense sous l'altitude moyenne du terrain proche (`valley_alt_m`, fournie par l'appelant) ; si `solar_hour` est donnée (P7, version 2.0), forte à l'aube et disparue vers 10 h ;
  - pluie et neige : intensité 0 à 1 du thème, jamais les deux à la fois (neige si le thème la demande, ou si l'altitude dépasse `snow_line_m` du thème) ;
  - `wetness` : assombrissement de la route sous la pluie (paramètre pour P17).
- Nouveau nœud `engine/scripts/weather_particles.gd` (`Node3D`) : un seul `GPUParticles3D` par effet, boîte de 40 m centrée sur la caméra qui la suit, gravité et vent, nombre borné par le budget (0 = nœud inactif).
- Ressources dessinées par code (aucune image externe).

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/weather_model.gd`, `engine/scripts/weather_particles.gd`, `engine/tests/unit/test_weather_model.gd`, `engine/tests/unit/test_weather_particles.gd`.
- **Modifiés :** `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, `render_quality.gd` (P17 applique `fog_boost`), le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Brume : plus forte à 200 m sous `valley_alt_m` qu'à 200 m au-dessus ; sans `solar_hour`, constante dans le temps ; avec `solar_hour`, maximale à 6 h et nulle à 11 h.
3. Pluie et neige jamais ensemble ; neige au-dessus de `snow_line_m` quand le thème demande de la pluie.
4. Particules : nombre jamais au-dessus du budget, nœud inactif à budget nul ; boîte toujours centrée sur la caméra à 1 m près après un déplacement de 500 m.
5. Vent du nord fort : vitesse latérale des particules dirigée vers le sud.
6. Thème sans `weather` : aucun effet, aucun nœud actif.

**Sur le PC cible (le propriétaire) :** séance en `low` avec pluie à 0,5 puis brume de vallée : perte de moins de 2 images/s (`[perf-rendu]`), pas de particules visibles « collées » à l'écran.

## 8. Hors périmètre

- Feuilles d'automne et effets de saison (P18, version 2.0), flaques, éclaboussures, gouttes sur l'écran, orage, accumulation de neige.
- Météo réelle (aucun réseau).
