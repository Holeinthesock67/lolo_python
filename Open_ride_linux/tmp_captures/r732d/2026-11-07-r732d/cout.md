# Coût des effets de rendu (biome farmland,temperate_forest,alpine, 60 km/h, socle : préréglage)

Gain = GPU médian de `base` moins celui de la variante (positif : la variante coûte moins).
Avec des répétitions, chaque chiffre est la médiane des répétitions (détail dans cout.json).

## low (budget GPU 8 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 7.85 | 0 | 59.75 | 16.67 | 0 | 728418 | 257.5 |
| ombres_arbres_100 | ombre des arbres jusqu'à 100 m de la caméra | 7.82 | 0.03 | 59.51 | 16.73 | 0 | 702367 | 246.5 |
| herbe_150m | herbe effacée à 150 m au lieu de 250 | 7.89 | -0.04 | 59.75 | 16.67 | 0 | 725994 | 254.75 |

## medium (budget GPU 12 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 13.66 | 0 | 59.75 | 16.67 | 2.5 | 1.8566e+06 | 372.5 |
| ombres_arbres_100_2c | ombre des arbres jusqu'à 100 m et 2 cascades d'ombre | 12.75 | 0.91 | 58.79 | 16.69 | 4.35 | 1.60485e+06 | 307 |
| ombres_arbres_100 | ombre des arbres jusqu'à 100 m de la caméra | 12.77 | 0.89 | 59.33 | 16.67 | 3.5 | 1.80339e+06 | 330 |
| herbe_150m | herbe effacée à 150 m au lieu de 250 | 13.58 | 0.08 | 58.77 | 16.93 | 4.6 | 1.85102e+06 | 372.5 |

## high (budget GPU 14 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 16.85 | 0 | 55.87 | 22.01 | 64.55 | 2.71307e+06 | 430.25 |
| ombres_arbres_100_2c | ombre des arbres jusqu'à 100 m et 2 cascades d'ombre | 15.44 | 1.41 | 57.56 | 18.39 | 37.5 | 2.53265e+06 | 366.5 |
| ombres_arbres_100 | ombre des arbres jusqu'à 100 m de la caméra | 15.57 | 1.28 | 57.88 | 18.5 | 40.85 | 2.68474e+06 | 388.5 |
| herbe_150m | herbe effacée à 150 m au lieu de 250 | 16.76 | 0.09 | 55.77 | 20.98 | 61.4 | 2.71806e+06 | 428.25 |

## Par biome du tronçon

GPU médian en ms et, entre parenthèses, gain par rapport à `base` dans le même biome.

### low (budget GPU 8 ms)

| Variante | farmland | temperate_forest | alpine | frontières |
| --- | --- | --- | --- | --- |
| base | **8.18** | 7.36 | — | 7.87 |
| ombres_arbres_100 | 8.18 (+0.00) | 7.23 (+0.13) | — | 7.88 (-0.01) |
| herbe_150m | 8.14 (+0.04) | 7.40 (-0.04) | — | 7.96 (-0.09) |

### medium (budget GPU 12 ms)

| Variante | farmland | temperate_forest | alpine | frontières |
| --- | --- | --- | --- | --- |
| base | **13.89** | **13.43** | — | **13.79** |
| ombres_arbres_100 | 13.90 (-0.01) | 12.32 (+1.11) | — | 12.89 (+0.90) |
| ombres_arbres_100_2c | 13.86 (+0.03) | 12.32 (+1.11) | — | 13.12 (+0.67) |
| herbe_150m | 13.94 (-0.05) | 13.54 (-0.11) | — | 13.71 (+0.08) |

### high (budget GPU 14 ms)

| Variante | farmland | temperate_forest | alpine | frontières |
| --- | --- | --- | --- | --- |
| base | **16.77** | **16.98** | — | **17.12** |
| ombres_arbres_100 | 16.73 (+0.04) | 15.26 (+1.72) | — | 15.73 (+1.39) |
| ombres_arbres_100_2c | 16.71 (+0.06) | 15.04 (+1.94) | — | 15.69 (+1.43) |
| herbe_150m | 16.69 (+0.08) | 16.91 (+0.07) | — | 16.94 (+0.18) |

