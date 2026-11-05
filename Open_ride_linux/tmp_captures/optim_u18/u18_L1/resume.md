# Recette U18, partie PC (7bt)

## low

Textures du sol (ligne [perf-rendu]) : 0 Mo

| Biome | s | i/s | p99 ms | GPU ms | GPU saturé % | VRAM Godot Mo | textures Mo | VRAM nvidia Mo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coast | 115 | 60 | 16.67 | 6.07 | 0 | 241.3 | 126.2 | 534 |
| mediterranean | 95 | 60 | 16.67 | 5.71 | 0 | 242.7 | 126.2 | 534 |
| temperate_grassland | 98 | 60 | 16.67 | 6.04 | 0 | 242.4 | 126.2 | 534 |
| farmland | 100 | 60 | 16.67 | 7.92 | 0 | 243.5 | 126.2 | 533 |
| temperate_forest | 92 | 60 | 16.67 | 7.21 | 0 | 243 | 126.2 | 533 |
| alpine | 98 | 60 | 16.67 | 6.83 | 0 | 242.1 | 127.1 | 533 |
| frontières | 66 | 60 | 16.67 | 6.46 | 0 | 242.3 | 126.2 | 534 |
| côte avec la mer (90 s) | 57 | 60 | 16.67 | 4.84 | 0 | 240.5 | 127.1 | 534 |

## Critères

- [OK] U18 §5.1 low coast : 60.0 i/s, p99 16.67 ms (115 s)
- [OK] U18 §5.1 low mediterranean : 60.0 i/s, p99 16.67 ms (95 s)
- [OK] U18 §5.1 low temperate_grassland : 60.0 i/s, p99 16.67 ms (98 s)
- [OK] U18 §5.1 low farmland : 60.0 i/s, p99 16.67 ms (100 s)
- [OK] U18 §5.1 low temperate_forest : 60.0 i/s, p99 16.67 ms (92 s)
- [OK] U18 §5.1 low alpine : 60.0 i/s, p99 16.67 ms (98 s)
- [À VOIR] U18 §5.2 textures du décor en high < 1 Go : pas de mesure
- [ÉCHEC] budgets low coast : 60.0 i/s, p99 16.67, GPU 6.07 ms
- [OK] budgets low mediterranean : 60.0 i/s, p99 16.67, GPU 5.71 ms
- [ÉCHEC] budgets low temperate_grassland : 60.0 i/s, p99 16.67, GPU 6.04 ms
- [ÉCHEC] budgets low farmland : 60.0 i/s, p99 16.67, GPU 7.92 ms
- [ÉCHEC] budgets low temperate_forest : 60.0 i/s, p99 16.67, GPU 7.21 ms
- [ÉCHEC] budgets low alpine : 60.0 i/s, p99 16.67, GPU 6.83 ms
- [À VOIR] U18 §5.3 aucune frontière droite entre biomes : à juger sur planche/ (propriétaire)
