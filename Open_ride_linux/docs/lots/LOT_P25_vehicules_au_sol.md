# Lot P25 – Véhicules au sol : voitures détaillées, camions, autocars, motos, routes voisines, tracteurs aux champs, phares

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Véhicules au sol : voitures détaillées, utilitaires, camions, autocars et motos, circulation des routes voisines, tracteurs qui hersent les champs, phares dans la brume, sous la pluie ou au soleil bas | GDScript + shader | P13, P17, P22, Y14 | Moyenne | **Livré le 28 octobre**, séance sur le PC à faire |

## 1. Objectif

Demande du propriétaire du 27 octobre (« ça manque de vie : animaux, oiseaux, véhicules sur terre et dans le ciel »), quatrième lot de la deuxième vague du décor vivant (P22 à P27). Les véhicules de P13 sont des pavés posés sur des cylindres, de trois sortes seulement, et ne roulent que sur la route du cycliste (remarque du propriétaire du 27 octobre : « véhicules trop simplistes »). Ce lot :

- refait les véhicules en maillages détaillés construits par code (profil de caisse, passages de roue, vitres, phares, feux, calandre, pare-chocs, rétroviseurs, plaques) et en ajoute quatre sortes : utilitaire, camion porteur, autocar, moto et son pilote ;
- fait rouler des véhicules sur les routes voisines de la couche `roads` (format 1.5, P22), avec leur sens, leurs voies et leur vitesse ;
- met un tracteur à herser dans des champs cultivés (`farmland`) ;
- allume les phares de tous les véhicules dans la brume, sous la pluie ou au soleil bas.

## 2. À lire

1. `docs/lots/LOT_P13_vehicules.md`, `docs/lots/LOT_P22_pres_champs_routes_voisines.md`, le lot Y14 (Builder de `people_mesh.gd`).
2. Code : `engine/scripts/traffic_model.gd`, `traffic_renderer.gd`, `living_decor.gd`, `osm_streamer.gd`, `fauna_placer.gd` (`_open_areas`), `weather_model.gd`, `theme_render_params.gd` (`sky_params`).

## 3. Prérequis

P13, P17, P22 (couche `roads`, terrains ouverts), Y14 (Builder des maillages construits par code).

## 4. Travail demandé

