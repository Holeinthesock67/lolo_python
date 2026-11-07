# Coût des effets de rendu (biome farmland,temperate_forest,alpine, 60 km/h, socle : préréglage)

Gain = GPU médian de `base` moins celui de la variante (positif : la variante coûte moins).
Avec des répétitions, chaque chiffre est la médiane des répétitions (détail dans cout.json).

## low (budget GPU 8 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 7.92 | 0 | 59.56 | 16.67 | 0 | 770750 | 258.5 |
| sans_ombres_arbres | arbres sans ombre portée | 7.96 | -0.04 | 59.56 | 16.67 | 0 | 735378 | 244 |
| ombres_arbres_150 | ombre des arbres jusqu'à 150 m de la caméra | 7.96 | -0.04 | 59.59 | 16.67 | 0 | 743490 | 245 |
| ombres_arbres_100 | ombre des arbres jusqu'à 100 m de la caméra | 7.99 | -0.07 | 59.36 | 16.97 | 0 | 731039 | 246 |

## medium (budget GPU 12 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 13.75 | 0 | 59.53 | 16.67 | 7.05 | 2.01998e+06 | 371.25 |
| ombres_arbres_100 | ombre des arbres jusqu'à 100 m de la caméra | 13.07 | 0.68 | 59.75 | 16.67 | 5.2 | 2.00153e+06 | 338.75 |
| sans_ombres_arbres | arbres sans ombre portée | 13.08 | 0.67 | 59.75 | 16.67 | 5 | 1.90514e+06 | 320 |
| ombres_arbres_150 | ombre des arbres jusqu'à 150 m de la caméra | 13.3 | 0.45 | 59.59 | 16.67 | 6.3 | 2.00692e+06 | 342 |
| ombres_2_cascades | 2 cascades d'ombre au lieu de 4 | 13.48 | 0.27 | 59.27 | 16.67 | 5.4 | 1.83234e+06 | 333.75 |
| ombres_200m | ombres jusqu'à 200 m au lieu de 400 / 600 | 13.77 | -0.02 | 59.75 | 16.67 | 7.3 | 2.01428e+06 | 358.75 |

## high (budget GPU 14 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 17.35 | 0 | 54.43 | 20.29 | 72.9 | 2.97396e+06 | 430.75 |
| sans_ombres_arbres | arbres sans ombre portée | 15.84 | 1.51 | 57.95 | 18.21 | 47.75 | 2.90027e+06 | 373 |
| ombres_arbres_100 | ombre des arbres jusqu'à 100 m de la caméra | 16.11 | 1.24 | 57.82 | 19.04 | 57.9 | 3.06125e+06 | 386.75 |
| ombres_arbres_150 | ombre des arbres jusqu'à 150 m de la caméra | 16.27 | 1.08 | 57.83 | 19.09 | 58.85 | 3.10643e+06 | 386.75 |
| ombres_2_cascades | 2 cascades d'ombre au lieu de 4 | 16.56 | 0.79 | 57.05 | 21.9 | 62.5 | 2.96492e+06 | 387 |
| ombres_200m | ombres jusqu'à 200 m au lieu de 400 / 600 | 16.84 | 0.51 | 56.52 | 19.27 | 71.6 | 3.11252e+06 | 399 |

## Par biome du tronçon

GPU médian en ms et, entre parenthèses, gain par rapport à `base` dans le même biome.

### low (budget GPU 8 ms)

| Variante | farmland | temperate_forest | alpine | frontières |
| --- | --- | --- | --- | --- |
| base | **8.34** | 7.54 | — | 7.85 |
| sans_ombres_arbres | 8.37 (-0.03) | 7.34 (+0.20) | — | 7.96 (-0.11) |
| ombres_arbres_100 | 8.28 (+0.06) | 7.38 (+0.16) | — | 7.89 (-0.04) |
| ombres_arbres_150 | 8.27 (+0.07) | 7.37 (+0.17) | — | 7.96 (-0.11) |

### medium (budget GPU 12 ms)

| Variante | farmland | temperate_forest | alpine | frontières |
| --- | --- | --- | --- | --- |
| base | **14.20** | **13.71** | — | **13.90** |
| sans_ombres_arbres | 14.25 (-0.05) | 12.47 (+1.24) | — | 13.41 (+0.49) |
| ombres_arbres_100 | 14.33 (-0.13) | 12.66 (+1.05) | — | 13.34 (+0.56) |
| ombres_arbres_150 | 14.11 (+0.09) | 12.87 (+0.84) | — | 13.46 (+0.44) |
| ombres_2_cascades | 14.26 (-0.06) | 13.12 (+0.59) | — | 13.75 (+0.15) |
| ombres_200m | 14.30 (-0.10) | 13.62 (+0.09) | — | 14.04 (-0.14) |

### high (budget GPU 14 ms)

| Variante | farmland | temperate_forest | alpine | frontières |
| --- | --- | --- | --- | --- |
| base | **17.33** | **17.46** | — | **17.54** |
| sans_ombres_arbres | 17.25 (+0.08) | 15.17 (+2.29) | — | 16.00 (+1.54) |
| ombres_arbres_100 | 17.26 (+0.07) | 15.57 (+1.89) | — | 16.01 (+1.53) |
| ombres_arbres_150 | 17.24 (+0.09) | 15.82 (+1.64) | — | 16.27 (+1.27) |
| ombres_2_cascades | 17.20 (+0.13) | 16.33 (+1.13) | — | 16.49 (+1.05) |
| ombres_200m | 17.25 (+0.08) | 16.81 (+0.65) | — | 16.93 (+0.61) |

