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
- **Modèle sans affichage** `engine/scripts/segment_markers_model.gd`, testé par `engine/tests/unit/test_segment_markers_model.gd` : positions (`s`, côté, orientation) des lignes, portiques et panneaux ; panneaux « Sprint dans 1 km », « 500 m », « 200 m » avant un sprint ; « Montée de 2e catégorie, 4,2 km à 6,1 % » au pied d'une montée, « 1 km », « 500 m » avant le sommet ; arches de bonus tous les `arch_every_m`, lu dans `~/OpenRide/powerups.toml` (section `[obtain]`) comme le fait le core, 5 000 m sans fichier, 0 : aucune arche (même règle que `ArchSchedule` de T6, vérifiée par un vecteur de test commun), répétées à chaque tour d'une boucle ; aucune arche quand l'option « Bonus » est coupée (`[powerups] enabled`, T7) ou en ERG.
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
