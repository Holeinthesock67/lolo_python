# Coût des effets de rendu (biome farmland, 60 km/h, socle propose)

Gain = GPU médian de `base` moins celui de la variante (positif : la variante coûte moins).
Avec des répétitions, chaque chiffre est la médiane des répétitions (détail dans cout.json).

## low (budget GPU 6 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 5.15 | 0 | 57.05 | 16.67 | 0 | 544715 | 208 |
| sans_ombres_details | pierres et fleurs du sol sans ombre | 5.05 | 0.1 | 58.15 | 16.67 | 0 | 546223 | 208 |
| passes | même réglage que base, temps GPU de chaque passe (passes.md) | 5.12 | 0.03 | 58.27 | 16.67 | 0 | 544091 | 208 |

## medium (budget GPU 12 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 9.96 | 0 | 58.36 | 16.67 | 0 | 1.1951e+06 | 291.5 |
| ssao_low | occlusion ambiante basse | 9.62 | 0.34 | 58.11 | 16.67 | 1.6 | 1.17208e+06 | 290 |
| lod_maillage_2 | niveaux de détail des maillages comme en low | 9.64 | 0.32 | 59.06 | 16.67 | 0 | 1.20143e+06 | 291.25 |
| passes | même réglage que base, temps GPU de chaque passe (passes.md) | 9.83 | 0.13 | 58.26 | 16.67 | 0 | 1.16969e+06 | 281.5 |
| sans_ombres_details | pierres et fleurs du sol sans ombre | 9.83 | 0.13 | 59.3 | 16.67 | 0 | 1.18486e+06 | 291 |

## high (budget GPU 14 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 10.69 | 0 | 58.23 | 16.67 | 0 | 1.66357e+06 | 308 |
| ssao_low | occlusion ambiante basse | 10.76 | -0.07 | 58.92 | 16.67 | 0 | 1.62407e+06 | 304 |
| ssao_medium | occlusion ambiante medium au lieu de high | 10.9 | -0.21 | 58.83 | 16.68 | 0 | 1.66185e+06 | 297.5 |
| passes | même réglage que base, temps GPU de chaque passe (passes.md) | 11.05 | -0.36 | 58.7 | 16.67 | 0 | 1.66607e+06 | 298 |
| sans_ombres_details | pierres et fleurs du sol sans ombre | 11.1 | -0.41 | 57.48 | 16.67 | 0 | 1.69878e+06 | 299.5 |
| lod_maillage_1 | niveaux de détail des maillages comme en medium | 11.22 | -0.53 | 57.2 | 16.67 | 0 | 1.70423e+06 | 311.5 |
| brume_light | grille de brume volumétrique du medium | 11.26 | -0.57 | 56.68 | 16.67 | 0 | 1.61628e+06 | 287.5 |

