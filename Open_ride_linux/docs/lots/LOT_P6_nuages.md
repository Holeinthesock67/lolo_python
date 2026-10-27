# Lot P6 – Nuages qui défilent

## 1. Objectif

Le ciel actuel est uni (ciel physique, ou ciel procédural en moteur Compatibility). Ce lot ajoute des nuages qui défilent dans le sens du vent (modèle P4), avec une couverture tirée du thème 1.2 (`sky.clouds`), et leur ombre douce sur le terrain en qualité haute. Coût visé : un seul passage de shader plein écran à l'horizon, sans volume.

## 2. À lire

1. `docs/lots/00_INDEX.md` (budget de la série P), `docs/lots/LOT_P1_contrat_vent_decor.md` §4.4, `docs/lots/LOT_P4_modele_vent_engine.md`, `docs/lots/LOT_E3_ciel_arbres_hud.md` (ciel physique, brouillard).
2. Code : `engine/scripts/main.gd` (`_apply_sky_params`, choix du ciel selon le moteur, en lecture seulement), `engine/scripts/theme_render_params.gd` (`sky_params`), `engine/scripts/render_quality.gd`, `engine/tests/render/test_terrain_render.gd`.

## 3. Prérequis

P4 livré. Version 1.0 publiée.

## 4. Travail demandé

- Nouveau shader de ciel `engine/shaders/sky_clouds.gdshader` (`shader_type sky`) :
  - dégradé du ciel repris des valeurs actuelles (zénith, horizon, soleil) pour que le ciel sans nuage reste celui d'aujourd'hui ;
  - nuages par bruit fractal 2D projeté sur un plan à `altitude_m`, couverture `coverage` (0 à 1), défilement `vent × speed_factor` ; fondu vers l'horizon pour cacher la répétition ;
  - `flat` : une couche ; `layered` : deux couches à vitesses différentes ;
  - mêmes paramètres globaux de vent que P5 ;
  - compatible avec le moteur Compatibility (tests sous Xvfb) et Forward+.
- `theme_render_params.gd` : `cloud_params(theme) -> Dictionary` (valeurs par défaut : couverture 0,3, facteur 1,0, blanc légèrement bleuté, 2 000 m), bornes contrôlées.
- Nouveau `engine/scripts/sky_clouds.gd` (`extends RefCounted`) : `build_material(params, quality) -> ShaderMaterial` et `update(material, wind_eval)` ; `clouds = "off"` rend le matériau actuel.
- Ombre des nuages (`high` seulement) : modulation de la lumière dans `terrain.gdshader` par le même bruit, désactivée en `low` et `medium` (aucun coût).

## 5. Fichiers concernés

