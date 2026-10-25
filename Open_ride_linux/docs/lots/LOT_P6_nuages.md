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
