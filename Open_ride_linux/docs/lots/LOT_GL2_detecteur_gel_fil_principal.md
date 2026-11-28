# Lot GL2 : détecteur de gel du fil principal de l'engine (gels du monde ouvert)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Gels du monde ouvert : un fil de l'engine signale tout blocage du fil principal de plus d'une seconde, avec l'étape en cours (tâche de fond attendue comprise) et sa durée ; `[perf-rendu]` au temps réel | GDScript | X15, PI1, GL1 | Petite | En cours (codé le 24 novembre, banc PC à faire) |

Suite du lot GL1 (#1006, mesure des trames `state` perdues), après relecture du journal de l'essai du 22/11.

## Constat : ce ne sont pas les trames qui se perdent, c'est l'engine qui s'arrête
- Essai du 22/11 (Biarritz, high, `openride_2026-11-22_15-53-37.log`) : à partir de 16:01, juste après deux choix
  aux carrefours (16:01:11 et 16:01:36), trois lignes `[gigue] state` de suite : max 9 141, 10 365 et 9 490 ms,
  1 688, 1 450 et 1 398 trames par minute. Le core envoie normalement (`Gigue` : state max 17 à 25 ms). Les
  carrefours de 15:56, 15:58 et 15:59 n'ont rien donné.
- Un écart de 9 s entre deux trames ne peut être noté par `ipc_client.gd` que si `_process` n'a pas tourné pendant
  ces 9 s : sinon le délai d'une seconde du contrat §6 aurait coupé la liaison (« Core non joignable »), et l'écart
  n'est pas compté quand la liaison est coupée. Aucune ligne « Core non joignable » dans le journal : le fil principal
  de l'engine était bloqué. Les trames « perdues » sont celles que le tampon de réception du noyau (environ 200 Ko,
  Godot ne lit le port qu'à `_process`) n'a pas pu garder ; les autres arrivent d'un coup à la reprise.
- Le journal ne le montrait pas : `[perf-rendu]` et `[diag] gel de l'engine` lisent le `delta` de Godot, borné à
  8 pas de physique (133 à 150 ms) quand il prend du retard. Pendant les gels, `[perf-rendu]` disait « max 146,8 ms ».
- Preuve au banc (rOWpile, medium, sonde à l'horloge, archive `acoups_ow_bancs.tgz`) : à t = 125,8 s, une image de
  4 286 ms au temps réel (`delta` 137 ms, presque tout dans les scripts : `process_ms` 4 286), un écart de 4 301 ms
  dans `[gigue] state`, 37 seq sautés (4039 → 4077) à la même seconde, et `[perf-rendu]` « max 137,1 ms ».
- Cause du blocage de 9 s : inconnue. Pistes, classées : (1) attente d'une tâche de fond sur le fil principal
  (`BgTasks.wait` de `world_streamer.swap_route` et `osm_streamer.swap_route` à chaque révision de la route, alors
  que les quatre fils du pool sont pris par des maillages de terrain et d'OSM de Biarritz en high) ; (2) travail sur
  toute la route connue à chaque révision (`living_decor.extend_route`, `segment_markers.refresh`, md5 de chaque
  tuile proche dans `_mark_rewritten_near`) ; (3) tuiles proches réécrites par le générateur après un choix
  (`session_ground`) et refaites. Ce lot donne la réponse au prochain essai ou banc.

## Ce que fait le lot (mesure seule, aucun changement de comportement)
- `engine/scripts/stall_watch.gd` : fil de surveillance (10 relevés par seconde) du battement posé par `main.gd` au
  début de chaque image. Sans image depuis 1 s : `[gel] fil principal bloqué depuis N ms : étape « X » (depuis M ms)`,
  rappel toutes les 5 s, puis `[gel] fin du blocage : N ms sans image ; étapes vues : X 90 %, Y 10 %`.
- Étapes : posées par `main.gd` aux grandes étapes de l'image (menus, parcours chargé, préchauffage, révision du
  monde ouvert et ses quatre sous-étapes, caméra et scène, fenêtre des tuiles, bots, décor vivant, arches, autres
  nœuds de la scène), par `bg_tasks.gd` pendant toute attente d'une tâche de fond (`attente de la tâche « osm 5 »`)
  et par les signaux du rendu (`rendu de l'image`, `après le rendu`). Une étape posée depuis un autre fil est ignorée.
- `[perf-rendu]` au temps réel (`PerfProbe.frame_time_ms`) au lieu du seul `delta` de Godot.
- Actif en séance réelle comme au banc, sans sonde : le journal du prochain essai nomme l'étape bloquée.

## Tests
- `engine/tests/unit/test_stall_watch.gd` : rien sans battement ni sous 1 s, début avec l'étape et son âge, rappel à
  5 s, fin avec la durée et la part des étapes, étape d'un autre fil ignorée, étape nommée pendant `BgTasks.wait`
  puis reposée, vrai fil démarré et arrêté.

## Recette PC
Catégorie : logique
- File `scripts/file_bancs/gl2_biarritz.toml` (cache séparé) : scénario `gel_ow_biarritz` (Biarritz trouvé par son
  nom, 12 min, un choix à droite puis à gauche toutes les 80 s comme à 16:01, captures toutes les 4 min), en high,
  medium et low, sonde active. Résultat : `gels.txt` de chaque étape (lignes `[gel]`, `[gigue] state`, révisions et
  carrefours) et `saccades.csv` de la sonde.
- Attendu : chaque écart de plus de 1 s de `[gigue] state` a sa ligne `[gel] fin du blocage` de même durée, avec
  l'étape qui l'explique. La correction viendra dans un lot suivant, selon l'étape nommée.
- Sur le vélo, sans banc : après une balade du monde ouvert, `grep "\[gel\]" ~/run_trainer.log`.
