# Lot AC5 : rechargement d'un parcours en étapes, une par image

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| À-coups du rechargement : chargement d'un parcours en dix étapes du plan unique, une par image, pas d'étape dans une image déjà chargée ; spectateurs et passants préchauffés un MultiMesh par image | GDScript | PI2, AC4 | Petite | En cours (codé le 22 novembre, banc PC à faire) |

Suite du lot AC4 (fil global « Supprimer les à-coups récurrents de main », 22/11).

## Constat (banc PC de la PR #981, galerie Cyber-Rogue medium, `saccades_r981_rogue.csv`)
- t = 106,7 s, sous l'écran de pause : image de 182 ms, cause « chargement » : rechargement complet du parcours de
  démo dans une seule image (`chargement streamer` 112 ms, ciel, décor, portiques…, plus `préchauffage portiques`
  21 ms et l'affichage du menu 26 ms). Ce rechargement sous la pause est déjà supprimé sur main par le lot R24 (#933,
  absent de la tête du banc) ; le même chargement en une image reste à chaque changement de parcours au menu.
- t = 106,8 s : 133 ms, cause « shaders », 11 pipelines : étape `spectateurs préchauffage`, tous les MultiMesh des
  spectateurs montrés dans la même image.
- t = 488,4 s, retour au monde classique après la run : 216 ms, 46 pipelines : écran de bilan (`menu affichage
  summary` 46 ms) et tout le chargement (streamer 32 ms, ciel, décor…) dans la même image.
- t = 109,5 s : 169 ms, cause « inconnue », 18 ms de scripts, aucune étape notée : hors de ce lot (rendu ou pilote),
  à suivre au prochain banc.

## Correction (une seule voie)
- `main.gd _poll_route_job` : le parcours lu par la tâche de fond est posé par le plan du chargement (`_load_plan`,
  même classe que le préchauffage, type « chargement » dans la sonde), en dix étapes jouées une par image :
  vidage, streamer, velodrome, ciel, decor, portiques_gp (qui lance le plan de préchauffage), segments, menu,
  fenetre, fin. Mêmes appels qu'avant, dans le même ordre. Le décor de route est caché du vidage à l'étape decor.
- `_step_loading` : une image joue une étape du chargement, sinon une étape du préchauffage, jamais les deux.
  `warmup_plan.gd may_step` : si le fil principal a déjà travaillé plus de 12 ms dans l'image (menu affiché), l'étape
  attend l'image suivante, au plus 4 images de suite. Un chargement remplacé par une autre demande (ou une run
  Cyber-Rogue) est abandonné ; le départ attend aussi la fin du chargement (`_step_start_wait`).
- `crowd_renderer.gd warm_steps(camera)` : une étape par MultiMesh (`spectateurs 0…`, `passants 0…`), chacune ne
  montre que le sien devant la caméra ; `warm_up(camera)` garde le préchauffage de tous d'un coup (tests).
- `world_streamer.gd` : sous-étapes notées dans la sonde (`streamer attente fils`, `vidage N`, `index`, `biome`,
  `osm`, `horizon`), pour nommer la partie en cause si l'étape streamer reste lente.

## Tests
- `test_warmup_plan.gd` : `may_step` remet l'étape d'une image chargée au plus MAX_SKIPS fois, puis joue ; plan du
  chargement à part, type propre.
- `test_crowd_model.gd` : une étape par MultiMesh, chacune ne montre que le sien, puis la sélection reprend.

## Recette PC
Catégorie : logique. Medium : galerie Cyber-Rogue (`rogue_galerie.py --qualites medium --probe`) et `grand_prix_onze` ;
attendu : aucune image de plus de 150 ms de cause « chargement », « shaders » (spectateurs) ou au retour de la run
(bilan), délai jusqu'au départ à peu près le même. Si `chargement streamer` dépasse encore 100 ms, la sous-étape
`streamer …` de la même image dit quoi découper ensuite.
