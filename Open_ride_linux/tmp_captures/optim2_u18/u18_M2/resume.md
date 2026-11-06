# Recette U18, partie PC (7bt)

## medium

Textures du sol (ligne [perf-rendu]) : 0 Mo

| Biome | s | i/s | p99 ms | GPU ms | GPU saturé % | VRAM Godot Mo | textures Mo | VRAM nvidia Mo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coast | 116 | 59.98 | 16.67 | 12.01 | 0 | 353.5 | 235.7 | 790 |
| mediterranean | 94 | 60 | 16.67 | 11.02 | 0 | 355.7 | 235.7 | 790 |
| temperate_grassland | 98 | 59.9 | 17.45 | 12.72 | 0 | 356.6 | 235.7 | 790 |
| farmland | 100 | 59.88 | 17.26 | 15.71 | 56 | 360.1 | 235.7 | 789 |
| temperate_forest | 94 | 60 | 16.67 | 14.45 | 19.1 | 358.8 | 235.7 | 789 |
| alpine | 97 | 60 | 16.67 | 12.57 | 0 | 358 | 236.5 | 789 |
| frontières | 66 | 59.23 | 18.06 | 12.86 | 4.5 | 357.9 | 235.7 | 790 |
| côte avec la mer (90 s) | 55 | 59.49 | 16.67 | 9.17 | 0 | 352.7 | 236.5 | 790 |

## Critères

- [À VOIR] U18 §5.1 low coast : pas de mesure
- [À VOIR] U18 §5.1 low mediterranean : pas de mesure
- [À VOIR] U18 §5.1 low temperate_grassland : pas de mesure
- [À VOIR] U18 §5.1 low farmland : pas de mesure
- [À VOIR] U18 §5.1 low temperate_forest : pas de mesure
- [À VOIR] U18 §5.1 low alpine : pas de mesure
- [À VOIR] U18 §5.2 textures du décor en high < 1 Go : pas de mesure
- [ÉCHEC] budgets medium coast : 59.98 i/s, p99 16.67, GPU 12.01 ms
- [OK] budgets medium mediterranean : 60.0 i/s, p99 16.67, GPU 11.02 ms
- [ÉCHEC] budgets medium temperate_grassland : 59.9 i/s, p99 17.45, GPU 12.72 ms
- [ÉCHEC] budgets medium farmland : 59.88 i/s, p99 17.26, GPU 15.71 ms
- [ÉCHEC] budgets medium temperate_forest : 60.0 i/s, p99 16.67, GPU 14.45 ms
- [ÉCHEC] budgets medium alpine : 60.0 i/s, p99 16.67, GPU 12.57 ms
- [À VOIR] U18 §5.3 aucune frontière droite entre biomes : à juger sur planche/ (propriétaire)
