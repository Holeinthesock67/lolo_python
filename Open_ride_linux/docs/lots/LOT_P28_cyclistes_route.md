# Lot P28 – Cyclistes sur la route du parcours

## 1. Objectif

Demande du propriétaire du 28 octobre : pour faire vivre la route, « plutôt plus de vélos » que plus de voitures. Aujourd'hui, en dehors des bots (O7, T12), le cycliste ne croise jamais un autre cycliste. Ce lot ajoute des cyclistes décoratifs sur la route du parcours : seuls ou en petits groupes, en face, qui doublent le cycliste ou qu'il double, plus nombreux dans les montées et près des villages. Ils ne sont pas des bots : aucun effet sur la physique, l'aspiration, les écarts ni le classement.

## 2. À lire

1. `docs/lots/LOT_P13_vehicules.md` (principe des cases de 250 m), `docs/lots/LOT_P17_integration_decor_complet.md`, `docs/lots/LOT_P21_passants_villages.md` (gestes et voix brèves), `docs/lots/LOT_Y14_personnages_animaux.md` (Builder et coureur casqué), `docs/lots/LOT_O7_affichage_bots.md`.
2. Code : `engine/scripts/traffic_model.gd`, `living_decor.gd` (montées `climbs`, villages), `people_mesh.gd` (`build_bike`, `build_person`, shader de pédalage ; à utiliser sans le modifier), `bots_view_model.gd` (positions des bots, pour l'écart), `sound_player.gd`, `quality_presets.gd`.

## 3. Prérequis

P13, P17, P21 et Y14 livrés ; P25 (véhicules au sol) fusionné avant, car il touche aussi `living_decor.gd` et `traffic_model.gd`.

## 4. Travail demandé

Nouveaux `engine/scripts/road_cyclists_model.gd` (sans nœud) et `road_cyclists_renderer.gd`, branchés par `living_decor.gd`.

- **Modèle sans nœud**, sur le principe de `traffic_model.gd` : le parcours est découpé en cases de 250 m ; chaque case tire, d'après la graine et son indice, un groupe de cyclistes avec une probabilité `CYCLIST_RATE` (proposition : 0,12 en plaine, 0,30 dans une montée de `climbs`, 0,20 à moins de 1 km d'un village), soit à peu près un groupe par kilomètre en plaine et trois par kilomètre dans un col. Taille du groupe : 1 (55 %), 2 (25 %), 3 à 6 (20 %), roulant en file ou à deux de front, à 0,6 m d'écart latéral et 1,5 m l'un derrière l'autre.
- **Trois cas**, tirés par groupe :
  - **en face** (40 %) : sur le bord gauche de la route, de 22 à 35 km/h sur le plat, de 35 à 55 km/h en descente ;
  - **devant, plus lent** (35 %) : sur le bord droit, de 18 à 28 km/h (de 9 à 16 km/h en montée) ; le cycliste les rattrape et les double ; ils restent à au moins 1,2 m sur sa droite pendant le dépassement (ils se serrent sur le bord) ;
  - **qui double** (25 %) : arrive de 150 m derrière, 4 à 8 km/h plus vite que le cycliste (au moins 25 km/h sur le plat), passe à au moins 1,2 m sur sa gauche, puis se rabat 20 m devant et s'éloigne. Si le cycliste accélère au-dessus de sa vitesse, le groupe reste derrière et disparaît au bout de 60 s.
- **Vitesse en pente** : vitesse de départ du groupe corrigée par la pente sous lui (une formule simple de puissance constante, sans le modèle physique du core) ; jamais plus de 70 km/h en descente.
- **Sécurité visuelle** : jamais un cycliste du décor à moins de 1,2 m latéralement du cycliste ou d'un bot à la même abscisse ; pas de groupe en face pendant qu'un véhicule de `traffic_model.gd` croise ou double ; aucun cycliste dans un tunnel ni en ville (`village` dense) à plus de 3 de front.
- **Pas d'effet sur la physique** : ce ne sont pas des bots (O7, T12) ; ils ne donnent ni aspiration, ni écart dans le HUD, ni classement.
- **Budget** : nouvelle clé `cyclists` de `LIVING` dans `quality_presets.gd`, 4 / 8 / 16 en `low` / `medium` / `high` ; les plus proches d'abord ; supprimés à plus de 300 m derrière ou 1 200 m devant.
- **Affichage** : vélo et coureur casqué construits par `people_mesh.gd` (`build_bike`, `build_person(false, true)`, sans modifier ce fichier), même shader de pédalage que les bots, cadence déduite de la vitesse (braquet fixe de 50 × 17), maillots tirés d'une palette de 8 couleurs par la graine du cycliste ; un `MultiMeshInstance3D` pour les vélos et un pour les coureurs, créés au démarrage. Un cycliste en face lève la main quand il croise le cycliste à moins de 15 m, une fois sur deux, si le shader des personnages le permet (geste des passants de P21) ; sinon il ne fait rien.
- **Son** : aucun son propre (le roulement d'un vélo ne s'entend pas par-dessus celui du cycliste) ; un groupe qui double dit « Salut ! » une fois sur trois, avec les voix brèves des passants de P21 (`sound_player.gd`).

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/living_decor.gd`, `quality_presets.gd` (clé `cyclists`), `sound_player.gd` (si une voix manque) ; `engine/tests/unit/test_quality_presets.gd`, `test_living_decor.gd` ; `engine/tests/perf_budgets.json` (ligne `road_cyclists_frame`) ; `engine/tests/README.md`, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `engine/scripts/road_cyclists_model.gd`, `road_cyclists_renderer.gd`, `engine/tests/unit/test_road_cyclists_model.gd`.
- **Interdits :** `people_mesh.gd` et `crowd_renderer.gd` (fil des personnages), les bots (core et `bots_view*.gd`), le compilateur, le core, les contrats.

## 6. Modifications de contrat autorisées

Aucune : ni IPC, ni format, ni thème, ni touche. Désactivé avec le reste par `[render] living = false`.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Sur 20 km de plaine puis 10 km de montée, de 15 à 30 groupes en plaine et de 20 à 40 en montée ; déterministe (même parcours, mêmes cyclistes).
3. Un groupe devant, plus lent, est doublé par le cycliste avec au moins 1,2 m d'écart ; un groupe qui double passe à gauche avec au moins 1,2 m d'écart puis se rabat ; aucun cycliste du décor à moins de 1,2 m latéralement du cycliste ou d'un bot à la même abscisse.
4. Jamais plus que `living(preset).cyclists` ; pédalage à la cadence attendue ; aucune aspiration ni écart au HUD ; aucun nœud créé après le démarrage ; mise à jour de 16 cyclistes sous 0,1 ms par image (`road_cyclists_frame`).

**Sur le PC cible (le propriétaire) :** séance en `medium` sur un parcours avec une montée : des cyclistes croisés, doublés ou qui doublent à peu près à chaque kilomètre, davantage dans la montée ; aucun cycliste qui traverse le cycliste ou un bot ; avis sur la densité (`CYCLIST_RATE`).

## 8. Hors périmètre

- Cyclistes qui réagissent à l'aspiration, aux attaques ou au classement : ce sont les bots (O7, T12, Y10).
- Pelotons de course, cyclistes sur les routes voisines, VTT sur les chemins (gravel, U22).
