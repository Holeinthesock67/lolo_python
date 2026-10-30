# Lot Y17 – Relief du gravier de la route par parallaxe (high)

**Statut : essai mesuré le 30 octobre.** La PR attend la mesure en définition native et l'accord du propriétaire sur les captures.

## 1. Objectif

Le propriétaire a posé la question le 29 octobre : « Parallax displacement ajouterait quelque chose en qualité ? ». Il a ensuite donné son accord pour un essai (« Ok pour un test »), puis pour aller jusqu'à la mesure des performances. Le grain de la route (gravillons, cailloux) n'avait jusque-là qu'un relief d'éclairage : sa normale venait du bruit procédural, comme du *bump mapping*. Vu de près et en angle rasant, le revêtement restait plat.

## 2. Règles

- **Seulement en high** : clé `parallax_steps` de `QualityPresets.IMAGE`, à 0 en low et en medium et à 12 en high. Avec 0, le shader suit exactement le chemin d'avant.
- **Un seul réglage global** `surface_parallax_steps` (`shader_globals` de `project.godot`), écrit par `render_quality.gd`. Il n'y a pas de matériau en plus.
- **Seulement là où il se voit** : le relief porte sur le grain fin et moyen et fait 12 mm de profondeur (`PARALLAX_DEPTH_M`). Il est complet jusqu'à 2,5 m (`PARALLAX_FULL_M`). Au-delà, la profondeur et le nombre de pas décroissent jusqu'à zéro à 6 m (`PARALLAX_MAX_M`), et la normale revient en fondu à celle d'avant. Plus loin, le shader ne fait aucun calcul de plus.
- **Pas de taches noires** : quand le point est décalé, la normale se recalcule par différences finies (5 mm) de la hauteur du grain, le long du repère de la route.

## 3. Contenu

- `road_markings.gdshader` :
  - `grain_height()` (hauteur du gravier) ;
  - `parallax()` (parallaxe par pas, au plus 32 pas, interpolation linéaire, angle rasant borné) ;
  - repère de la route tiré des dérivées d'écran, calculées hors des branches.
- `quality_presets.gd` et `render_quality.gd` : clé `parallax_steps` et réglage global.
- Tests :
  - `test_quality_presets` : la clé et sa valeur par préréglage ;
  - `test_road_markings_render` : en angle rasant, l'image change entre 0 et 12 pas, sans pixel noir ;
  - vue `route_rasante` ajoutée à `vitrine_rendu.gd`.

## 4. Mesures

| Mesure | low | medium | high |
| --- | --- | --- | --- |
| Cloud (lavapipe) | – | – | gravier en relief visible à 2–3 m (captures du 29 octobre) |
| PC GTX 1060, 720p (7ax, 30 octobre) | 57,8 i/s, GPU 5,14 ms | 57,8 i/s, GPU 7,72 ms | 57,6 i/s, GPU 11,98 ms |
| visual_check, PC | 594/594 | 596/596 | 596/596 |

En high, la vitrine compte 758 000 triangles et 17 appels de dessin sur `route_rasante`. Aucun défaut n'est visible.

**Mesure en 1680×1011 (7ay, 30 octobre, première version sans limite de distance)** : low 4,99 ms, medium 11,47 ms, high **18,79 ms** à 49 i/s. Le coût de +5,2 ms vient de la parallaxe calculée sur toute la route visible. Le critère n'était pas tenu, d'où la limite à 6 m ajoutée ensuite.

Il reste à mesurer la version limitée à 6 m en définition native (1680×1011) et en low, medium et high, pour comparer avec main en 4.7.2 (GPU en high : 13,61 ms). Le critère est un GPU en high ≤ 14 ms.
