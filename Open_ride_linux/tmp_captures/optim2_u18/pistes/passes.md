# Temps GPU de chaque passe de rendu (Godot --gpu-profile, médiane après chauffe)

Mesuré avec la variante `passes` (mêmes réglages que `base`). L'option de profil coûte un peu de temps
GPU : comparer les passes entre elles, pas le total avec `base`.

## low (somme des passes 5.26 ms)

| Passe | ms | part |
| --- | --- | --- |
| Render Opaque Pass | 3.07 | 58 % |
| Setup Sky | 0.77 | 15 % |
| SMAA | 0.47 | 9 % |
| Tonemap | 0.21 | 4 % |
| Render Depth Pre-Pass | 0.20 | 4 % |
| Render Sky | 0.18 | 3 % |
| Render Directional/SpotLight Shadows | 0.17 | 3 % |
| Setup Shadows | 0.09 | 2 % |
| Render CanvasItems | 0.07 | 1 % |

## medium (somme des passes 9.87 ms)

| Passe | ms | part |
| --- | --- | --- |
| Render Opaque Pass | 4.17 | 42 % |
| Render Depth Pre-Pass | 1.25 | 13 % |
| Process SSIL | 0.79 | 8 % |
| Setup Sky | 0.77 | 8 % |
| Glow | 0.51 | 5 % |
| Resolve | 0.39 | 4 % |
| Copy Final Framebuffer (SSIL/SSR) | 0.32 | 3 % |
| Process SSAO | 0.29 | 3 % |
| Resolve Depth Pre-Pass (MSAA) | 0.28 | 3 % |
| Tonemap | 0.27 | 3 % |
| Render Directional/SpotLight Shadows | 0.24 | 2 % |
| Render Fog | 0.14 | 1 % |
| Render Sky | 0.14 | 1 % |
| Render CanvasItems | 0.07 | 1 % |
| Setup Shadows | 0.06 | 1 % |
| Prepare Depth for SSAO/SSIL | 0.05 | 1 % |

## high (somme des passes 11.10 ms)

| Passe | ms | part |
| --- | --- | --- |
| Render Opaque Pass | 5.38 | 48 % |
| Render Depth Pre-Pass | 1.82 | 16 % |
| Setup Sky | 0.81 | 7 % |
| Glow | 0.52 | 5 % |
| Process SSAO | 0.43 | 4 % |
| Resolve | 0.40 | 4 % |
| Render Directional/SpotLight Shadows | 0.33 | 3 % |
| Tonemap | 0.27 | 2 % |
| Resolve Depth Pre-Pass (MSAA) | 0.27 | 2 % |
| Render Sky | 0.24 | 2 % |
| Render Fog | 0.23 | 2 % |
| Render CanvasItems | 0.12 | 1 % |
| Filter Fog | 0.07 | 1 % |
| Setup Shadows | 0.06 | 1 % |
| Prepare Depth for SSAO/SSIL | 0.06 | 1 % |

