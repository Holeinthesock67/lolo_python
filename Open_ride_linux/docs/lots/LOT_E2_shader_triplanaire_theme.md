# Lot E2 – Shader triplanaire et application du thème (terrain, route, ciel)

## 1. Objectif

Mettre en place le shader spatial triplanaire pour le terrain (`engine/shaders/terrain.gdshader`), raccorder les paramètres de thème (Lot I5 et Lot L3) au terrain, au ruban de route et aux paramètres de ciel/brouillard dans la scène principale (`engine/scripts/main.gd` et `engine/scripts/world_streamer.gd`), et valider l'instanciation et la compilation sans écran (`engine/tests/unit/test_terrain_material.gd`).

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_L3_parametres_rendu_theme.md` (livraison), `docs/lots/LOT_I5_chargeur_themes_godot.md`.
2. `docs/SRS_v1.1.md` §8 et §8.1 (Shader triplanaire), §10 (Thèmes) ; `docs/contracts/world_format_v1.md` §9 (Thèmes : palettes, textures, shader triplanaire).
3. Code : `engine/scripts/theme_loader.gd`, `engine/scripts/theme_render_params.gd`, `engine/scripts/world_streamer.gd`, `engine/scripts/road_builder.gd`, `engine/scripts/main.gd`.

## 3. Prérequis

Lots E1, I5 et L3 livrés.

## 4. Travail demandé

1. **Shader triplanaire du terrain (`engine/shaders/terrain.gdshader`)** :
   - Shader spatial (`shader_type spatial; render_mode ...;`) sans UVs sur le maillage, projetant les textures en mètres depuis les coordonnées du monde (`v_world_pos`).
   - Normales mondiales (`v_world_normal`) pour les poids triplanaires (`tri_weights`) selon les projections YZ, XZ, XY.
   - Uniforms : couleurs et inverses d'échelle (`grass_color`, `grass_inv_scale`, `rock_color`, `rock_inv_scale`, `snow_color`, `snow_inv_scale`), textures (`sampler2D`) avec drapeaux de présence (`has_grass_texture`, etc.), seuil de pente `slope_threshold_deg` (22° par défaut), altitude de neige `snow_line_m` (2 200 m par défaut), `blend_sharpness` (4.0 par défaut).
   - Calcul de pente et mélange herbe / roche / neige reproduisant exactement la fonction de référence `ThemeRenderParams.blend_weights` du Lot L3 :
     - herbe sous le seuil, roche au-dessus, lissée sur une bande d'au plus ± 3° ;
     - neige au-dessus de `snow_line_m`, fondue sur 50 m, absente sur roche raide (> 50°).
   - Repli propre sur couleur unie si la texture est absente ou non spécifiée.

2. **Créateur de matériau (`engine/scripts/terrain_material.gd`)** :
   - `create_material(theme: Dictionary = {}, theme_dir: String = "") -> ShaderMaterial` : instancie le shader et configure les uniforms depuis `ThemeRenderParams.terrain_uniforms(theme)` et `ThemeLoader.texture_for(theme, theme_dir, ...)`.
   - `apply_to_material(mat: ShaderMaterial, theme: Dictionary, theme_dir: String = "") -> void` : mise à jour dynamique.

3. **Application à la route (`engine/scripts/road_builder.gd`)** :
   - `make_material(road_color: Color, road_texture: Texture2D = null) -> StandardMaterial3D` : prend en compte la couleur et texture d'asphalte du thème.
   - `build_chunk_arrays(route, k: int, road_width_m: float = ROAD_WIDTH_M)` : largeur paramétrable issue du thème (`road.width_m`).

4. **Intégration dans le moteur (`world_streamer.gd` et `main.gd`)** :
   - `WorldStreamer.set_theme(theme_dict: Dictionary, theme_dir: String = "")` : applique le thème à `_terrain_material` (ShaderMaterial triplanaire), `_road_material`, `_road_width_m` et `_ground_color`.
   - `main.gd` : charge le thème via `ThemeLoader.load_named(cfg["theme"])`, le passe à `streamer.set_theme`, et oriente le soleil (`DirectionalLight3D`) et le brouillard d'après `ThemeRenderParams.sky_params(theme_dict)`.

5. **Tests sans écran (`engine/tests/unit/test_terrain_material.gd`)** :
   - Vérifications de l'instanciation, des uniforms par défaut, du thème personnalisé, du chargement avec texture réelle, de la mise à jour dynamique et de l'attachement à un maillage de rendu.

## 5. Fichiers concernés

- **Nouveaux :**
  - `engine/shaders/terrain.gdshader`
  - `engine/scripts/terrain_material.gd`
  - `engine/tests/unit/test_terrain_material.gd`
  - `docs/lots/LOT_E2_shader_triplanaire_theme.md`
- **Modifiés :**
  - `engine/scripts/theme_loader.gd` (renvoi de `theme_dir`)
  - `engine/scripts/road_builder.gd` (paramètres couleur, texture, largeur)
  - `engine/scripts/world_streamer.gd` (intégration `set_theme` et matériau shader terrain)
  - `engine/scripts/main.gd` (chargement du thème et application du ciel/soleil/brouillard)
  - `docs/lots/00_INDEX.md`
  - `docs/SUIVI_AVANCEMENT.md`

## 6. Modifications de contrat autorisées

Aucune. Respect strict du schéma `theme.schema.json` et du format .world v1 §9.

## 7. Critères d'acceptation

1. `engine/tests/unit/test_terrain_material.gd` passe sans écran dans Godot 4.3 (0 échec).
2. L'ensemble de la suite de tests unitaires Godot dans `engine/tests/unit/` (11 suites) passe avec 0 échec.
3. Les scènes principales et les tests de conformité documentaire `test_docs_coherence.py` et pytest core passent sans régression.
4. Le shader compile sans avertissement ni erreur dans Godot 4.3 headless.

## 8. Hors périmètre

- Bruit perlin/simplex de micro-variation décorative au sol (E3).
- Arbres et végétation procédurale (E3).
- Bâtiments et plans d'eau (E4).

## 9. Livraison (24 octobre 2026)

- `engine/shaders/terrain.gdshader` : shader triplanaire spatial pour le terrain avec projection en mètres et mélange continu herbe/roche/neige conforme à la spécification.
- `engine/scripts/terrain_material.gd` : utilitaire de construction et mise à jour de `ShaderMaterial` selon le thème.
- `engine/scripts/road_builder.gd` et `engine/scripts/world_streamer.gd` : route et terrain pilotés par les paramètres du thème.
- `engine/scripts/main.gd` : soleil (`DirectionalLight3D`) et brouillard orientés selon `sky_params`.
- `engine/tests/unit/test_terrain_material.gd` : 29 vérifications unitaires sans écran.
