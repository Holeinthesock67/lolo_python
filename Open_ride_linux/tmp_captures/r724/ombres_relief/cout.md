# Coût des effets de rendu (biome farmland, 60 km/h, socle propose)

Gain = GPU médian de `base` moins celui de la variante (positif : la variante coûte moins).
Avec des répétitions, chaque chiffre est la médiane des répétitions (détail dans cout.json).

## low (budget GPU 6 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 5.05 | 0 | 57.75 | 16.67 | 0 | 538806 | 208 |
| ombres_terrain_proxy | relief simplifié dans les ombres (maille 40 m), tuiles lointaines sans ombre | 4.96 | 0.09 | 59.79 | 16.68 | 0 | 304973 | 201.75 |
| sans_ombres_terrain | le relief ne porte aucune ombre (borne) | 4.96 | 0.09 | 59.93 | 16.67 | 0 | 296761 | 197.25 |

## medium (budget GPU 12 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 9.52 | 0 | 59.85 | 16.67 | 0 | 1.14581e+06 | 285.75 |
| sans_ombres_terrain | le relief ne porte aucune ombre (borne) | 9.48 | 0.04 | 59.83 | 16.67 | 0 | 711026 | 264.75 |
| ombres_terrain_proxy | relief simplifié dans les ombres (maille 40 m), tuiles lointaines sans ombre | 9.77 | -0.25 | 59.88 | 16.67 | 0 | 722840 | 276 |

## high (budget GPU 14 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 10.92 | 0 | 59.95 | 16.67 | 1.3 | 1.61936e+06 | 299 |
| ombres_terrain_proxy | relief simplifié dans les ombres (maille 40 m), tuiles lointaines sans ombre | 10.58 | 0.34 | 59.56 | 16.67 | 0 | 1.24359e+06 | 288 |
| sans_ombres_terrain | le relief ne porte aucune ombre (borne) | 10.77 | 0.15 | 58.74 | 16.67 | 0 | 1.22039e+06 | 275.25 |

