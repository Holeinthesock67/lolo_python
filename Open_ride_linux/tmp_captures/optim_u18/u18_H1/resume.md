# Recette U18, partie PC (7bt)

## high

Textures du sol (ligne [perf-rendu]) : 0 Mo

| Biome | s | i/s | p99 ms | GPU ms | GPU saturé % | VRAM Godot Mo | textures Mo | VRAM nvidia Mo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coast | 116 | 56.97 | 18.42 | 16.41 | 53.4 | 384.9 | 263.9 | 798 |
| mediterranean | 96 | 59.27 | 18.06 | 15.96 | 64.6 | 388.4 | 263.9 | 798 |
| temperate_grassland | 99 | 59.08 | 18.06 | 16.17 | 74.7 | 388.5 | 263.9 | 798 |
| farmland | 100 | 52.2 | 20.07 | 18.41 | 88 | 394.1 | 263.9 | 797 |
| temperate_forest | 95 | 54.08 | 20 | 17.86 | 90.5 | 392.3 | 263.9 | 797 |
| alpine | 99 | 60 | 16.67 | 15.38 | 44.4 | 391.8 | 264.8 | 797 |
| frontières | 66 | 58.23 | 18.25 | 16.23 | 71.2 | 391.6 | 263.9 | 798 |
| côte avec la mer (90 s) | 56 | 59.91 | 16.67 | 11.7 | 0 | 383.3 | 264.8 | 791 |

## Critères

- [À VOIR] U18 §5.1 low coast : pas de mesure
- [À VOIR] U18 §5.1 low mediterranean : pas de mesure
- [À VOIR] U18 §5.1 low temperate_grassland : pas de mesure
- [À VOIR] U18 §5.1 low farmland : pas de mesure
- [À VOIR] U18 §5.1 low temperate_forest : pas de mesure
- [À VOIR] U18 §5.1 low alpine : pas de mesure
- [OK] U18 §5.2 textures du décor en high < 1 Go : 265 Mo
- [ÉCHEC] budgets high coast : 56.97 i/s, p99 18.42, GPU 16.41 ms
- [ÉCHEC] budgets high mediterranean : 59.27 i/s, p99 18.06, GPU 15.96 ms
- [ÉCHEC] budgets high temperate_grassland : 59.08 i/s, p99 18.06, GPU 16.17 ms
- [ÉCHEC] budgets high farmland : 52.2 i/s, p99 20.07, GPU 18.41 ms
- [ÉCHEC] budgets high temperate_forest : 54.08 i/s, p99 20.0, GPU 17.86 ms
- [ÉCHEC] budgets high alpine : 60.0 i/s, p99 16.67, GPU 15.38 ms
- [À VOIR] U18 §5.3 aucune frontière droite entre biomes : à juger sur planche/ (propriétaire)
