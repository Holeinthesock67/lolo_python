# Lot T8 – Engine : lignes de départ et d'arrivée, arches de bonus, panneaux « Sprint » et « Montée »

## 1. Objectif

Montrer les segments et les arches de bonus dans la scène 3D : une ligne au sol et un portique au départ et à l'arrivée de chaque segment, les panneaux qui l'annoncent, et les arches de bonus aux positions fixes du core. Décision du 27 octobre : **code d'abord, sans maquette** ; le rendu se valide ensemble à la recette (T11).

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md` §3.1, §3.3 et §6.
2. `docs/contracts/world_format_v1.md` §8 bis (couche `segments.json`) ; `docs/contracts/ipc_v1.md` révision 1.4 (champ `segment`).
3. Cahier `LOT_T6_bonus.md` (`ArchSchedule` : arche tous les 5 km, répétée à chaque tour d'une boucle).
4. Code de l'engine : `engine/scripts/route_data.gd` (lecture du `.world`), `world_streamer.gd`, `road_builder.gd`, `roadside_props.gd`, `banner.gd`, `climb_detector.gd` (montées détectées par l'engine pour le décor, lot P14), `quality_presets.gd`.

## 3. Prérequis

T1 et T3 (livrés) ; T7 pour la position des arches dans la séance. Le rendu des lignes et des panneaux ne demande que la couche `segments.json` et peut commencer tout de suite.

## 4. Travail demandé

- **Lecture :** `route_data.gd` lit `segments.json` si le manifeste la déclare (version de couche `1.x`, champ inconnu ignoré, fichier invalide ignoré avec un message dans la console).
- **Modèle sans affichage** `engine/scripts/segment_markers_model.gd`, testé par `engine/tests/unit/test_segment_markers_model.gd` : positions (`s`, côté, orientation) des lignes, portiques et panneaux ; panneaux « Sprint dans 1 km », « 500 m », « 200 m » avant un sprint ; « Montée de 2e catégorie, 4,2 km à 6,1 % » au pied d'une montée, « 1 km », « 500 m » avant le sommet ; arches de bonus tous les `arch_every_m`, lu dans `~/OpenRide/powerups.toml` (section `[obtain]`) comme le fait le core, 5 000 m sans fichier, 0 : aucune arche (même règle que `ArchSchedule` de T6, vérifiée par un vecteur de test commun), répétées à chaque tour d'une boucle ; aucune arche quand l'option « Bonus » est coupée (`[powerups] mode = "off"`, T7) ou en ERG.
- **Rendu** `engine/scripts/segment_markers.gd` : ligne peinte au sol, portique au départ et à l'arrivée (vert pour un sprint, à pois rouges pour une montée), panneaux en bord de route, arche de bonus distincte ; objets créés par tronçon avec le streaming existant, sans nouveau coût quand aucun segment n'est proche.
- **Décor :** les spectateurs de P15 et les bannières de sommet suivent la couche `segments` quand elle existe (une seule source pour les montées), et `climb_detector.gd` sinon.
- **Budget :** moins de 0,3 ms par image et moins de 50 nœuds actifs sur la GTX 1060 en qualité basse ; mesure par `perf_probe.gd`.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/segment_markers_model.gd`, `engine/scripts/segment_markers.gd`, leurs tests.
- **Modifiés :** `route_data.gd`, `world_streamer.gd`, `living_decor.gd` (source des montées), `main.gd` (ajout du nœud).
- **Interdits :** le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Tests Godot sans écran verts, dont le nouveau modèle (positions des panneaux sur le parcours de démonstration, boucle, parcours sans couche `segments`).
2. Parcours de démonstration : portiques de la montée et du sprint visibles aux bonnes positions (contrôle visuel à la recette T11).
3. Un `.world` sans couche `segments` s'affiche comme aujourd'hui.
4. Budget de rendu tenu (`perf_probe`).

## 8. Hors périmètre

- HUD (T9 et T15), menus (T10).

## 9. Livraison (27 octobre 2026, code ; validation sur le PC)

