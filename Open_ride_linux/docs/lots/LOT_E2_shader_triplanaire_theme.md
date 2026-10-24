# Lot E2 – Shader triplanaire et application du thème (terrain, route, soleil)

## 1. Objectif

Remplacer les couleurs de sommet provisoires d'E1 par le shader triplanaire du SRS §8.1, piloté par le thème actif (lots I5 et L3) : herbe, roche et neige selon la pente et l'altitude, textures projetées en mètres sans UV. Appliquer aussi le thème à la route (couleur, texture, largeur) et à l'orientation du soleil. Changer de thème ne demande ni recompilation ni modification du `.world`.

Le cahier a été réécrit le 24 octobre après la revue critique de la PR #75 (constats R1 à R13 de la revue, PR #76) : ses critères prouvent maintenant le rendu par une vraie image, et non plus par la relecture des paramètres.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_L3_parametres_rendu_theme.md` (livraison), `docs/lots/LOT_I5_chargeur_themes_godot.md`, `docs/lots/LOT_E1_rendu_route_terrain.md`.
2. `docs/SRS_v1.1.md` §8 et §8.1 (shader triplanaire), §10 (thèmes) ; `docs/contracts/world_format_v1.md` §9 (thèmes : palettes, textures, shader triplanaire).
3. Code : `engine/scripts/theme_loader.gd`, `engine/scripts/theme_render_params.gd`, `engine/scripts/world_streamer.gd`, `engine/scripts/road_builder.gd`, `engine/scripts/terrain_tiles.gd`, `engine/scripts/main.gd`.

## 3. Prérequis

Lots E1, I5 et L3 livrés.

## 4. Travail demandé

### 4.1 Shader triplanaire du terrain (`engine/shaders/terrain.gdshader`)

- Shader spatial, sans UV : textures projetées depuis la position monde, `scale_m` du thème en mètres (inverse transmis en `*_inv_scale`).
- Poids des trois projections (YZ, XZ, XY) tirés de la normale monde, comme `ThemeRenderParams.triplanar_weights`.
- Poids herbe / roche / neige calculés **comme** `ThemeRenderParams.blend_weights` (L3) : herbe sous le seuil de pente, roche au-dessus, transition d'au plus ± 3° ; neige au-dessus de `snow_line_m`, fondue sur 50 m, absente sur la roche raide.
- **Aucune constante de L3 recopiée à la main** : la bande de fonte, les pentes de la neige raide et les bornes de la demi-bande sont des `uniform` remplis par `terrain_material.gd` depuis les constantes de `theme_render_params.gd`.
- Une couche de poids nul n'est pas échantillonnée (économie de lectures de texture) ; filtrage anisotrope des textures.
- Repli sur la couleur unie `color` quand la texture est absente ou `null` (format §9).

### 4.2 Création du matériau (`engine/scripts/terrain_material.gd`)

- `create_material(theme, theme_dir) -> ShaderMaterial` et `apply_to_material(mat, theme, theme_dir)` : uniforms tirés de `ThemeRenderParams.terrain_uniforms(theme)`, textures par `ThemeLoader.texture_for`.
- `theme_loader.gd` renvoie aussi `theme_dir`, le dossier du thème réellement chargé (y compris en cas de repli sur `default`), pour résoudre les textures relatives.

### 4.3 Route (`engine/scripts/road_builder.gd`)

- `make_material(road_color, road_texture)` : couleur ou texture du thème, **avec la ligne médiane d'E1 peinte par-dessus** (`road_image`). Avec les UV d'E1 (`v` = `s` / 6 m), une texture de route se répète tous les 6 m.
- `build_chunk_arrays(route, k, road_width_m)` : largeur `road.width_m` du thème, capturée dans chaque tâche de fond.

### 4.4 Intégration (`world_streamer.gd`, `main.gd`, `terrain_tiles.gd`)

