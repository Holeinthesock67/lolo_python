# Coût des effets de rendu (biome farmland,temperate_forest,alpine, 60 km/h, socle : préréglage)

Gain = GPU médian de `base` moins celui de la variante (positif : la variante coûte moins).
Avec des répétitions, chaque chiffre est la médiane des répétitions (détail dans cout.json).

## low (budget GPU 6 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 7.5 | 0 | 59.96 | 16.67 | 0 | 712466 | 246.25 |
| vegetation_50 | moitié moins d'arbres (densité du préréglage × 0,5) | 7.13 | 0.37 | 60 | 16.67 | 0 | 730723 | 269.5 |
| passes | même réglage que base, temps GPU de chaque passe (passes.md) | 7.38 | 0.12 | 59.02 | 16.67 | 0 | 721350 | 249 |
| arbres_lod0_300m | arbres détaillés jusqu'à 300 m au lieu de 450 | 7.44 | 0.06 | 59.75 | 16.67 | 0 | 701509 | 238 |
| sans_ombres_arbres | arbres sans ombre portée | 7.45 | 0.05 | 59.75 | 16.67 | 0 | 664242 | 223.75 |
| sans_imposteurs | sans les forêts lointaines en imposteurs (lot Y5) | 7.47 | 0.03 | 59.67 | 16.67 | 0 | 700027 | 222.5 |
| sans_arbres | aucun arbre proche (borne du coût des arbres) | 7.89 | -0.39 | 59.76 | 16.67 | 0 | 543717 | 143 |

## medium (budget GPU 12 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 12.99 | 0 | 59.5 | 16.67 | 0.6 | 1.79684e+06 | 359.25 |
| sans_ombres_arbres | arbres sans ombre portée | 12.2 | 0.79 | 59.75 | 16.67 | 1.05 | 1.61074e+06 | 304.5 |
| vegetation_50 | moitié moins d'arbres (densité du préréglage × 0,5) | 12.39 | 0.6 | 59.5 | 16.67 | 0.2 | 1.63793e+06 | 363 |
| arbres_lod0_300m | arbres détaillés jusqu'à 300 m au lieu de 450 | 12.57 | 0.42 | 59.75 | 16.67 | 1.2 | 1.7039e+06 | 339 |
| sans_imposteurs | sans les forêts lointaines en imposteurs (lot Y5) | 12.91 | 0.08 | 59.67 | 16.67 | 1.2 | 1.78924e+06 | 327 |
| passes | même réglage que base, temps GPU de chaque passe (passes.md) | 13.51 | -0.52 | 59.87 | 16.67 | 2.2 | 1.83658e+06 | 364 |
| sans_arbres | aucun arbre proche (borne du coût des arbres) | 13.59 | -0.6 | 59.75 | 16.67 | 1.7 | 1.10887e+06 | 195.5 |

## high (budget GPU 14 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 16.01 | 0 | 58.12 | 18.75 | 48 | 3.10115e+06 | 416.5 |
| sans_ombres_arbres | arbres sans ombre portée | 14.74 | 1.27 | 59.25 | 17.37 | 25 | 2.48231e+06 | 359.5 |
| vegetation_50 | moitié moins d'arbres (densité du préréglage × 0,5) | 14.99 | 1.02 | 59.41 | 17.37 | 26.45 | 2.40071e+06 | 406.5 |
| arbres_lod0_300m | arbres détaillés jusqu'à 300 m au lieu de 450 | 15.17 | 0.84 | 59.74 | 16.67 | 32.65 | 2.67381e+06 | 389 |
| passes | même réglage que base, temps GPU de chaque passe (passes.md) | 15.91 | 0.1 | 58.51 | 18.06 | 46.5 | 3.61745e+06 | 410 |
| sans_imposteurs | sans les forêts lointaines en imposteurs (lot Y5) | 15.96 | 0.05 | 58.61 | 18.06 | 47.85 | 3.61466e+06 | 357.25 |
| sans_arbres | aucun arbre proche (borne du coût des arbres) | 16.18 | -0.17 | 58.66 | 18.7 | 62.35 | 1.68896e+06 | 228.75 |

## Par biome du tronçon

GPU médian en ms et, entre parenthèses, gain par rapport à `base` dans le même biome.

### low (budget GPU 6 ms)

| Variante | farmland | temperate_forest | alpine | frontières |
| --- | --- | --- | --- | --- |
| base | **7.80** | **7.07** | — | **7.49** |
| passes | 7.85 (-0.05) | 7.13 (-0.06) | — | 7.54 (-0.05) |
| sans_ombres_arbres | 7.70 (+0.10) | 6.89 (+0.18) | — | 7.39 (+0.10) |
| vegetation_50 | 7.72 (+0.08) | 6.97 (+0.10) | — | 7.21 (+0.28) |
| sans_arbres | 7.68 (+0.12) | 8.02 (-0.95) | — | 7.87 (-0.38) |
| sans_imposteurs | 7.69 (+0.11) | 7.12 (-0.05) | — | 7.42 (+0.07) |
| arbres_lod0_300m | 7.78 (+0.02) | 7.03 (+0.04) | — | 7.38 (+0.11) |

### medium (budget GPU 12 ms)

| Variante | farmland | temperate_forest | alpine | frontières |
| --- | --- | --- | --- | --- |
| base | **13.06** | **12.91** | — | **13.21** |
| passes | 13.46 (-0.40) | 13.61 (-0.70) | — | 13.65 (-0.44) |
| sans_ombres_arbres | 13.12 (-0.06) | 11.73 (+1.18) | — | 12.43 (+0.78) |
| vegetation_50 | 13.24 (-0.18) | 12.07 (+0.84) | — | 12.35 (+0.86) |
| sans_arbres | 13.43 (-0.37) | 13.88 (-0.97) | — | 13.47 (-0.26) |
| sans_imposteurs | 13.27 (-0.21) | 12.85 (+0.06) | — | 12.98 (+0.23) |
| arbres_lod0_300m | 13.06 (+0.00) | 12.40 (+0.51) | — | 12.46 (+0.75) |

### high (budget GPU 14 ms)

| Variante | farmland | temperate_forest | alpine | frontières |
| --- | --- | --- | --- | --- |
| base | **15.89** | **16.34** | — | **16.29** |
| passes | 15.72 (+0.17) | 16.16 (+0.18) | — | 16.22 (+0.07) |
| sans_ombres_arbres | 15.83 (+0.06) | 14.48 (+1.86) | — | 14.86 (+1.43) |
| vegetation_50 | 15.75 (+0.14) | 14.43 (+1.91) | — | 15.12 (+1.17) |
| sans_arbres | 15.93 (-0.04) | 16.62 (-0.28) | — | 16.15 (+0.14) |
| sans_imposteurs | 15.96 (-0.07) | 16.12 (+0.22) | — | 16.05 (+0.24) |
| arbres_lod0_300m | 15.75 (+0.14) | 15.09 (+1.25) | — | 15.00 (+1.29) |

