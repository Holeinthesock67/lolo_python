# Recette U18, partie PC (7bt)

## low

Textures du sol (ligne [perf-rendu]) : 0 Mo

| Biome | s | i/s | p99 ms | GPU ms | GPU saturé % | VRAM Godot Mo | textures Mo | VRAM nvidia Mo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coast | 115 | 58.88 | 16.86 | 6.29 | 0 | 240.7 | 126.2 | 534 |
| mediterranean | 95 | 60 | 16.67 | 5.77 | 0 | 242.4 | 126.2 | 534 |
| temperate_grassland | 99 | 60 | 16.67 | 5.96 | 0 | 241.7 | 126.2 | 534 |
| farmland | 100 | 60 | 16.67 | 7.84 | 0 | 243.4 | 126.2 | 534 |
| temperate_forest | 94 | 60 | 16.67 | 7.28 | 0 | 242.5 | 126.2 | 533 |
| alpine | 97 | 60 | 16.67 | 6.75 | 0 | 241.6 | 127.1 | 533 |
| frontières | 65 | 60 | 16.67 | 6.46 | 0 | 241.8 | 126.2 | 534 |
| côte avec la mer (90 s) | 49 | 60 | 16.67 | 4.73 | 0 | 241.5 | 127.1 | 534 |

## medium

Textures du sol (ligne [perf-rendu]) : 0 Mo

| Biome | s | i/s | p99 ms | GPU ms | GPU saturé % | VRAM Godot Mo | textures Mo | VRAM nvidia Mo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coast | 117 | 60 | 16.67 | 14.34 | 7.7 | 443.7 | 325.3 | 790 |
| mediterranean | 96 | 60 | 16.67 | 13.27 | 2.1 | 445.8 | 325.3 | 790 |
| temperate_grassland | 99 | 60 | 16.67 | 14.95 | 26.3 | 446.7 | 325.3 | 790 |
| farmland | 100 | 53.28 | 20.01 | 18.24 | 83 | 449.8 | 325.3 | 790 |
| temperate_forest | 95 | 57.52 | 22.2 | 16.86 | 75.8 | 448.9 | 325.3 | 781 |
| alpine | 99 | 60 | 16.67 | 14.92 | 17.2 | 448.1 | 326.1 | 781 |
| frontières | 66 | 60 | 16.67 | 15.3 | 37.9 | 448.1 | 325.3 | 790 |
| côte avec la mer (90 s) | 56 | 60 | 16.67 | 11.44 | 0 | 442.4 | 326.2 | 791 |

## high

Textures du sol (ligne [perf-rendu]) : 0 Mo

| Biome | s | i/s | p99 ms | GPU ms | GPU saturé % | VRAM Godot Mo | textures Mo | VRAM nvidia Mo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coast | 117 | 50.57 | 20.83 | 18.6 | 76.9 | 451 | 329.5 | 799 |
| mediterranean | 96 | 54.77 | 22.27 | 17.57 | 79.2 | 454.5 | 329.5 | 799 |
| temperate_grassland | 99 | 54.47 | 19.89 | 17.8 | 87.9 | 454.6 | 329.5 | 798 |
| farmland | 100 | 47.35 | 24.9 | 20.44 | 79 | 459.9 | 329.5 | 798 |
| temperate_forest | 95 | 50.47 | 20.83 | 19.38 | 89.5 | 458.4 | 329.5 | 789 |
| alpine | 98 | 56 | 18.06 | 17.16 | 83.7 | 457.9 | 330.4 | 790 |
| frontières | 65 | 52.92 | 21.18 | 17.95 | 75.4 | 457.5 | 329.5 | 799 |
| côte avec la mer (90 s) | 56 | 59.8 | 16.67 | 13.92 | 5.4 | 448.4 | 330.4 | 791 |

## Critères

- [OK] U18 §5.1 low coast : 58.88 i/s, p99 16.86 ms (115 s)
- [OK] U18 §5.1 low mediterranean : 60.0 i/s, p99 16.67 ms (95 s)
- [OK] U18 §5.1 low temperate_grassland : 60.0 i/s, p99 16.67 ms (99 s)
- [OK] U18 §5.1 low farmland : 60.0 i/s, p99 16.67 ms (100 s)
- [OK] U18 §5.1 low temperate_forest : 60.0 i/s, p99 16.67 ms (94 s)
- [OK] U18 §5.1 low alpine : 60.0 i/s, p99 16.67 ms (97 s)
- [OK] U18 §5.2 textures du décor en high < 1 Go : 330 Mo
- [ÉCHEC] budgets low coast : 58.88 i/s, p99 16.86, GPU 6.29 ms
- [OK] budgets low mediterranean : 60.0 i/s, p99 16.67, GPU 5.77 ms
- [OK] budgets low temperate_grassland : 60.0 i/s, p99 16.67, GPU 5.96 ms
- [ÉCHEC] budgets low farmland : 60.0 i/s, p99 16.67, GPU 7.84 ms
- [ÉCHEC] budgets low temperate_forest : 60.0 i/s, p99 16.67, GPU 7.28 ms
- [ÉCHEC] budgets low alpine : 60.0 i/s, p99 16.67, GPU 6.75 ms
- [ÉCHEC] budgets medium coast : 60.0 i/s, p99 16.67, GPU 14.34 ms
- [ÉCHEC] budgets medium mediterranean : 60.0 i/s, p99 16.67, GPU 13.27 ms
- [ÉCHEC] budgets medium temperate_grassland : 60.0 i/s, p99 16.67, GPU 14.95 ms
- [ÉCHEC] budgets medium farmland : 53.28 i/s, p99 20.01, GPU 18.24 ms
- [ÉCHEC] budgets medium temperate_forest : 57.52 i/s, p99 22.2, GPU 16.86 ms
- [ÉCHEC] budgets medium alpine : 60.0 i/s, p99 16.67, GPU 14.92 ms
- [ÉCHEC] budgets high coast : 50.57 i/s, p99 20.83, GPU 18.6 ms
- [ÉCHEC] budgets high mediterranean : 54.77 i/s, p99 22.27, GPU 17.57 ms
- [ÉCHEC] budgets high temperate_grassland : 54.47 i/s, p99 19.89, GPU 17.8 ms
- [ÉCHEC] budgets high farmland : 47.35 i/s, p99 24.9, GPU 20.44 ms
- [ÉCHEC] budgets high temperate_forest : 50.47 i/s, p99 20.83, GPU 19.38 ms
- [ÉCHEC] budgets high alpine : 56.0 i/s, p99 18.06, GPU 17.16 ms
- [À VOIR] U18 §5.3 aucune frontière droite entre biomes : à juger sur planche/ (propriétaire)
