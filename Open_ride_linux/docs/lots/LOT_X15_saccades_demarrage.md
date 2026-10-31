# Lot X15 – Saccades et temps de démarrage

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : Saccades avec leur cause, tâches de fond par tronçon, temps de démarrage | GDScript + Python | X13 | Petite | **Livré le 28 octobre** (branche `claude/project-thread-818r6t-x15`, sur X35) ; mesure en fenêtre réelle sur le PC ; issue #213 |

## 1. Objectif

Le banc du 25 octobre donnait 1 à 3 images/s pendant les 15 premières secondes, et l'essai 69 un pic de 68 ms au départ. La sonde X13 compte les images lentes, mais ne dit pas ce qui se passait. Proposition du fil bâtiments (28 octobre) : le temps des tâches de fond par tronçon.

## 2. À lire

`engine/scripts/perf_probe.gd`, `world_streamer.gd`, `osm_streamer.gd`, `tree_renderer.gd`, `main.gd` (démarrage, `route_loaded`), `engine/tests/perf_probe.py`.

## 3. Travail demandé

- **Journal des saccades** (sonde active) : chaque image de plus de 33 ms écrit une ligne dans `saccades.csv` (heure, durée, distance) avec ce qui s'est passé pendant cette image : tuile de terrain intégrée, couche OSM ajoutée, préparation d'arbres, compilation de shader (`RenderingServer` : nombre de pipelines compilés), capture du banc. Les modules de streaming signalent leurs étapes à la sonde par un appel léger (`PerfProbe.mark("tuile", id, ms)`), sans coût sans sonde.
- **Tâches de fond par tronçon** : durée de préparation de chaque tronçon (terrain, OSM, bâtiments, arbres) dans `taches.csv`.
- **Temps de démarrage** : du lancement de l'engine à la première image jouable (parcours chargé, 10 images de suite sous 33 ms) ; ligne `Démarrage : première image jouable à N ms`.
- **`perf_probe.py report`** : top 20 des saccades avec leur cause, répartition des causes, temps de démarrage.

## 4. Fichiers

- **Modifiés :** `perf_probe.gd`, `world_streamer.gd`, `osm_streamer.gd`, `tree_renderer.gd`, `main.gd`, `engine/tests/perf_probe.py`, `engine/tests/unit/test_perf_probe.gd`, `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `core/tests/test_perf_probe_saccades.py`.

## 5. Critères d'acceptation

1. Test GDScript : une image artificiellement longue après une marque « tuile » est attribuée à la tuile.
2. Rapport sur un CSV fabriqué : classement et causes justes.
3. Sans sonde, aucune écriture et aucun coût mesurable (test de budget X2).

## 6. Hors périmètre

Supprimer les saccades trouvées.

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x15`, sur X35).

- **Sonde** (`perf_probe.gd`) : `PerfProbe.mark(type, id, ms)` (étape du fil principal) et `PerfProbe.task(type, id, ms)` (tâche de fond, appelable depuis un fil de `WorkerThreadPool`, sous verrou) sont statiques et rendent la main tout de suite sans sonde ouverte (0,2 µs par appel mesuré dans le conteneur). Sonde ouverte, elle écrit à côté de son fichier :
  - `saccades.csv` (`t_s;unix_s;frame_ms;distance_m;cause;steps`) : chaque image de plus de 33 ms, la distance affichée, les étapes faites depuis l'image précédente et la cause : `capture` pour les trois images d'une capture du banc (X35), sinon l'étape la plus longue si elle prend au moins le quart de l'image, sinon `inconnue` ;
  - `taches.csv` (`t_s;kind;id;ms`) : durée de chaque tâche de fond, écrite à chaque seconde ;
  - `demarrage.txt` et la ligne `Démarrage : première image jouable à N ms` (temps depuis le lancement de l'engine) : première des 10 images de suite sous 33 ms après `route_loaded` (`route_ready()` appelé par `main.gd`).
- **Étapes signalées** : `world_streamer.gd` (tâches `near`, `far`, `flat`, `road` et `arbres` (préparation des arbres d'une tuile) ; étapes `tuile`, `route` et `arbres` (pose des arbres) dans `integrate`), `osm_streamer.gd` (tâches `osm` (tronçon entier) et `batiments` ; étape `osm`, signal `chunk_loaded` compris). `tree_renderer.gd` n'est pas modifié : sa préparation est mesurée autour de `prepare_tile`.
- **Rapport** : `perf_probe.py watch` et `report`, et `sim_bench.py --probe`, lisent ces fichiers dans le dossier du fichier de l'engine, les recopient dans le dossier du rapport et ajoutent à `sonde.txt` et `rapport.html` le temps de démarrage, les saccades par cause (nombre, pire, total), les 20 pires (heure, durée, distance, cause, étapes) et les durées des tâches de fond par type (médiane, p99, max). Un engine plus ancien sans ces fichiers donne le rapport d'avant.
- **Écart** : Godot 4.3 ne publie pas le nombre de pipelines compilés (compteurs `RENDERING_INFO_PIPELINE_COMPILATIONS_*` arrivés avec Godot 4.4) ; une compilation de shader apparaît donc comme `inconnue`. À ajouter avec la migration Y2. Sous Xvfb (rendu logiciel, plus de 100 ms par image), il n'y a ni première image jouable ni saccade utile : le banc garde l'attente fixe de 5 s d'X35, et la mesure se fait en fenêtre réelle sur le PC (`sim_bench.py --native --probe`).
- Tests : `engine/tests/unit/test_perf_probe.gd` (image longue après une marque `tuile` attribuée à la tuile, capture, `inconnue`, tâches, démarrage après 10 images, aucun effet ni coût sans sonde) ; `core/tests/test_perf_probe_saccades.py` (5 tests : classement, causes, tâches, rapport, engine ancien).
