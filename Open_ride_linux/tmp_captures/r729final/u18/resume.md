# Recette U18, partie PC (7bt)

## low

Textures du sol (ligne [perf-rendu]) : 0 Mo

| Biome | s | i/s | p99 ms | GPU ms | GPU saturé % | VRAM Godot Mo | textures Mo | VRAM nvidia Mo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coast | 116 | 59.99 | 16.67 | 5.89 | 0 | 241.3 | 129.5 | 534 |
| mediterranean | 96 | 60 | 16.67 | 5.49 | 0 | 242.9 | 129.5 | 534 |
| temperate_grassland | 99 | 60 | 16.67 | 5.78 | 0 | 242.3 | 129.5 | 534 |
| farmland | 100 | 60 | 16.67 | 7.83 | 0 | 244.1 | 129.5 | 534 |
| temperate_forest | 95 | 60 | 16.67 | 7.27 | 0 | 243.1 | 129.5 | 534 |
| alpine | 98 | 60 | 16.67 | 6.89 | 0 | 242.3 | 130.4 | 533 |
| frontières | 65 | 59.56 | 16.67 | 6.33 | 0 | 242.5 | 129.5 | 534 |
| côte avec la mer (90 s) | 51 | 60 | 16.67 | 4.63 | 0 | 241.1 | 130.4 | 534 |

## medium

Textures du sol (ligne [perf-rendu]) : 0 Mo

| Biome | s | i/s | p99 ms | GPU ms | GPU saturé % | VRAM Godot Mo | textures Mo | VRAM nvidia Mo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coast | 120 | 59.03 | 16.67 | 10.59 | 0 | 322.9 | 201.2 | 790 |
| mediterranean | 106 | 60 | 16.67 | 9.41 | 0 | 325.2 | 201.2 | 790 |
| temperate_grassland | 107 | 60 | 16.67 | 11.16 | 0 | 325.9 | 201.2 | 790 |
| farmland | 106 | 59.94 | 17.47 | 14.18 | 3.8 | 329.2 | 201.2 | 790 |
| temperate_forest | 108 | 60 | 16.67 | 12.98 | 0 | 328.1 | 201.2 | 790 |
| alpine | 82 | 60 | 16.67 | 11.83 | 0 | 327.9 | 201.2 | 789 |
| frontières | 72 | 60 | 16.67 | 11.65 | 0 | 327.3 | 201.2 | 790 |
| côte avec la mer (90 s) | 55 | 59.51 | 16.67 | 7.9 | 0 | 321 | 202 | 800 |

## high

Textures du sol (ligne [perf-rendu]) : 0 Mo

| Biome | s | i/s | p99 ms | GPU ms | GPU saturé % | VRAM Godot Mo | textures Mo | VRAM nvidia Mo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coast | 116 | 60 | 16.67 | 13.73 | 5.2 | 329.7 | 205.4 | 798 |
| mediterranean | 95 | 60 | 16.67 | 13.63 | 0 | 333.2 | 205.4 | 798 |
| temperate_grassland | 98 | 60 | 16.67 | 13.73 | 4.1 | 333.4 | 205.4 | 798 |
| farmland | 99 | 57.81 | 22.29 | 16.52 | 65.7 | 338.6 | 205.4 | 805 |
| temperate_forest | 93 | 59.01 | 21.4 | 15.94 | 64.5 | 337.1 | 205.4 | 805 |
| alpine | 97 | 60 | 16.67 | 13.8 | 0 | 337.1 | 206.2 | 805 |
| frontières | 68 | 60 | 16.67 | 14.15 | 14.7 | 336.2 | 205.4 | 805 |
| côte avec la mer (90 s) | 55 | 59.78 | 16.67 | 9.73 | 0 | 327.6 | 206.3 | 790 |

## Critères

- [OK] U18 §5.1 low coast : 59.99 i/s, p99 16.67 ms (116 s)
- [OK] U18 §5.1 low mediterranean : 60.0 i/s, p99 16.67 ms (96 s)
- [OK] U18 §5.1 low temperate_grassland : 60.0 i/s, p99 16.67 ms (99 s)
- [OK] U18 §5.1 low farmland : 60.0 i/s, p99 16.67 ms (100 s)
- [OK] U18 §5.1 low temperate_forest : 60.0 i/s, p99 16.67 ms (95 s)
- [OK] U18 §5.1 low alpine : 60.0 i/s, p99 16.67 ms (98 s)
- [OK] U18 §5.2 textures du décor en high < 1 Go : 206 Mo
- [OK] budgets low coast : 59.99 i/s, p99 16.67, GPU 5.89 ms
- [OK] budgets low mediterranean : 60.0 i/s, p99 16.67, GPU 5.49 ms
- [OK] budgets low temperate_grassland : 60.0 i/s, p99 16.67, GPU 5.78 ms
- [ÉCHEC] budgets low farmland : 60.0 i/s, p99 16.67, GPU 7.83 ms
- [ÉCHEC] budgets low temperate_forest : 60.0 i/s, p99 16.67, GPU 7.27 ms
- [ÉCHEC] budgets low alpine : 60.0 i/s, p99 16.67, GPU 6.89 ms
- [OK] budgets medium coast : 59.03 i/s, p99 16.67, GPU 10.59 ms
- [OK] budgets medium mediterranean : 60.0 i/s, p99 16.67, GPU 9.41 ms
- [OK] budgets medium temperate_grassland : 60.0 i/s, p99 16.67, GPU 11.16 ms
- [ÉCHEC] budgets medium farmland : 59.94 i/s, p99 17.47, GPU 14.18 ms
- [ÉCHEC] budgets medium temperate_forest : 60.0 i/s, p99 16.67, GPU 12.98 ms
- [OK] budgets medium alpine : 60.0 i/s, p99 16.67, GPU 11.83 ms
- [OK] budgets high coast : 60.0 i/s, p99 16.67, GPU 13.73 ms
- [OK] budgets high mediterranean : 60.0 i/s, p99 16.67, GPU 13.63 ms
- [OK] budgets high temperate_grassland : 60.0 i/s, p99 16.67, GPU 13.73 ms
- [ÉCHEC] budgets high farmland : 57.81 i/s, p99 22.29, GPU 16.52 ms
- [ÉCHEC] budgets high temperate_forest : 59.01 i/s, p99 21.4, GPU 15.94 ms
- [OK] budgets high alpine : 60.0 i/s, p99 16.67, GPU 13.8 ms
- [À VOIR] U18 §5.3 aucune frontière droite entre biomes : à juger sur planche/ (propriétaire)
