# Lot AC5 : rechargement d'un parcours en étapes, une par image

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| À-coups du rechargement : chargement d'un parcours en trois étapes (vidage, streamer, suite), une par image, pas d'étape dans une image déjà chargée ; spectateurs et passants préchauffés un MultiMesh par image | GDScript | PI2, AC4 | Petite | En cours (codé le 22 novembre, banc PC à faire) |

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
  même classe que le préchauffage, type « chargement » dans la sonde), en trois étapes jouées une par image :
  « vidage » (monde d'avant libéré, décor de route caché), « streamer » (nouveau monde), « suite » (velodrome, ciel,
  decor, portiques_gp qui lance le préchauffage, segments, menu, fenetre, fin : quelques ms en tout, chaque partie
  notée « chargement <partie> »). Mêmes appels qu'avant, dans le même ordre. Une étape par partie (dix images) a été
  essayée : sous Xvfb chaque image après le streamer prend plusieurs secondes, le parcours arrivait une minute plus
  tard et 6 vérifications des tests graphiques échouaient (CI de la tête 069e1444).
- `_step_loading` : une image joue une étape du chargement, sinon une étape du préchauffage, jamais les deux.
  `warmup_plan.gd may_step` : si l'affichage du menu a déjà pris plus de 12 ms dans l'image (seule mesure retenue : sous un rendu lent, compter tout le début de l'image ralentissait le préchauffage de moitié, tour « flancs » de la CI), l'étape
  attend l'image suivante, une fois au plus. Un chargement remplacé par une autre demande (ou une run
  Cyber-Rogue) est abandonné ; le départ attend aussi la fin du chargement (`_step_start_wait`).
- `crowd_renderer.gd warm_steps(camera)` : une étape par MultiMesh (`spectateurs 0…`, `passants 0…`), chacune ne
  montre que le sien devant la caméra ; `warm_up(camera)` garde le préchauffage de tous d'un coup (tests).
- `world_streamer.gd` : sous-étapes notées dans la sonde (`streamer attente fils`, `vidage N`, `index`, `biome`,
  `osm`, `horizon`), pour nommer la partie en cause si l'étape streamer reste lente.

## Correction du 25/11 : le préchauffage attend le décor du départ
- Banc rJ25J (pile #1066 + #953 + #985, DB1 medium, shaders froids, GTX 1060) : les étapes « spectateurs 0 » à
  « spectateurs 3 » jouaient dans les mêmes images que l'arrivée des premières tuiles, des arbres et des tronçons OSM
  du départ (8,5 s et 53 pipelines, puis 1,1 s, 1,6 s et 3,8 s). Une étape par image ne suffit pas si l'image compile
  déjà le décor.
- `warmup_plan.gd may_step(busy_ms, streaming)` : tant que le décor du départ arrive (`streamer.pending_count() > 0`,
  doublures de shaders du lot AC6 comprises), pas d'étape ; au plus `STREAM_WAIT_MS` (15 s) depuis la première attente
  du plan, puis le plan avance quoi qu'il arrive. Pas d'attente en séance (`RUNNING`) ni dans la scène Cyber-Rogue.
- `crowd_renderer.gd` : dès `warm_steps`, les vraies personnes sont retenues (MultiMesh vides) jusqu'à l'étape du
  dernier MultiMesh, au plus `HOLD_MAX_MS` (30 s) : la foule du départ ne fait plus son premier dessin d'un coup, avec
  les tuiles, pendant que le plan attend.

## Tests
- 25/11 : `test_warmup_plan.gd` (attente du décor, borne, remise à zéro par un nouveau plan), `test_crowd_model.gd`
  (foule retenue avant les étapes, relâchée à la dernière, retenue bornée).
- `test_warmup_plan.gd` : `may_step` remet l'étape d'une image chargée au plus MAX_SKIPS fois, puis joue ; plan du
  chargement à part, type propre.
- `test_crowd_model.gd` : une étape par MultiMesh, chacune ne montre que le sien, puis la sélection reprend.

## Recette PC
Catégorie : logique. Medium : galerie Cyber-Rogue (`rogue_galerie.py --qualites medium --probe`) et `grand_prix_onze` ;
attendu : aucune image de plus de 150 ms de cause « chargement », « shaders » (spectateurs) ou au retour de la run
(bilan), délai jusqu'au départ à peu près le même. Si `chargement streamer` dépasse encore 100 ms, la sous-étape
`streamer …` de la même image dit quoi découper ensuite.
Depuis le 25/11 (avec #953 et #1066) : shaders froids, DB1 low, medium et high, monde ouvert `ea1_lac` medium, cache
séparé ; attendu : aucune étape « préchauffage spectateurs N » dans une image qui a aussi « tuile », « arbres » ou
« osm N », et aucune image de plus de 1 s après le chargement.
