# Recette U18, partie PC (7bt)

## high

Textures du sol (ligne [perf-rendu]) : 0 Mo

| Biome | s | i/s | p99 ms | GPU ms | GPU saturé % | VRAM Godot Mo | textures Mo | VRAM nvidia Mo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coast | 116 | 57.27 | 18.29 | 16.12 | 42.2 | 385.4 | 263.9 | 798 |
| mediterranean | 96 | 60 | 16.67 | 15.56 | 47.9 | 388.9 | 263.9 | 798 |
| temperate_grassland | 100 | 59.36 | 18.06 | 15.73 | 55 | 389.2 | 263.9 | 800 |
| farmland | 100 | 52.95 | 20.27 | 18.19 | 87 | 394.3 | 263.9 | 798 |
| temperate_forest | 95 | 55.08 | 20.9 | 17.43 | 86.3 | 392.8 | 263.9 | 798 |
| alpine | 99 | 60 | 16.67 | 15.01 | 20.2 | 392.7 | 264.8 | 798 |
| frontières | 66 | 58.51 | 18.35 | 15.82 | 63.6 | 391.9 | 263.9 | 798 |
| côte avec la mer (90 s) | 57 | 60 | 16.67 | 11.84 | 0 | 383.3 | 264.8 | 791 |

## Critères

- [À VOIR] U18 §5.1 low coast : pas de mesure
- [À VOIR] U18 §5.1 low mediterranean : pas de mesure
- [À VOIR] U18 §5.1 low temperate_grassland : pas de mesure
- [À VOIR] U18 §5.1 low farmland : pas de mesure
- [À VOIR] U18 §5.1 low temperate_forest : pas de mesure
- [À VOIR] U18 §5.1 low alpine : pas de mesure
- [OK] U18 §5.2 textures du décor en high < 1 Go : 265 Mo
- [ÉCHEC] budgets high coast : 57.27 i/s, p99 18.29, GPU 16.12 ms
- [ÉCHEC] budgets high mediterranean : 60.0 i/s, p99 16.67, GPU 15.56 ms
- [ÉCHEC] budgets high temperate_grassland : 59.36 i/s, p99 18.06, GPU 15.73 ms
- [ÉCHEC] budgets high farmland : 52.95 i/s, p99 20.27, GPU 18.19 ms
- [ÉCHEC] budgets high temperate_forest : 55.08 i/s, p99 20.9, GPU 17.43 ms
- [ÉCHEC] budgets high alpine : 60.0 i/s, p99 16.67, GPU 15.01 ms
- [À VOIR] U18 §5.3 aucune frontière droite entre biomes : à juger sur planche/ (propriétaire)
