# Recette U18, partie PC (7bt)

## low

Textures du sol (ligne [perf-rendu]) : 0 Mo

| Biome | s | i/s | p99 ms | GPU ms | GPU saturé % | VRAM Godot Mo | textures Mo | VRAM nvidia Mo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coast | 115 | 60 | 16.67 | 6.16 | 0 | 240.7 | 126.2 | 534 |
| mediterranean | 95 | 59.54 | 16.67 | 5.76 | 0 | 242.2 | 126.2 | 534 |
| temperate_grassland | 99 | 58.51 | 31.94 | 6.03 | 0 | 241.9 | 126.2 | 534 |
| farmland | 100 | 60 | 16.67 | 8.04 | 0 | 243 | 126.2 | 533 |
| temperate_forest | 95 | 60 | 16.67 | 7.26 | 0 | 242.4 | 126.2 | 533 |
| alpine | 98 | 60 | 16.67 | 6.86 | 0 | 241.6 | 127.1 | 533 |
| frontières | 67 | 58.53 | 16.72 | 6.6 | 0 | 242 | 126.2 | 534 |
| côte avec la mer (90 s) | 53 | 58.38 | 16.67 | 4.72 | 0 | 240 | 127.1 | 534 |

## Critères

- [OK] U18 §5.1 low coast : 60.0 i/s, p99 16.67 ms (115 s)
- [OK] U18 §5.1 low mediterranean : 59.54 i/s, p99 16.67 ms (95 s)
- [ÉCHEC] U18 §5.1 low temperate_grassland : 58.51 i/s, p99 31.94 ms (99 s)
- [OK] U18 §5.1 low farmland : 60.0 i/s, p99 16.67 ms (100 s)
- [OK] U18 §5.1 low temperate_forest : 60.0 i/s, p99 16.67 ms (95 s)
- [OK] U18 §5.1 low alpine : 60.0 i/s, p99 16.67 ms (98 s)
- [À VOIR] U18 §5.2 textures du décor en high < 1 Go : pas de mesure
- [ÉCHEC] budgets low coast : 60.0 i/s, p99 16.67, GPU 6.16 ms
- [OK] budgets low mediterranean : 59.54 i/s, p99 16.67, GPU 5.76 ms
- [ÉCHEC] budgets low temperate_grassland : 58.51 i/s, p99 31.94, GPU 6.03 ms
- [ÉCHEC] budgets low farmland : 60.0 i/s, p99 16.67, GPU 8.04 ms
- [ÉCHEC] budgets low temperate_forest : 60.0 i/s, p99 16.67, GPU 7.26 ms
- [ÉCHEC] budgets low alpine : 60.0 i/s, p99 16.67, GPU 6.86 ms
- [À VOIR] U18 §5.3 aucune frontière droite entre biomes : à juger sur planche/ (propriétaire)
