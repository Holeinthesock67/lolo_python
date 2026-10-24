# Lot L3 – Paramètres de rendu tirés du thème : terrain, route, ciel (sans affichage)

## 1. Objectif

Préparer E2 (shader triplanaire et thèmes) et le ciel d'E3 : convertir un thème chargé par `theme_loader.gd` (lot I5) en paramètres de rendu prêts à l'emploi, et écrire en GDScript la **fonction de référence** du mélange herbe / roche / neige du SRS §8.1. Le futur shader d'E2 reproduira cette fonction, et ses tests serviront de vecteurs de vérification. Aucun shader, aucun matériau, aucun nœud ici.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_I5_chargeur_themes_godot.md` (livraison).
2. `docs/SRS_v1.1.md` §8 et §8.1 (shader triplanaire), §10 (thèmes) ; `docs/contracts/world_format_v1.md` §9 ; `docs/contracts/world/theme.schema.json`.
3. Code : `engine/scripts/theme_loader.gd` (`load_theme`, `load_named`, `texture_for`), `engine/themes/default/theme.json`, `engine/tests/test_theme_loader.gd`.

## 3. Prérequis

Lot K1 livré.

## 4. Travail demandé

Nouveau `engine/scripts/theme_render_params.gd` (`extends RefCounted`, sans `class_name`), sans nœud :

- `terrain_uniforms(theme: Dictionary) -> Dictionary` : pour `grass`, `rock` et `snow`, la couleur (`Color`), l'inverse de l'échelle (`1.0 / scale_m`, répétitions par mètre) et le chemin de texture ou `null` ; `slope_threshold_deg` converti en cosinus (`cos_slope`), `snow_line_m`, `blend_sharpness`. Les noms des clés sont ceux des futurs `uniform` du shader et sont listés en tête du script.
- `blend_weights(normal: Vector3, altitude_m: float, params: Dictionary) -> Vector3` : poids (herbe, roche, neige), de somme 1, avec :
  - pente sous le seuil : herbe ; au-dessus : roche ; transition continue d'au plus ± 3° autour du seuil, d'autant plus franche que `blend_sharpness` est grand ;
  - neige au-dessus de `snow_line_m`, fondue sur 50 m, et pas sur la roche la plus raide (pente supérieure à 50°) ;
  - aucun `noise` dans cette fonction (le bruit de variation du shader est une décoration d'E2, hors vérification).
- `triplanar_weights(normal: Vector3, sharpness: float) -> Vector3` : poids des trois projections (YZ, XZ, XY), positifs, de somme 1.
- `road_params(theme)` (couleur, texture, largeur) et `sky_params(theme)` : direction du soleil (vecteur unitaire déduit de `sun_elevation_deg`, azimut constant documenté), densité du brouillard, valeurs par défaut quand le thème ne les donne pas.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/theme_render_params.gd`, `engine/tests/unit/test_theme_render_params.gd`.
- **Modifiés :** `engine/tests/README.md` (une ligne), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `theme_loader.gd` (lecture seule ; un défaut trouvé est signalé, pas corrigé ici), `main.gd`, scripts de rendu d'E1, `run_engine_tests.sh`.

## 6. Modifications de contrat autorisées

Aucune. L'azimut du soleil n'est pas dans le format §9 : constante du script, signalée dans le rapport comme candidate pour une future version du thème.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Thème par défaut : sol plat à 1 000 m → herbe ≥ 0,99 ; pente de 30° à 1 000 m → roche ≥ 0,99 ; sol plat à 2 400 m → neige ≥ 0,99 ; pente de 60° à 2 400 m → roche ≥ 0,99.
3. Continuité : le long d'une pente qui passe de 0 à 45° par pas de 0,5°, aucun poids ne saute de plus de 0,2 entre deux pas ; pareil en altitude de 2 100 à 2 300 m par pas de 1 m.
4. Pour 1 000 normales et altitudes tirées à graine fixe : chaque poids dans [0, 1], somme à 1 ± 1e-5 (pour `blend_weights` et `triplanar_weights`).
5. Un thème réduit à `{"version": "1.0"}` donne les valeurs par défaut du thème de référence ; un seuil de pente de 30° dans le thème déplace la transition à 30°.
6. `sky_params` : vecteur du soleil unitaire, d'élévation égale à `sun_elevation_deg` à 0,01° près.

## 8. Hors périmètre

- Shader `.gdshader`, matériaux, environnement Godot, textures (E2, E3).
- Bruit de variation de l'herbe et facettes de la roche (E2).
