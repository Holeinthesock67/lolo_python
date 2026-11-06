# Coût des effets de rendu (biome farmland, 60 km/h, socle propose)

Gain = GPU médian de `base` moins celui de la variante (positif : la variante coûte moins).
Avec des répétitions, chaque chiffre est la médiane des répétitions (détail dans cout.json).

## low (budget GPU 6 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 5.05 | 0 | 58.12 | 17.83 | 0 | 538252 | 208 |
| ciel_incremental | carte de rayonnement du ciel étalée sur plusieurs images | 4.92 | 0.13 | 56.45 | 19.52 | 0 | 538806 | 207.5 |
| ciel_128 | carte de rayonnement du ciel en 128 au lieu de 256 | 5.09 | -0.04 | 59.61 | 16.67 | 0 | 540182 | 208 |

## medium (budget GPU 12 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 9.9 | 0 | 59.31 | 16.68 | 0 | 1.1721e+06 | 289.5 |
| ciel_incremental | carte de rayonnement du ciel étalée sur plusieurs images | 9.42 | 0.48 | 59.95 | 16.67 | 0 | 1.12519e+06 | 285.5 |
| ciel_128 | carte de rayonnement du ciel en 128 au lieu de 256 | 9.7 | 0.2 | 60 | 16.67 | 0 | 1.15955e+06 | 287.25 |

## high (budget GPU 14 ms)

| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | préréglage tel quel | 10.71 | 0 | 59.75 | 16.67 | 0 | 1.62139e+06 | 299.75 |
| ciel_incremental | carte de rayonnement du ciel étalée sur plusieurs images | 10.53 | 0.18 | 59.98 | 16.67 | 0 | 1.61973e+06 | 301 |
| ciel_128 | carte de rayonnement du ciel en 128 au lieu de 256 | 10.77 | -0.06 | 59.7 | 16.67 | 0 | 1.61977e+06 | 300.5 |

