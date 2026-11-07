# Coût des effets de rendu (biome farmland,temperate_forest,alpine, 60 km/h, socle : préréglage)

Gain = GPU médian de `base` moins celui de la variante (positif : la variante coûte moins).
Avec des répétitions, chaque chiffre est la médiane des répétitions (détail dans cout.json).

## low (budget GPU 6 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 8.04 | 0 | 59.73 | 16.67 | 0 | 773402 | 257 |
| sans_ombres | aucune ombre portée (borne du coût des ombres) | 7.29 | 0.75 | 59.25 | 16.7 | 0 | 499390 | 226.5 |
| herbe_50 | moitié des touffes d'herbe | 7.78 | 0.26 | 59.75 | 16.67 | 0 | 704419 | 256 |
| ombres_arbres_100 | ombre des arbres jusqu'à 100 m de la caméra | 7.91 | 0.13 | 60 | 16.67 | 0 | 757832 | 252 |
| sans_ombres_arbres | arbres sans ombre portée | 7.92 | 0.12 | 59.56 | 16.67 | 0.2 | 718664 | 239.5 |
| ombres_arbres_150 | ombre des arbres jusqu'à 150 m de la caméra | 7.92 | 0.12 | 60 | 16.67 | 0 | 758361 | 250.25 |
| ombres_arbres_250 | ombre des arbres jusqu'à 250 m de la caméra | 7.99 | 0.05 | 59.95 | 16.67 | 0 | 759248 | 256.75 |

## medium (budget GPU 12 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 13.72 | 0 | 59.56 | 16.67 | 5.1 | 2.10439e+06 | 368.25 |
| sans_ombres | aucune ombre portée (borne du coût des ombres) | 12.23 | 1.49 | 59.78 | 16.67 | 0.8 | 1.42e+06 | 281.5 |
| sans_ombres_arbres | arbres sans ombre portée | 12.98 | 0.74 | 59.73 | 16.67 | 5.75 | 1.88801e+06 | 319 |
| herbe_50 | moitié des touffes d'herbe | 13.12 | 0.6 | 60 | 16.67 | 1 | 1.76888e+06 | 367.5 |
| ombres_arbres_100 | ombre des arbres jusqu'à 100 m de la caméra | 13.49 | 0.23 | 59.87 | 16.67 | 4.95 | 2.03067e+06 | 353 |
| ombres_arbres_150 | ombre des arbres jusqu'à 150 m de la caméra | 13.55 | 0.17 | 60 | 16.67 | 3.85 | 2.06641e+06 | 354 |
| ombres_arbres_250 | ombre des arbres jusqu'à 250 m de la caméra | 13.73 | -0.01 | 60 | 16.67 | 4.9 | 2.08188e+06 | 365 |

## high (budget GPU 14 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 17.06 | 0 | 56.11 | 19.76 | 74.6 | 4.01448e+06 | 420 |
| sans_ombres | aucune ombre portée (borne du coût des ombres) | 14.72 | 2.34 | 59.7 | 16.67 | 26.75 | 2.35765e+06 | 336.75 |
| sans_ombres_arbres | arbres sans ombre portée | 15.67 | 1.39 | 59.03 | 17.73 | 45.45 | 2.90677e+06 | 370.25 |
| herbe_50 | moitié des touffes d'herbe | 15.78 | 1.28 | 59.2 | 17.24 | 45.85 | 3.42356e+06 | 420.75 |
| ombres_arbres_100 | ombre des arbres jusqu'à 100 m de la caméra | 16.77 | 0.29 | 56.97 | 19.41 | 71.35 | 3.1442e+06 | 405.25 |
| ombres_arbres_150 | ombre des arbres jusqu'à 150 m de la caméra | 16.78 | 0.28 | 57.03 | 18.81 | 70.55 | 3.40777e+06 | 406 |
| ombres_arbres_250 | ombre des arbres jusqu'à 250 m de la caméra | 17.09 | -0.03 | 55.8 | 19.59 | 75 | 3.42489e+06 | 416.5 |

## Par biome du tronçon

GPU médian en ms et, entre parenthèses, gain par rapport à `base` dans le même biome.

### low (budget GPU 6 ms)

| Variante | farmland | temperate_forest | alpine | frontières |
| --- | --- | --- | --- | --- |
| base | **8.39** | **7.54** | — | **8.07** |
| sans_ombres | 7.71 (+0.68) | 6.67 (+0.87) | — | 7.29 (+0.78) |
| sans_ombres_arbres | 8.20 (+0.19) | 7.34 (+0.20) | — | 7.86 (+0.21) |
| ombres_arbres_100 | 8.25 (+0.14) | 7.44 (+0.10) | — | 7.90 (+0.17) |
| ombres_arbres_150 | 8.21 (+0.18) | 7.46 (+0.08) | — | 7.98 (+0.09) |
| ombres_arbres_250 | 8.23 (+0.16) | 7.58 (-0.04) | — | 7.94 (+0.13) |
| herbe_50 | 8.04 (+0.35) | 7.29 (+0.25) | — | 7.88 (+0.19) |

### medium (budget GPU 12 ms)

| Variante | farmland | temperate_forest | alpine | frontières |
| --- | --- | --- | --- | --- |
| base | **14.20** | **13.63** | — | **13.90** |
| sans_ombres | 13.38 (+0.82) | 11.68 (+1.95) | — | 12.46 (+1.44) |
| sans_ombres_arbres | 14.25 (-0.05) | 12.32 (+1.31) | — | 13.27 (+0.63) |
| ombres_arbres_100 | 14.24 (-0.04) | 13.29 (+0.34) | — | 13.73 (+0.17) |
| ombres_arbres_150 | 14.14 (+0.06) | 13.32 (+0.31) | — | 13.59 (+0.31) |
| ombres_arbres_250 | 14.21 (-0.01) | 13.62 (+0.01) | — | 13.82 (+0.08) |
| herbe_50 | 13.51 (+0.69) | 13.00 (+0.63) | — | 13.08 (+0.82) |

### high (budget GPU 14 ms)

| Variante | farmland | temperate_forest | alpine | frontières |
| --- | --- | --- | --- | --- |
| base | **17.23** | **17.11** | — | **17.19** |
| sans_ombres | 16.08 (+1.15) | 13.99 (+3.12) | — | 14.76 (+2.43) |
| sans_ombres_arbres | 17.21 (+0.02) | 14.98 (+2.13) | — | 15.71 (+1.48) |
| ombres_arbres_100 | 17.23 (+0.00) | 16.71 (+0.40) | — | 16.78 (+0.41) |
| ombres_arbres_150 | 17.23 (+0.00) | 16.77 (+0.34) | — | 16.66 (+0.53) |
| ombres_arbres_250 | 17.23 (+0.00) | 17.11 (+0.00) | — | 17.19 (+0.00) |
| herbe_50 | 15.99 (+1.24) | 15.82 (+1.29) | — | 15.99 (+1.20) |