- **Nouveaux :** `engine/shaders/sky_clouds.gdshader`, `engine/scripts/sky_clouds.gd`, `engine/tests/unit/test_sky_clouds.gd`, `engine/tests/render/test_sky_clouds_render.gd`.
- **Modifiés :** `engine/scripts/theme_render_params.gd` (une fonction), `engine/shaders/terrain.gdshader` (ombre, derrière un `uniform bool` faux par défaut), `engine/tests/unit/test_theme_render_params.gd`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd` (branchement par P16), la scène, le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier, rendu compris.
2. Rendu : couverture 0 : ciel identique au ciel actuel à 3/255 près ; couverture 0,6 : au moins 30 % de pixels clairs au-dessus de l'horizon ; deux images à 2 s d'écart avec vent : les nuages se sont déplacés dans le sens du vent (corrélation des deux images).
3. `cloud_params` : valeurs par défaut sans clé, bornes appliquées (couverture 1,7 ramenée à 1).
4. `clouds = "off"` : aucun changement d'image dans `engine/tests/run_visual_tests.sh`.
5. Ombre désactivée : `terrain.gdshader` rend exactement comme avant (test de rendu d'E2 inchangé).

**Sur le PC cible (le propriétaire) :** séance en `low`, couverture 0,5 : nuages sans motif répété visible, défilement fluide ; perte de moins de 1 image/s mesurée par `[perf-rendu]`.

## 8. Hors périmètre

- Nuages volumétriques, orage, éclairs, arc-en-ciel.
- Couleurs du coucher de soleil (P7, qui pilote les mêmes paramètres de couleur).

## 9. Livraison

Livré sur la branche `lot-p6-nuages` (issue #130), sans toucher à `main.gd`, à la scène, au core ni au contrat.

- **Shader** `engine/shaders/sky_clouds.gdshader` (`shader_type sky`) : reprend le dégradé du `ProceduralSkyMaterial` de Godot 4.3 (mêmes noms d'uniforms, mêmes valeurs par défaut, couleurs du ciel actuel), si bien qu'à couverture 0 l'image est celle d'aujourd'hui (écart mesuré : 0/255). Nuages : bruit fractal 2D (4 octaves en `flat`, 5 en `layered`) sur un plan à `altitude_m` au-dessus de la caméra, ancré au monde (la caméra passe dessous), fondu vers l'horizon ; `layered` ajoute une seconde couche plus haute, 1,6 fois plus rapide. Le disque solaire passe derrière les nuages. Les paramètres globaux du vent de P5 font évoluer la forme des nuages par vent fort.
- **Défilement** : `sky_clouds.gd` cumule côté CPU, à chaque `update(material, wind_eval, dt_s)`, le déplacement `vent × speed_factor` (uniform `cloud_offset`), pour que les nuages ne sautent pas quand la direction du vent change. Le troisième argument `dt_s` (1/60 s par défaut) s'ajoute à la signature du cahier.
- **`clouds = "off"`** (préréglage, ou décor vivant coupé) et couverture nulle : `build_material(params, quality, current)` rend `current`, le matériau de ciel en place, sans le changer (ciel physique en Forward+, ciel procédural en Compatibility) ; sans `current`, le ciel procédural actuel. Avec des nuages, les deux moteurs utilisent le dégradé procédural : en Forward+, le ciel physique d'aujourd'hui est remplacé (à vérifier sur le PC cible avec P16).
- **`cloud_params(theme)`** dans `theme_render_params.gd` : couverture 0 à 1 (0,3 par défaut), facteur de vitesse 0 à 5 (1,0), couleur `#f4f7fb` (blanc légèrement bleuté), altitude de 300 à 10 000 m (2 000 m). Le thème par défaut 1.2 donne 1 500 m et `#ffffff`.
- **Ombre des nuages** : dans `terrain.gdshader`, derrière `uniform bool cloud_shadow_enabled = false` (rendu d'E2 inchangé, `test_terrain_render` vert) ; même bruit et même défilement que la couche basse, projeté à la verticale, assombrissement de 35 % au plus. `sky_clouds.terrain_shadow_params(sky_material, quality)` donne les uniforms, actifs seulement en `layered` (préréglage `high`).
- **Pour P16** : appeler `build_material(cloud_params(theme), living(preset).clouds, env.sky.sky_material)` après le choix du ciel de `main.gd`, puis `update` à chaque image avec `wind_model.evaluate()`. Un matériau de ciel qui change à chaque image fait recalculer la carte de rayonnement : garder `Sky.process_mode` en `PROCESS_MODE_INCREMENTAL` ou `REALTIME` avec une petite `radiance_size`, et mesurer avec `[perf-rendu]`.
- **Tests** : `test_sky_clouds.gd` (14 vérifications, coût de `update` 0,002 ms par image), `test_sky_clouds_render.gd` (5 vérifications : couverture 0 identique au ciel actuel, 41 % de pixels clairs à 0,6, décalage de 7 pixels vers l'est par vent d'ouest avec une corrélation de 0,99, deux couches), `test_theme_render_params.gd` (5 vérifications de plus pour `cloud_params`).
- **Reste sur le PC cible (le propriétaire)** : séance en `low`, couverture 0,5, nuages sans motif répété visible et défilement fluide, perte de moins de 1 image/s par `[perf-rendu]` ; à faire avec P16, qui branche le ciel.

