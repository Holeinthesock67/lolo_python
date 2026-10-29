# Lot P32 – Circulation à droite : le cycliste dans la voie de droite, chacun à droite dans son sens

## 1. Objectif

Demande du propriétaire du 29 octobre : « les véhicules dont les cyclistes roulent à droite de la route et pas au milieu ». Jusqu'ici, le cycliste (caméra, avatar) roulait sur la ligne médiane et tout le décor de la route se plaçait par rapport à lui : la voiture en face passait près du bord gauche, celle qui double se rabattait devant lui au milieu, les cyclistes du décor se partageaient les bords autour de l'axe.

## 2. À lire

`docs/lots/LOT_P13_*`, `LOT_P25_vehicules_au_sol.md`, `LOT_P28_cyclistes_route.md` ; code : `engine/scripts/road_builder.gd`, `traffic_model.gd`, `road_cyclists_model.gd`, `bots_view.gd`, `main.gd`.

## 3. Prérequis

P25 et P28 livrés.

## 4. Travail demandé

- **Places en travers de la chaussée** (`road_builder.gd`, seule source) : écart à l'axe, positif à droite du sens du parcours, sur la chaussée de 6 m. Cycliste `RIDER_LATERAL_M` = 1,2 m (voie de droite, 1,8 m du bord), bots `BOT_LATERAL_M` = 2,1 m (à sa droite, vers le bord), milieu de voie `LANE_CENTER_M` = 1,5 m (la voie d'en face à −1,5 m).
- **Cycliste** (`main.gd` `_rider_point`) : la caméra (toutes les vues), l'avatar et la vue des menus partent de cette place.
- **Véhicules de la route** (`traffic_model.gd`) : en face, milieu de leur voie (`oncoming_lateral`, plus loin si l'écart de 1,5 m au cycliste le demande : camion, autocar) ; qui doublent : voie de droite derrière le cycliste, à 1,5 m au moins de lui en le doublant (`lane_lateral`, compté depuis sa place), puis retour à droite.
- **Cyclistes du décor** (`road_cyclists_model.gd`) : en face sur le bord gauche (leur droite), devant et plus lents sur le bord droit, ceux qui doublent passent à sa gauche puis se rabattent à droite. `MIN_GAP_M` passe de 1,2 à 0,7 m d'épaule à épaule (un cycliste qui en double un autre) : avec le cycliste dans la voie de droite, 1,2 m ne laisse plus de place sur le bord.
- **Routes voisines** (`road_traffic_model.gd`) : inchangées, déjà à droite sur les routes à deux voies ; un chemin à une voie reste roulé au milieu.
- **Outil de test** (message `_test` `decor_place`, hors contrat) : pose une voiture (`vehicle` : `kind`, `dir`, `rel_m`, `kmh` ; dans le même sens et tout près, posée en train de doubler) ou un groupe de cyclistes (`cyclists` : `case`, `rel_m`, `size`, `abreast`) près du cycliste. `test_info` du décor donne `road_users` (sorte, sens, écart à l'axe, distance) et `rider_lateral` (écart de la caméra à l'axe, mesuré).

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/road_builder.gd`, `main.gd`, `bots_view.gd`, `traffic_model.gd`, `road_cyclists_model.gd`, `living_decor.gd` ; `engine/tests/visual_check.py` (scène `voies`) ; tests `test_traffic_model.gd`, `test_road_cyclists_model.gd` ; `engine/tests/README.md`, `docs/OUTILS_DE_TEST.md`, `docs/RECETTE_P27.md`, index.
- **Interdits :** le core, les contrats, la position des bots dans le core (seul leur affichage bouge).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `test_traffic_model.gd` : chaque véhicule à droite dans son sens hors dépassement, à 1,5 m au moins du cycliste dans la voie de droite, chaque sorte en face sur sa droite.
2. `test_road_cyclists_model.gd` : en face à gauche de l'axe, devant à droite du cycliste, jamais à moins de 0,7 m de lui ni d'un bot.
3. `visual_check.py`, scène `voies` : cycliste dans la voie de droite, usagers en face à gauche de l'axe, cyclistes devant à sa droite, utilitaire qui double à 1,5 m au moins sur sa gauche.
4. `test_docs_coherence.py` passe.

## 8. Hors périmètre

Le cycliste ne se déporte pas pour doubler (sa place est fixe) ; les places ne suivent pas encore `road.width_m` du thème (6 m partout aujourd'hui).

## 9. Livraison

- `visual_check.py` en `1280x720:low` dans le cloud : 543/543 vérifications, dont la scène `voies` (cycliste à +1,20 m de l'axe ; voiture en face à −1,63 m, cycliste en face à −2,50 m ; deux cyclistes devant à +2,50 m ; utilitaire qui double à −1,72 m, 1,50 m d'écart). Captures avant et après : `voies_face`, `voies_depassement`.
- Images de référence de `run_visual_tests.sh` sur le PC : la caméra a bougé de 1,2 m, relancer une fois avec `--update-golden`.
