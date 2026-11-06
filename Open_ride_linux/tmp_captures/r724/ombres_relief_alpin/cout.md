# Coût des effets de rendu (biome alpine, 60 km/h, socle propose)

Gain = GPU médian de `base` moins celui de la variante (positif : la variante coûte moins).
Avec des répétitions, chaque chiffre est la médiane des répétitions (détail dans cout.json).

## low (budget GPU 6 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 6.92 | 0 | 59.52 | 16.67 | 0 | 650646 | 132 |
| sans_ombres_terrain | le relief ne porte aucune ombre (borne) | 6.87 | 0.05 | 59.76 | 16.7 | 0 | 361602 | 118 |
| ombres_terrain_proxy | relief simplifié dans les ombres (maille 40 m), tuiles lointaines sans ombre | 6.89 | 0.03 | 58.89 | 17.02 | 0 | 365188 | 124 |

## medium (budget GPU 12 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 12.54 | 0 | 59.67 | 16.67 | 4.05 | 1.57391e+06 | 185.5 |
| sans_ombres_terrain | le relief ne porte aucune ombre (borne) | 12.48 | 0.06 | 59.86 | 16.67 | 9.95 | 992922 | 154.5 |
| ombres_terrain_proxy | relief simplifié dans les ombres (maille 40 m), tuiles lointaines sans ombre | 12.6 | -0.06 | 58.58 | 17.37 | 9.75 | 1.01143e+06 | 169 |

## high (budget GPU 14 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 13.79 | 0 | 58.88 | 16.67 | 21.9 | 2.38766e+06 | 196.75 |
| sans_ombres_terrain | le relief ne porte aucune ombre (borne) | 13.5 | 0.29 | 58.92 | 16.68 | 28.75 | 1.80756e+06 | 168.25 |
| ombres_terrain_proxy | relief simplifié dans les ombres (maille 40 m), tuiles lointaines sans ombre | 13.57 | 0.22 | 58.83 | 16.67 | 17.35 | 1.83276e+06 | 182 |