- `WorldStreamer.set_theme(theme, theme_dir)` : matériaux de terrain et de route, largeur de route, couleur du sol plat ; remplace aussi les matériaux des maillages déjà affichés.
- `main.gd` charge le thème (`ThemeLoader.load_named` avec l'option `--theme` du lot L4) et oriente le soleil d'après `ThemeRenderParams.sky_params`.
- **Brouillard non modifié :** le brouillard en profondeur d'E1 masque la limite des tuiles lointaines ; `sky.fog_density` du thème est réservé au brouillard volumétrique du lot E3.
- **Préréglage de qualité inchangé (`low`) :** le branchement de `--quality` sur la table unique de L4 est fait dans E3.
- Les tuiles de terrain ne calculent plus de couleur de sommet (`ARRAY_COLOR`).

### 4.5 Tests

- `engine/tests/unit/test_terrain_material.gd` (sans écran) : uniforms du thème par défaut et d'un thème personnalisé, constantes de L3 transmises et déclarées dans le shader, aucune de ces constantes écrite en dur dans `fragment()`, textures, ligne médiane sur une texture de route, tuiles sans couleur de sommet.
- `engine/tests/render/test_terrain_render.gd` (vraie image) : en `--headless`, Godot ne compile aucun shader. Ce test rend un plan sous Xvfb avec l'OpenGL logiciel de Mesa (moteur Compatibility) et lit la couleur du pixel central. `run_engine_tests.sh` le lance quand `xvfb-run` existe ; l'intégration continue l'exige (`REQUIRE_RENDER=1`).

## 5. Fichiers concernés

- **Nouveaux :** `engine/shaders/terrain.gdshader`, `engine/scripts/terrain_material.gd`, `engine/tests/unit/test_terrain_material.gd`, `engine/tests/render/test_terrain_render.gd`, `docs/lots/LOT_E2_shader_triplanaire_theme.md`.
- **Modifiés :** `engine/scripts/theme_loader.gd`, `engine/scripts/road_builder.gd`, `engine/scripts/world_streamer.gd`, `engine/scripts/terrain_tiles.gd`, `engine/scripts/main.gd`, `engine/tests/run_engine_tests.sh`, `engine/tests/README.md`, `.github/workflows/openride.yml` (paquets Xvfb et Mesa, `REQUIRE_RENDER=1`), `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune. Respect strict de `theme.schema.json` et du format `.world` v1 §9.

## 7. Critères d'acceptation

**Automatiques (intégration continue) :**
1. Toutes les suites de `engine/tests/unit/` et `engine/tests/render/` passent, ainsi que le reste de `run_engine_tests.sh` et `pytest` dans `core/` et `compiler/`.
2. Les constantes de la fonction de référence de L3 sont transmises au shader et aucune n'est écrite en dur dans `fragment()`.
3. Vraie image rendue, thème par défaut : sol plat à 1 000 m en herbe, pente de 30° à 1 000 m en roche, sol plat à 2 400 m en neige, pente de 60° à 2 400 m en roche ; pente de 22°, sol plat à 2 225 m et pente de 47° à 2 400 m égaux au mélange de `blend_weights`, à 3/255 près. Un seuil de pente de 30° dans le thème garde une pente de 26° en herbe ; une texture d'herbe remplace la couleur de repli.
4. Ligne médiane présente sur une texture de route du thème ; tuiles sans couleur de sommet.

**Sur le PC cible (le propriétaire, GTX 1060, préréglage `low`) :**
5. Shader compilé sans erreur ni avertissement au lancement de la scène (moteur Forward+).
6. Démo puis trace réelle compilée : moyenne ≥ 55 images/s ; perte ≤ 10 % entre le thème sans texture et un thème de trois textures 2 048² ; limite du terrain lointain toujours invisible.
7. `--theme=<nom>` change les couleurs sans recompiler ni toucher au `.world`.

## 8. Hors périmètre

- Variation de l'herbe par bruit et facettes de la roche (SRS §8.1) : lot E3, §4.1.
- Ciel physique, brouillard volumétrique et préréglages de qualité : lot E3.
- Arbres (E3), bâtiments et plans d'eau (E4).

## 9. Livraison (24 octobre 2026, PR #75)

- Shader triplanaire, création du matériau, thème appliqué au terrain, à la route et au soleil (code initial de la PR #75).
- Corrections après la revue du 24 octobre (PR #76) : branche mise à jour sur `main` (conflit de `main.gd` avec la PR #73 résolu en gardant le HUD ERG et la fréquence cardiaque) ; écriture de `sky.fog_density` dans le brouillard de profondeur retirée ; `--quality` laissé à E3 ; fichiers hors périmètre (`launcher.py`, `test_launcher.py`, `test_ftms_spec.py`) rendus identiques à `main` ; constantes de L3 en `uniform` ; couches de poids nul non échantillonnées et filtrage anisotrope ; ligne médiane conservée sur une texture de route ; couleurs de sommet retirées des tuiles ; test de rendu réel sous Xvfb ajouté à `run_engine_tests.sh` et à l'intégration continue.
- Tests : `test_terrain_material` 48 vérifications, `test_terrain_render` 9 vérifications (rendu Mesa llvmpipe), suite complète de `run_engine_tests.sh` verte.
- **Écart constaté :** le moteur Compatibility mélange les couleurs en espace sRGB, Forward+ en espace linéaire ; les poids sont les mêmes, seules les teintes de transition diffèrent légèrement. Le test de rendu vérifie le cas Compatibility ; le cas Forward+ se voit à l'écran sur le PC cible (critère 5).
- **Préparation de l'essai (revue du 24 octobre après-midi) :** le brouillard de profondeur d'E1 gardait l'opacité par défaut de Godot (`fog_density` = 0,01), soit 1 % de brouillard à 12 km : la limite du terrain restait visible. Il est réglé à 1 (`render_quality.gd`, `main.tscn`), comme le prévoit le cahier E3 §4.2. Les textures du thème reçoivent leurs mipmaps au chargement (`theme_loader.gd`), sans quoi le filtrage anisotrope ne servait à rien. Thème d'essai à trois textures 2 048² : `engine/tests/make_texture_theme.py`.
- **Reste à faire par le propriétaire :** critères 5 à 7 sur le PC cible, selon [ESSAI_GRAPHIQUE_E2.md](../ESSAI_GRAPHIQUE_E2.md).
