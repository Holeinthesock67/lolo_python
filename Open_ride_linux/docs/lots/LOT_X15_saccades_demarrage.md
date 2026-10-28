# Lot X15 – Saccades et temps de démarrage

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
