# Lot AC1 : l'image qui suit une capture est comptée avec la capture

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| À-coups de main : l'image lente qui suit une capture du banc est comptée avec la capture, process_ms non hérité | GDScript | PI1 | Petite | En cours (PR #953, banc PC à faire) |

Fil global « Supprimer les à-coups récurrents de main » (21/11). Analyse complète :
`/mnt/project-files/statut/ACOUPS_MAIN_2026-11-21.md` (bancs de la nuit rNUIT20).

## Constat
- Au banc, chaque capture d'écran prend ~290 ms (lecture de l'image par le CPU). L'image d'après est encore lente
  (50 à 110 ms) : le rendu se remet de la lecture. Elle arrive une fois par capture, et seulement au banc.
- La sonde de PI1 lit `process_ms` (Performance.TIME_PROCESS) sur deux images et garde le plus grand, car Godot
  publie ce temps avec une image de retard. Pour l'image qui suit une capture, la première lecture est donc celle
  de la capture : l'image hérite de ~290 ms et passe en cause « scripts ».
- Effet : ces images comptaient comme de vrais à-coups dans tous les fils (DB3 Sud high : 3,2 images lentes par
  minute, dont 48 juste après une capture ; 0,3 par minute sans elles).

## Règle (une seule, pour tous les bancs)
- Une image lente qui suit une image avec l'étape `capture` a la cause `capture`, comme la capture elle-même,
  sauf si une étape à elle (au moins le quart de l'image) ou des pipelines compilés l'expliquent.
- Son `process_ms` est celui de sa propre lecture (la seconde), pas celui de la capture.
- `perf_probe.py` et `sim_bench.py` écartent déjà les causes `capture` : rien d'autre ne change.

## Tests
`engine/tests/unit/test_perf_probe.gd` : cause après une capture (et priorité des étapes et des shaders), repérage
de l'étape `capture`, suite capture → image suivante → image lente plus loin écrite dans `saccades.csv`.

## Recette PC
Catégorie : logique. Fumée + medium : un banc avec captures (ex. `nominal` sur `demo-biomes-sud`, captures toutes
les 15 s) ; attendu : plus d'images « scripts » juste après les captures, images lentes par minute en baisse,
pire image et budgets GPU inchangés.
