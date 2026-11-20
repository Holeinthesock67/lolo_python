# Lot PI1 – Pire image : vraie durée des blocages et compteur de shaders compilés

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Pire image (fil global du 17 novembre) : la sonde mesure la vraie durée d'une image au lieu du delta borné de Godot, compte les pipelines compilés et le temps des scripts, et nomme les causes « shaders » et « scripts » | GDScript, Python | X13, X15, Y2 | Petite | En cours (étape 1 : mesure) |

## 1. Objectif

La « pire image » de 133 à 150 ms revient sur presque tous les bancs : ERG (#882), Grand Prix, demo_long, DB1, DB3, récif. L'analyse du 17 novembre a porté sur 150 fichiers `saccades.csv` (bancs r201 à r716e, puis r882b, rgp10e, rgp11d, rGP13, rGP4v, rAS10c, rDB3bB, rDB3m, r866e, rSM1d et rSM2b). Elle montre deux choses :

- **La mesure plafonne.** Aucune image ne dépasse 150,0 ms, et les valeurs s'entassent à 133,3 ms. La sonde lit le `delta` de `_process`, que Godot borne quand il prend du retard : au plus 8 pas de physique à 60 Hz, soit 133 ms, avec un peu de marge jusqu'à 150 ms. Un blocage de 0,2 s et un blocage de 2 s s'affichent donc pareil.
- **Les pires images restantes tombent sur des moments de jeu**, et les captures du banc sont déjà mises à part. On les trouve au départ (0 m), au demi-tour au bout du parcours (ERG à 4 175 m, demo_long à 8 768 m), à chaque appui sur Z en Grand Prix, et à la pose des arbres d'une tuile proche (DB1). Dans la plupart des cas, les étapes notées ne prennent que 0,5 à 4 ms. La cause est donc « inconnue » : premier dessin (compilation des pipelines, envoi au GPU) ou scripts qui ne sont pas notés.

Plan complet : `/mnt/project-files/plans/PLAN_PIRE_IMAGE_GLOBALE_2026-11-17.md`. Ce lot fait l'étape 1, la mesure. La correction viendra après le profil sur le PC, et elle sera la même pour tous les modes.

## 2. Spécification (étape 1)

| # | Règle |
| --- | --- |
| PI1-1 | `perf_probe.gd` : le temps d'une image est le plus grand de deux valeurs, le `delta` de Godot et le temps réel écoulé depuis l'image précédente (`frame_time_ms`). Cette règle vaut pour toutes les colonnes : p50, p99, pire image et saccades. |
| PI1-2 | `saccades.csv` gagne trois colonnes : `delta_ms` (le delta de Godot, pour comparer), `pipelines` (pipelines compilés pendant l'image, somme des `Performance.PIPELINE_COMPILATIONS_*`, publiés depuis Godot 4.4) et `process_ms` (`Performance.TIME_PROCESS` de l'image). `moteur.csv` gagne `pipelines` (somme de la seconde). |
| PI1-3 | Cause d'une saccade, dans cet ordre : capture, puis étape notée d'au moins le quart de l'image, puis « shaders » si au moins un pipeline a été compilé, puis « scripts » si `process_ms` fait au moins le quart de l'image, sinon « inconnue » (rendu, envoi au GPU, pilote). |
| PI1-4 | `perf_probe.py` : le rapport des saccades donne le total des pipelines compilés, le nombre d'images plus longues que le delta de Godot, et les pipelines de chaque pire saccade. Les fichiers d'un engine plus ancien se lisent comme avant. |
| PI1-6 | Capture du banc (après le banc rPI1) : `main.gd` mesure le coût de la capture (lecture de l'image et PNG) et le passe à `mark_capture(ms)`. La sonde le retire de l'image de la capture, puis compte le reste comme pour toute image. La capture est aussi une étape `capture` de saccades.csv, et elle n'est la cause que selon la règle des étapes. Avant, l'image de la capture et les deux suivantes étaient mises à part en entier, et un gel de 3,9 s tombé sur une capture disparaissait. |
| PI1-7 | `process_ms` : selon l'ordre des nœuds, Godot publie le temps des `_process` à l'image lente ou à la suivante. La saccade s'écrit donc une image plus tard, avec la plus grande des deux lectures. |
| PI1-5 | Les seuils ne changent pas : départ 150 ms, pire image 100 ms, 3 images lentes par minute au plus. Avec la vraie durée, certains bancs vont d'abord sembler pires. C'est attendu. |

## 3. Fichiers

- `engine/scripts/perf_probe.gd`, `engine/tests/unit/test_perf_probe.gd` ;
- `engine/tests/perf_probe.py`, `core/tests/test_perf_probe_saccades.py`.

## 4. Critères d'acceptation

1. Cloud : `test_perf_probe.gd` et `test_perf_probe_saccades.py` passent.
2. PC, sur main et sur la branche, en low, medium et high : l'ERG sur la démo avec demi-tour (banc de r882b), `grand_prix`, `grand_prix_onze`, `demo_long`, DB1, DB3 et le récif. Pour chaque banc, un tableau des vraies durées et des causes (départ, demi-tour, Z, arbres), avec les pipelines compilés.
3. Un passage sans capture ni sonde chiffre le coût de l'instrumentation (question du propriétaire, 17 novembre).

## 5. Banc rPI1 (nuit du 19 au 20 novembre, branche 4a3d1514 et main 80f9dd54)

Scénarios passés : ERG 15 min sur la démo (sans demi-tour), `grand_prix`, demo_long et une fumée (demo medium), en low, medium et high.

- **Chargement : environ 25 s de gel du fil principal avant le départ, dans tous les scénarios et dans les trois qualités.** On voit quatre images d'affilée de 14 s, 4,7 s, 2 s et 3,8 s (de 20 à 32 s), avec 70, 67, 17 et 17 pipelines compilés, et des `_process` de 11,7 s, 7 s, 2 s et 3,9 s. La première se produit pendant « cyclistes préchauffage » (1 000 ms notés). Sur main, ces mêmes gels apparaissaient à 128-146 ms.
- La pire image « départ » de 225 à 255 ms, en échec sur la branche, est la traîne de ces gels. Le gel de 3,6 à 3,9 s qui la précède était caché, car il était compté comme une capture, d'où PI1-6.
- Grand Prix : à chaque Z, une image de 135 à 148 ms, sans pipeline compilé et avec 16 à 27 ms de scripts. Le temps part donc dans le rendu.
- Captures du banc : 245 à 308 ms (lecture de l'image et PNG), contre 141 à 148 ms affichés sur main.
- ERG en low, medium et high, branche et main : « médiane 15,7 km/h, attendu 40 » vient du réglage de vitesse imposée dans une séance ERG sur le col, pas du jeu.

## 6. Suite (étape 3, selon le profil)

- Si ce sont les shaders : un seul préchauffage au chargement, où chaque module déclare ses matériaux et maillages, et qui remplace les préchauffages au cas par cas (Y19, Y20, cyclistes, forêts lointaines, panneaux). On y ajoute le cache des pipelines sur disque.
- Si ce sont les scripts : les étapes qui manquent (demi-tour, objets du GP) sont notées, puis passent par une seule file limitée par image.
- Arbres d'une tuile (DB1) : la même file limitée par image que les autres intégrations du streaming.
