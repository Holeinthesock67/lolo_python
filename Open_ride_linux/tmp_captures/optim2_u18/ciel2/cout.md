# Coût des effets de rendu (biome farmland, 60 km/h, socle propose)

Gain = GPU médian de `base` moins celui de la variante (positif : la variante coûte moins).
Avec des répétitions, chaque chiffre est la médiane des répétitions (détail dans cout.json).

## low (budget GPU 6 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 5.25 | 0 | 54.31 | 16.67 | 1.35 | 556434 | 215.5 |
| ciel_allege | les trois allègements du ciel ensemble | 4.85 | 0.4 | 59.47 | 16.67 | 0 | 551064 | 213 |
| ciel_rayon_sans_nuages | nuages absents de la lumière ambiante du ciel (fond inchangé) | 5.14 | 0.11 | 57.6 | 20.95 | 0 | 543453 | 214 |
| ciel_demi_res | nuages du fond calculés en demi-résolution | 5.18 | 0.07 | 58.32 | 16.67 | 1.65 | 543798 | 213.5 |

## medium (budget GPU 12 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 9.98 | 0 | 59.69 | 16.67 | 0 | 1.1589e+06 | 286 |
| ciel_allege | les trois allègements du ciel ensemble | 9.59 | 0.39 | 59.76 | 16.67 | 0 | 1.14315e+06 | 284.75 |
| ciel_rayon_sans_nuages | nuages absents de la lumière ambiante du ciel (fond inchangé) | 9.71 | 0.27 | 59.74 | 16.67 | 0 | 1.15511e+06 | 286 |
| ciel_demi_res | nuages du fond calculés en demi-résolution | 9.84 | 0.14 | 59.92 | 16.67 | 0 | 1.15258e+06 | 284.5 |

## high (budget GPU 14 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 10.84 | 0 | 59.83 | 16.67 | 0 | 1.60058e+06 | 295.75 |
| ciel_allege | les trois allègements du ciel ensemble | 10.34 | 0.5 | 59.43 | 16.67 | 0 | 1.62254e+06 | 307.25 |
| ciel_rayon_sans_nuages | nuages absents de la lumière ambiante du ciel (fond inchangé) | 10.74 | 0.1 | 59.73 | 16.67 | 0 | 1.60147e+06 | 294 |
| ciel_demi_res | nuages du fond calculés en demi-résolution | 10.87 | -0.03 | 59.75 | 16.67 | 0 | 1.60068e+06 | 295.25 |

