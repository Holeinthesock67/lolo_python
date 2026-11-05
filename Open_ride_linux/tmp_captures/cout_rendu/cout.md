# Coût des effets de rendu (biome farmland, 60 km/h)

Gain = GPU médian de `base` moins celui de la variante (positif : la variante coûte moins).

## low (budget GPU 6 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 5.61 | 0 | 57.29 | 16.67 | 3.4 | 575243 | 223 |
| sans_ombres | aucune ombre portée (borne du coût des ombres) | 5.11 | 0.5 | 60 | 16.67 | 0 | 319503 | 190 |
| herbe_50 | moitié des touffes d'herbe | 5.34 | 0.27 | 58.43 | 19.05 | 0 | 541782 | 227 |
| sans_ombres_arbres | arbres sans ombre portée | 5.43 | 0.18 | 59.33 | 16.67 | 0 | 539415 | 209 |
| tri_visible | tri de ce que la caméra ne voit pas (lot S1) | 5.44 | 0.17 | 59.94 | 16.67 | 0 | 569042 | 227 |
| vegetation_50 | moitié moins d'arbres | 5.48 | 0.13 | 59.28 | 16.67 | 2.8 | 620276 | 232 |
| arbres_lod0_300m | arbres détaillés jusqu'à 300 m au lieu de 450 | 5.49 | 0.12 | 59.59 | 16.67 | 0 | 556849 | 224 |

## medium (budget GPU 12 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 13.23 | 0 | 58.04 | 16.67 | 0 | 1.32146e+06 | 294 |
| msaa0_smaa | sans MSAA (bords crénelés, sauf SMAA) | 9.92 | 3.31 | 60 | 16.67 | 0 | 1.33272e+06 | 297.5 |
| sans_ombres | aucune ombre portée (borne du coût des ombres) | 11.3 | 1.93 | 59.71 | 16.67 | 0 | 685356 | 207 |
| msaa2 | MSAA 2× au lieu de 4× | 11.39 | 1.84 | 59.86 | 16.67 | 0 | 1.33949e+06 | 296.5 |
| sans_ssil | sans lumière indirecte d'écran | 11.87 | 1.36 | 60 | 16.67 | 0 | 1.34288e+06 | 296.5 |
| sans_glow | sans halo | 11.99 | 1.24 | 60 | 16.67 | 0 | 1.34123e+06 | 297 |
| atlas_2048 | atlas des ombres 2048 au lieu de 4096 | 12.27 | 0.96 | 60 | 16.67 | 0 | 1.34253e+06 | 296.5 |
| herbe_50 | moitié des touffes d'herbe | 12.46 | 0.77 | 60 | 16.67 | 0 | 1.1929e+06 | 296 |
| sans_ssao | sans occlusion ambiante | 12.47 | 0.76 | 59.92 | 16.67 | 0 | 1.33854e+06 | 296 |
| filtre_low | bord des ombres moins doux | 12.65 | 0.58 | 59.72 | 16.67 | 0 | 1.33977e+06 | 296 |
| sans_brume | sans brume volumétrique | 12.69 | 0.54 | 59.62 | 16.67 | 0 | 1.32788e+06 | 295 |
| ssao_low | occlusion ambiante basse | 12.71 | 0.52 | 60 | 16.67 | 0 | 1.33443e+06 | 295.5 |
| sans_ombres_arbres | arbres sans ombre portée | 12.77 | 0.46 | 59.84 | 16.67 | 0 | 1.1199e+06 | 248.5 |
| arbres_lod0_300m | arbres détaillés jusqu'à 300 m au lieu de 450 | 12.79 | 0.44 | 59.41 | 16.67 | 0 | 1.22378e+06 | 278.5 |
| vegetation_50 | moitié moins d'arbres | 12.8 | 0.43 | 60 | 16.67 | 0 | 1.22954e+06 | 293 |
| ombres_2_cascades | 2 cascades d'ombre au lieu de 4 | 12.82 | 0.41 | 60 | 16.67 | 0 | 1.00397e+06 | 258 |
| ombres_200m | ombres jusqu'à 200 m au lieu de 400 / 600 | 12.82 | 0.41 | 60 | 16.67 | 0 | 1.29068e+06 | 284.5 |
| tri_visible | tri de ce que la caméra ne voit pas (lot S1) | 12.86 | 0.37 | 59.89 | 16.67 | 0 | 1.34142e+06 | 296 |
| brume_ambiante | brume éclairée par le ciel (montagnes sombres) | 12.95 | 0.28 | 60 | 16.67 | 0 | 1.33697e+06 | 296 |

