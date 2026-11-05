# Coût des effets de rendu (biome farmland, 60 km/h)

Gain = GPU médian de `base` moins celui de la variante (positif : la variante coûte moins).

## low (budget GPU 6 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 5.2 | 0 | 56.54 | 18.06 | 0 | 582003 | 219 |
| godot_gratuits | les quatre réglages Godot et la brume éclairée ensemble | 5.08 | 0.12 | 59.73 | 16.67 | 0 | 553685 | 216 |
| herbe_degrade | AJOUT : herbe au pied plus sombre, pointe plus claire | 5.08 | 0.12 | 59.77 | 16.67 | 0 | 553685 | 216.5 |
| soleil_brume | AJOUT : halo du soleil dans le brouillard (fog_sun_scatter) | 5.09 | 0.11 | 59.51 | 16.67 | 0 | 553685 | 216 |
| feuillage_simple | herbe et arbres en diffuse_lambert, sans reflets (G1) | 5.12 | 0.08 | 59.95 | 16.67 | 0 | 573195 | 214 |
| arbres_loin_simple | arbres lointains sans vent ni reflets (G3) | 5.16 | 0.04 | 59.06 | 16.67 | 0 | 560423 | 214 |
| embellis | AJOUT : les trois améliorations et la brume éclairée ensemble | 5.21 | -0.01 | 59.59 | 16.67 | 0 | 553685 | 216.5 |
| terrain_macro | AJOUT : prés plus ou moins mûrs à l'échelle de 600 m | 5.35 | -0.15 | 56.92 | 18.06 | 0 | 586781 | 216 |

## medium (budget GPU 12 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 11.88 | 0 | 59.69 | 16.67 | 0 | 1.16712e+06 | 285 |
| halo_3_niveaux | halo à 3 niveaux, agrandi en linéaire (G6) | 11.43 | 0.45 | 60 | 16.67 | 0 | 1.146e+06 | 285 |
| soleil_brume | AJOUT : halo du soleil dans le brouillard (fog_sun_scatter) | 11.68 | 0.2 | 59.84 | 16.67 | 0 | 1.16967e+06 | 288 |
| terrain_macro | AJOUT : prés plus ou moins mûrs à l'échelle de 600 m | 11.88 | 0 | 59.96 | 16.67 | 0 | 1.14687e+06 | 285.5 |
| feuillage_simple | herbe et arbres en diffuse_lambert, sans reflets (G1) | 11.89 | -0.01 | 59.64 | 16.67 | 0 | 1.12448e+06 | 285 |
| godot_gratuits | les quatre réglages Godot et la brume éclairée ensemble | 12.07 | -0.19 | 60 | 16.67 | 0 | 1.17222e+06 | 289 |
| embellis | AJOUT : les trois améliorations et la brume éclairée ensemble | 12.07 | -0.19 | 60 | 16.67 | 0 | 1.16969e+06 | 286.5 |
| herbe_degrade | AJOUT : herbe au pied plus sombre, pointe plus claire | 12.14 | -0.26 | 59.87 | 16.67 | 0 | 1.12404e+06 | 284 |
| arbres_loin_simple | arbres lointains sans vent ni reflets (G3) | 12.45 | -0.57 | 59.88 | 16.67 | 0 | 1.18896e+06 | 289 |

## high (budget GPU 14 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 14.2 | 0 | 59.61 | 16.67 | 16.7 | 1.72269e+06 | 308 |
| halo_3_niveaux | halo à 3 niveaux, agrandi en linéaire (G6) | 14.36 | -0.16 | 59 | 16.95 | 21.6 | 1.62387e+06 | 299 |
| godot_gratuits | les quatre réglages Godot et la brume éclairée ensemble | 14.48 | -0.28 | 59 | 16.67 | 16.2 | 1.61977e+06 | 301 |
| aniso_8 | filtrage anisotrope 8× au lieu de 16× (G5) | 14.49 | -0.29 | 58 | 17.24 | 16.7 | 1.62098e+06 | 297.5 |
| feuillage_simple | herbe et arbres en diffuse_lambert, sans reflets (G1) | 14.54 | -0.34 | 59.78 | 16.67 | 24.3 | 1.61977e+06 | 300 |
| herbe_degrade | AJOUT : herbe au pied plus sombre, pointe plus claire | 14.59 | -0.39 | 58 | 17.24 | 21.6 | 1.61895e+06 | 297 |
| terrain_macro | AJOUT : prés plus ou moins mûrs à l'échelle de 600 m | 14.77 | -0.57 | 57.88 | 18.06 | 35.1 | 1.61913e+06 | 297 |
| embellis | AJOUT : les trois améliorations et la brume éclairée ensemble | 14.77 | -0.57 | 58.67 | 16.67 | 21.6 | 1.623e+06 | 299 |
| arbres_loin_simple | arbres lointains sans vent ni reflets (G3) | 14.87 | -0.67 | 57.65 | 18.06 | 33.3 | 1.63696e+06 | 296.5 |
| soleil_brume | AJOUT : halo du soleil dans le brouillard (fog_sun_scatter) | 14.91 | -0.71 | 57.16 | 18.06 | 27.8 | 1.62975e+06 | 297 |

