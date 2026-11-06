# Recette U18, partie PC (7bt)

## high

Textures du sol (ligne [perf-rendu]) : 0 Mo

| Biome | s | i/s | p99 ms | GPU ms | GPU saturé % | VRAM Godot Mo | textures Mo | VRAM nvidia Mo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coast | 117 | 60 | 16.67 | 14.26 | 21.4 | 323.1 | 202.1 | 790 |
| mediterranean | 96 | 60 | 16.67 | 13.39 | 3.1 | 326.6 | 202.1 | 790 |
| temperate_grassland | 99 | 60 | 16.67 | 13.44 | 1 | 326.8 | 202.1 | 790 |
| farmland | 100 | 57.59 | 24.85 | 16.44 | 69 | 333.4 | 202.1 | 797 |
| temperate_forest | 95 | 59.43 | 18.06 | 15.8 | 55.8 | 330.5 | 202.1 | 797 |
| alpine | 99 | 60 | 16.67 | 13.06 | 0 | 330 | 203 | 797 |
| frontières | 66 | 60 | 16.67 | 13.85 | 18.2 | 329.6 | 202.1 | 797 |
| côte avec la mer (90 s) | 57 | 59.98 | 16.67 | 10.1 | 1.8 | 321 | 203 | 790 |

## Critères

- [À VOIR] U18 §5.1 low coast : pas de mesure
- [À VOIR] U18 §5.1 low mediterranean : pas de mesure
- [À VOIR] U18 §5.1 low temperate_grassland : pas de mesure
- [À VOIR] U18 §5.1 low farmland : pas de mesure
- [À VOIR] U18 §5.1 low temperate_forest : pas de mesure
- [À VOIR] U18 §5.1 low alpine : pas de mesure
- [OK] U18 §5.2 textures du décor en high < 1 Go : 203 Mo
- [ÉCHEC] budgets high coast : 60.0 i/s, p99 16.67, GPU 14.26 ms
- [OK] budgets high mediterranean : 60.0 i/s, p99 16.67, GPU 13.39 ms
- [OK] budgets high temperate_grassland : 60.0 i/s, p99 16.67, GPU 13.44 ms
- [ÉCHEC] budgets high farmland : 57.59 i/s, p99 24.85, GPU 16.44 ms
- [ÉCHEC] budgets high temperate_forest : 59.43 i/s, p99 18.06, GPU 15.8 ms
- [OK] budgets high alpine : 60.0 i/s, p99 16.67, GPU 13.06 ms
- [À VOIR] U18 §5.3 aucune frontière droite entre biomes : à juger sur planche/ (propriétaire)
