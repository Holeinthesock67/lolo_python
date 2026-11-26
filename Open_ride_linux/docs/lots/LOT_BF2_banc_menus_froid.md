# Lot BF2 : banc des menus à caches de rendu vides jugé à froid

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série AC (à-coups) : le banc des menus note si ses caches de rendu étaient vides, et la sonde juge alors le départ à froid (1 s), comme le banc simulé depuis BF1 | Python | BF1, ML2 | Petite | **En revue** (PR à venir) |

Demande du 26/11 (coordinateur, après le banc r1097) : même défaut que celui corrigé par BF1 dans `sim_bench.py`,
cette fois dans le banc des menus (`menu_bench.py` puis `perf_probe.py report`).

## 1. Constat (banc r1097, étape « ow-chaud », scénario ea1_lac)

- `[ÉCHEC] à-coups : départ : pire image 3547 ms de 20 à 30 s et avant le premier mètre (au plus 150 ms)`.
- Le banc des menus part d'un HOME neuf : sans `--caches-rendu`, les caches de Godot et du pilote sont vides et tout
  se compile au départ (82 pipelines à 18 s, puis 3 à 13 par image). `perf_probe.py report`, lancé ensuite par la
  file, jugeait pourtant le départ à chaud (150 ms) : il ne savait rien des caches.

## 2. Travail

- BF2-1 : `menu_bench.render_caches_empty` (pas de `--caches-rendu`, ou dossier sans fichier) ; au lancement de
  l'engine, ligne `[INFO] caches de rendu` et marque `shaders.txt` (« froid » ou « chaud ») posée à côté de chaque
  fichier `--perf-probe=` passé à l'engine.
- BF2-2 : `perf_probe.py report` lit cette marque (`read_shaders_mark`) et la passe à `hitch_checks` : à froid, départ
  jugé à `cold_start_freeze_ms` (1 s), chargement indicatif ; option `--shaders` pour l'imposer ; sans marque, à
  chaud comme avant. `watch` lit aussi la marque.
- Tests : `core/tests/test_bancs_menus_froid.py`.

## 3. Recette

- Rejouer l'étape ea1_lac de la file du monde ouvert : ligne « Caches de shaders au départ : froid (marque du banc) »,
  départ jugé à 1 s. Avec `--caches-rendu` déjà rempli : « chaud », 150 ms.

## Livraison

- PR à venir (branche `claude/project-thread-gn65yi-menus`).