- **`vehicle_mesh.gd`** (nouveau) : huit maillages, sol à y = 0, avant vers -z : berline `car_a`, citadine haute `car_b`, utilitaire `van`, camion porteur `truck` (cabine et caisse), autocar `bus` (bande de vitres, bande de couleur, girouette, climatisation), moto `moto` (pilote penché, casque et visière), tracteur `tractor` (capot, cabine vitrée, garde-boue, roues arrière à crampons, gyrophare) et tracteur à herse `tractor_field`. Les caisses sont un profil de côté extrudé en largeur, rétréci au-dessus de la ligne de caisse, avec les passages de roue découpés. Zones de couleur (CUSTOM0.x) : peinture, vitre, noir, métal, phare, feu arrière, clair, seconde couleur. `build_body` (sans roues), `build_wheel`, `wheel_list`, `build_full` (roues fixes), palettes `paint` (8 couleurs de voiture, 4 de tracteur, 4 d'autocar) et `second`.
- **`shaders/vehicle.gdshader`** (nouveau) : couleur, rugosité et reflets par zone ; phares en émission quand `lights` = 1, feux arrière toujours un peu, plus vifs phares allumés. Mode `instanced` (MultiMesh) : peinture en couleur d'instance, phares dans INSTANCE_CUSTOM.x.
- **`traffic_model.gd`** : `KINDS` à sept sortes avec leur taille hors tout (celle des maillages, rétroviseurs compris), leur part des tirages et leur plage de vitesse ; `pick_kind(u)` ; huit couleurs ; `headlights(weather_eval, sun_elevation_deg)` : vrai pour `fog_boost` ≥ 0,3, `rain` ≥ 0,2 ou un soleil à 8° ou moins. Mêmes garanties qu'en P13 (écart latéral de 1,5 m, jamais de dépassement face à un véhicule).
- **`traffic_renderer.gd`** refait : pool de 8 véhicules, une caisse et 6 roues par case, maillages construits une fois par sorte, un matériau par case (peinture, seconde couleur, phares), roues qui tournent chacune selon son rayon, son du passage plus grave pour un camion ou un autocar et plus aigu pour une moto (`pitch_scale`), moteur pour le tracteur ; `set_lights(on)`.
- **`road_traffic_model.gd`** (nouveau) : chemins des routes voisines (`road_paths`) et des champs (`field_paths`), calculés dans la tâche de fond d'un tronçon. Sur une route, un véhicule tous les SPACING_M en moyenne (160 m sur une autoroute, 450 m sur une route secondaire, 900 m dans une rue, 2,5 km sur une piste), sortes tirées d'après MIX (que des tracteurs sur une piste), sens, voie à droite du sens, couleur ; une vitesse par voie, celle de la route (80 à 100 %) ou celle du plus lent, donc jamais de rattrapage ; chaque véhicule disparaît entre deux passages et grandit sur 6 m aux bouts. Un champ cultivé de 2 ha au moins porte, quatre fois sur dix (`FIELD_SHARE`, tiré de son identifiant), un tracteur qui le herse en aller et retour à 2,2 m/s, rangs tous les 9 m, à 8 m du bord, posés sur le sol. Horloge figée en pause ; au plus `distant_vehicles` véhicules, les plus proches de la caméra à moins de 900 m, triés toutes les 0,5 s.
- **`road_traffic_renderer.gd`** (nouveau) : un MultiMesh par sorte (`build_full`), sans ombre, caché au-delà de 1 000 m.
- **`osm_streamer.gd`** : `traffic_enabled` ; la tâche de fond lit la couche `roads` (relief exagéré appliqué comme pour l'eau) et les champs, et met les chemins dans `extras.traffic` de `chunk_loaded`.
- **`living_decor.gd`** : budgets, chemins des tronçons chargés et retirés, mise à jour figée en pause, phares de tous les véhicules ; `test_info` donne `distant_vehicles` et `headlights`.
- **`quality_presets.gd`** : clé `distant_vehicles` : 6, 12 et 24 en `low`, `medium` et `high`.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/vehicle_mesh.gd`, `road_traffic_model.gd`, `road_traffic_renderer.gd`, `engine/shaders/vehicle.gdshader` ; `engine/tests/unit/test_vehicle_mesh.gd`, `test_road_traffic_model.gd`, `engine/tests/render/test_vehicle_render.gd`.
- **Modifiés :** `engine/scripts/traffic_model.gd`, `traffic_renderer.gd`, `osm_streamer.gd`, `living_decor.gd`, `quality_presets.gd` ; `engine/tests/unit/test_traffic_model.gd`, `test_living_decor.gd`, `test_quality_presets.gd`, `engine/tests/perf_budgets.json`, `engine/tests/README.md`, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** le compilateur, le core, les contrats, `crowd_renderer.gd`, `people_mesh.gd` (fil des personnages ; ses cylindres ont les bouts tournés à l'envers, `vehicle_mesh.gd` a donc son propre `_cyl`).

## 6. Modifications de contrat autorisées

Aucune : ni IPC, ni format, ni thème, ni touche. Désactivé avec le reste par `[render] living = false` ; sans couche `roads` ni champ, il n'y a que la circulation du parcours.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Maillages : huit sortes de 2 000 triangles au plus, à la taille de `traffic_model.gd` (largeur à 5 cm), posées sur le sol, phares devant, feux derrière, toutes les zones, faces dans le sens de leurs normales, roues centrées sur leur axe.
3. Circulation du parcours : les garanties de P13 sur 13 graines ; les sept sortes tirées sur 200 graines, vitesses dans leur plage ; chaque sorte habillée (caisse, roues, peinture) ; phares éteints par beau temps, allumés dans la brume, sous la pluie ou au soleil bas.
4. Routes voisines et champs : une rue de 8 m et un chemin piéton écartés ; autoroute à sens unique sur trois voies sans tracteur ; piste à tracteurs, dans un seul sens ; une vitesse par voie ; tracteur dans son champ, sur le sol, en aller et retour à 2,2 m/s ; en deux minutes, au plus le budget, à moins de 900 m, chacun à droite de son sens et penché comme la route, jamais deux au même endroit ; les plus proches gardés ; déterministe ; figé en pause ; retiré avec son tronçon ; mise à jour sous 0,15 ms et affichage sous 0,1 ms par image.
5. Rendu : même peinture proche et en MultiMesh, vitres sombres, phares allumés qui brillent dans le noir.
6. Décor vivant complet : chemins des tronçons chargés, véhicules lointains jamais sur le parcours, tracteur au champ, phares sous la pluie, figés en pause, coût total sous 2 ms par image (`living_decor_frame`).

**Sur le PC cible (le propriétaire) :** séance sur un parcours de campagne compilé avec les couches OSM (`roads` comprise) : voitures, utilitaires, camions, autocars et motos qui croisent et doublent, circulation sur les routes voisines, un tracteur dans un champ ; séance avec le thème de pluie ou de brume : phares allumés. Perte de moins de 1 image/s en `low` (P27 fera la mesure complète).

## 8. Hors périmètre

- Véhicules dans le ciel (avions, hélicoptère, parapentes, montgolfières) : P26.
- Feux qui éclairent la route (lumières dynamiques), clignotants, poussière du tracteur, cultures dessinées dans les champs : plus tard (P27 ou série Y).
- Nuit (P19, version 2.0) : `headlights` prendra l'heure quand elle existera.

## 9. Livraison

- Mesures ici (machine partagée, Godot 4.3 sans écran) : circulation du parcours en 0,001 ms par image ; routes voisines en 0,07 à 0,09 ms pour 15 véhicules, affichage en 0,03 ms ; décor vivant complet en 0,49 ms par image en `high`.
- Tests : `test_vehicle_mesh.gd` (11 vérifications), `test_road_traffic_model.gd` (24), `test_traffic_model.gd` (21), `test_living_decor.gd` (32), `test_quality_presets.gd` (24), `render/test_vehicle_render.gd` (6).
- Reste sur le PC cible : la séance décrite au §7.