## high (budget GPU 14 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 16.3 | 0 | 58.46 | 17.05 | 64.9 | 1.92744e+06 | 325 |
| msaa0_smaa | sans MSAA (bords crénelés, sauf SMAA) | 12.64 | 3.66 | 60 | 16.67 | 0 | 1.92803e+06 | 325 |
| sans_ombres | aucune ombre portée (borne du coût des ombres) | 14.01 | 2.29 | 59.48 | 16.67 | 2.8 | 1.19429e+06 | 233.5 |
| msaa2 | MSAA 2× au lieu de 4× | 14.63 | 1.67 | 59.98 | 16.67 | 13.5 | 1.8979e+06 | 322 |
| sans_ssil | sans lumière indirecte d'écran | 14.7 | 1.6 | 59.86 | 16.67 | 2.8 | 1.9221e+06 | 323 |
| sans_glow | sans halo | 15.32 | 0.98 | 59.67 | 16.67 | 27 | 1.92591e+06 | 323 |
| herbe_50 | moitié des touffes d'herbe | 15.34 | 0.96 | 59.83 | 16.67 | 32.4 | 1.56482e+06 | 323 |
| atlas_2048 | atlas des ombres 2048 au lieu de 4096 | 15.49 | 0.81 | 59.8 | 16.67 | 44.4 | 1.92132e+06 | 324 |
| sans_ssao | sans occlusion ambiante | 15.52 | 0.78 | 60 | 16.67 | 48.6 | 1.92591e+06 | 323 |
| sans_brume | sans brume volumétrique | 15.72 | 0.58 | 59.94 | 16.67 | 52.8 | 1.92167e+06 | 324 |
| sans_ombres_arbres | arbres sans ombre portée | 15.85 | 0.45 | 59.14 | 16.67 | 63.9 | 1.63711e+06 | 272.5 |
| filtre_low | bord des ombres moins doux | 15.86 | 0.44 | 59.34 | 16.67 | 52.8 | 1.93496e+06 | 328 |
| arbres_lod0_300m | arbres détaillés jusqu'à 300 m au lieu de 450 | 15.91 | 0.39 | 59.02 | 17.26 | 57.1 | 1.75978e+06 | 303 |
| ombres_2_cascades | 2 cascades d'ombre au lieu de 4 | 16 | 0.3 | 59.03 | 16.67 | 62.2 | 1.57348e+06 | 281 |
| ssao_low | occlusion ambiante basse | 16.02 | 0.28 | 59.04 | 16.67 | 63.9 | 1.93025e+06 | 325 |
| ombres_200m | ombres jusqu'à 200 m au lieu de 400 / 600 | 16.08 | 0.22 | 58.71 | 16.87 | 63.9 | 1.84076e+06 | 306 |
| tri_visible | tri de ce que la caméra ne voit pas (lot S1) | 16.16 | 0.14 | 59.02 | 16.67 | 59.5 | 1.92655e+06 | 323 |
| vegetation_50 | moitié moins d'arbres | 16.23 | 0.07 | 58.03 | 16.67 | 48.6 | 1.7404e+06 | 320 |
| brume_ambiante | brume éclairée par le ciel (montagnes sombres) | 16.26 | 0.04 | 58.3 | 17.4 | 61.1 | 1.92088e+06 | 324 |

