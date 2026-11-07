# Temps GPU de chaque passe de rendu (Godot --gpu-profile, médiane après chauffe)

Mesuré avec la variante `passes` (mêmes réglages que `base`). L'option de profil coûte un peu de temps
GPU : comparer les passes entre elles, pas le total avec `base`.

## low (somme des passes 7.38 ms)

| Passe | ms | part |
| --- | --- | --- |
| Render Opaque Pass | 5.43 | 74 % |
| SMAA | 0.54 | 7 % |
| Setup Sky | 0.53 | 7 % |
| Render Depth Pre-Pass | 0.36 | 5 % |
| Tonemap | 0.19 | 3 % |
| Render Directional/SpotLight Shadows | 0.17 | 2 % |
| Setup Shadows | 0.06 | 1 % |
| Setup Sky Resolution Buffers | 0.05 | 1 % |

## medium (somme des passes 12.56 ms)

| Passe | ms | part |
| --- | --- | --- |
| Render Opaque Pass | 6.81 | 54 % |
| Render Depth Pre-Pass | 2.71 | 22 % |
| Setup Sky | 0.53 | 4 % |
| Glow | 0.49 | 4 % |
| Resolve | 0.40 | 3 % |
| Render Directional/SpotLight Shadows | 0.32 | 3 % |
| Process SSAO | 0.30 | 2 % |
| Resolve Depth Pre-Pass (MSAA) | 0.27 | 2 % |
| Tonemap | 0.25 | 2 % |
| Render Fog | 0.15 | 1 % |
| Setup Shadows | 0.06 | 0 % |
| Render CanvasItems | 0.06 | 0 % |
| Setup Sky Resolution Buffers | 0.05 | 0 % |
| Prepare Depth for SSAO/SSIL | 0.05 | 0 % |

## high (somme des passes 14.99 ms)

| Passe | ms | part |
| --- | --- | --- |
| Render Opaque Pass | 8.05 | 54 % |
| Render Depth Pre-Pass | 3.31 | 22 % |
| Render Directional/SpotLight Shadows | 0.63 | 4 % |
| Setup Sky | 0.53 | 4 % |
| Glow | 0.48 | 3 % |
| Process SSAO | 0.43 | 3 % |
| Resolve | 0.39 | 3 % |
| Resolve Depth Pre-Pass (MSAA) | 0.26 | 2 % |
| Tonemap | 0.25 | 2 % |
| Render Fog | 0.23 | 2 % |
| Setup Sky Resolution Buffers | 0.09 | 1 % |
| Filter Fog | 0.07 | 0 % |
| Setup Shadows | 0.06 | 0 % |
| Prepare Depth for SSAO/SSIL | 0.06 | 0 % |
| Render CanvasItems | 0.05 | 0 % |

