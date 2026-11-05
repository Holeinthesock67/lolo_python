# Recette U18, partie PC (7bt)

## medium

Textures du sol (ligne [perf-rendu]) : 0 Mo

| Biome | s | i/s | p99 ms | GPU ms | GPU saturé % | VRAM Godot Mo | textures Mo | VRAM nvidia Mo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coast | 116 | 60 | 16.67 | 12.29 | 0 | 378 | 259.7 | 790 |
| mediterranean | 96 | 60 | 16.67 | 11.5 | 0 | 380.4 | 259.7 | 790 |
| temperate_grassland | 99 | 60 | 16.67 | 13.08 | 0 | 381.3 | 259.7 | 790 |
| farmland | 100 | 59 | 24.98 | 16.41 | 60 | 384.6 | 259.7 | 797 |
| temperate_forest | 95 | 60 | 16.67 | 14.69 | 22.1 | 383.3 | 259.7 | 797 |
| alpine | 98 | 60 | 16.67 | 13.13 | 1 | 382.5 | 260.5 | 797 |
| frontières | 67 | 60 | 16.67 | 13.52 | 9 | 382.4 | 259.7 | 797 |
| côte avec la mer (90 s) | 58 | 60 | 16.67 | 9.98 | 1.7 | 376.2 | 260.5 | 790 |

## Critères

- [À VOIR] U18 §5.1 low coast : pas de mesure
- [À VOIR] U18 §5.1 low mediterranean : pas de mesure
- [À VOIR] U18 §5.1 low temperate_grassland : pas de mesure
- [À VOIR] U18 §5.1 low farmland : pas de mesure
- [À VOIR] U18 §5.1 low temperate_forest : pas de mesure
- [À VOIR] U18 §5.1 low alpine : pas de mesure
- [À VOIR] U18 §5.2 textures du décor en high < 1 Go : pas de mesure
- [ÉCHEC] budgets medium coast : 60.0 i/s, p99 16.67, GPU 12.29 ms
- [OK] budgets medium mediterranean : 60.0 i/s, p99 16.67, GPU 11.5 ms
- [ÉCHEC] budgets medium temperate_grassland : 60.0 i/s, p99 16.67, GPU 13.08 ms
- [ÉCHEC] budgets medium farmland : 59.0 i/s, p99 24.98, GPU 16.41 ms
- [ÉCHEC] budgets medium temperate_forest : 60.0 i/s, p99 16.67, GPU 14.69 ms
- [ÉCHEC] budgets medium alpine : 60.0 i/s, p99 16.67, GPU 13.13 ms
- [À VOIR] U18 §5.3 aucune frontière droite entre biomes : à juger sur planche/ (propriétaire)