- `route_data.gd` lit la couche `segments` quand le manifeste la déclare (`segments`, `segments_present`) : version de couche `1.x`, champ inconnu ignoré, fichier invalide ignoré avec un message dans la console, route chargée dans tous les cas.
- Nouveau modèle `engine/scripts/segment_markers_model.gd` : portiques et lignes de départ et d'arrivée, panneaux (sprint dans 1 km, 500 m, 200 m ; pied de montée « Montée de 4e catégorie » et « 1,5 km à 3,6 % » ; sommet dans 1 km et 500 m), arches de bonus, lecture de `[obtain] arch_every_m` dans `~/OpenRide/powerups.toml`, montées de la couche au format de `climb_detector.gd`, fenêtre autour de la caméra par recherche dichotomique.
- Nouveau rendu `engine/scripts/segment_markers.gd`, créé par `main.gd` : portique (banderole verte pour un sprint, blanche à pois rouges pour une montée), ligne peinte au sol (blanche au départ, en damier à l'arrivée), panneaux, arche violette lumineuse. Seules les marques à moins de 400 m devant et 30 m derrière la caméra sont en scène (aucun nœud quand rien n'est proche) ; exagération du relief (lot Q2) appliquée comme à la route.
- `living_decor.gd` : spectateurs, panneaux de col et chiffres peints suivent les montées de la couche `segments` quand elle existe (`climbs_of`), sinon `climb_detector.gd`.
- Choix faits :
  - arches affichées seulement quand la trame `state` porte le champ `powerup` (SIM, option « Bonus » active, séance en cours) : l'engine suit ainsi l'ERG et l'option sans lire `config.toml` et sans nouveau champ de contrat ;
  - panneaux de la série T à **gauche** de la route, pour ne pas se superposer aux panneaux d'approche de P14 (à droite, « Sommet à 1 km ») ;
  - montée qui commence au départ d'un parcours ouvert : panneau de pied posé 15 m après la ligne ; sur une boucle, les panneaux d'approche passent au tour précédent ;
  - fenêtre glissante gérée par `segment_markers.gd` plutôt que par les tronçons de `world_streamer.gd` (quelques marques par kilomètre au plus) : `world_streamer.gd` reste inchangé ;
  - `powerups.toml` refusé par le core pour une autre clé que `arch_every_m` (par exemple un `factor` hors bornes) : le core repasse à 5 000 m, l'engine garde la valeur du fichier. Cas rare, signalé ici ; un fichier valide donne les mêmes arches (vecteurs partagés `engine/tests/data/arch_schedule_vectors.json`, vérifiés aussi par `core/tests/test_powerups.py`).
- Tests : `engine/tests/unit/test_segment_markers_model.gd` (à lancer sur le PC : Godot n'est pas disponible dans l'environnement cloud) ; `core/tests/test_powerups.py` (vecteurs des arches).
- Reste à faire sur le PC : `engine/tests/run_engine_tests.sh` complet, mesure `perf_probe` (moins de 0,3 ms par image, moins de 50 nœuds actifs en qualité basse sur la GTX 1060), contrôle visuel à la recette T11.

## 10. Portiques redessinés (29 octobre 2026, demande « améliorer le design des gates »)

- Une seule forme pour tous les portiques : arche gonflable (tube à coins arrondis, un maillage partagé refait seulement quand la largeur de route change), lestée de deux blocs, bandeau suspendu (titre en capitales, sous-titre plus petit), deux drapeaux-plumes, ligne au sol. Les arches de bonus prennent la même forme, en violet lumineux.
- Styles (`style` des marques de `segment_markers_model.items`) : `sprint_start` / `sprint_finish` vert à bandes blanches (« SPRINT », « FIN DU SPRINT ») ; `climb_start` blanc à pois rouges, bandeau blanc (« MONTÉE », nom et catégorie) ; `summit` mêmes pois, bandeau rouge (« SOMMET ») ; `route_start` bleu (« DÉPART ») ; `route_finish` en damier (« ARRIVÉE ») ; `route_line` en damier sur une boucle (« DÉPART · ARRIVÉE »). Toute arrivée a une frise en damier sous le bandeau et une ligne en damier de 1 m au sol ; tout départ, une ligne blanche.
- Nouveau : portiques de départ et d'arrivée du parcours (sauf monde ouvert, `route_gates` faux). Un portique de segment à moins de 25 m (`MERGE_M`) de l'un d'eux n'est pas doublé : le portique du parcours prend son nom en sous-titre (démo : « DÉPART / Montée 1 · 4e catégorie »).
- Coût : par portique, 13 nœuds au plus (contre 6), environ 600 triangles pour le tube, aucune ombre portée. Vitrine `engine/tests/vitrine_portiques.gd` (captures avant/après en 1920×1080 et 1024×600, CSV des triangles, appels de dessin et nœuds) ; images par seconde mesurées sur la GTX 1060 par la file des mesures du PC.
- Jingles des portiques : voir LOT_T17 §10.
