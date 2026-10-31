# Lot P29 – Bateaux : voiliers, barques et pédalos sur les lacs, péniches et canoës sur l'eau courante, navires en mer

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Bateaux : voiliers, barques et pédalos sur les lacs, péniches sur les canaux, canoës et kayaks sur les rivières, ferry et porte-conteneurs en mer (avec U9), sillages, diesel et corne de brume | GDScript + shader | P12, P25, P26, Y14 (U9 pour la mer) | Moyenne | **Livré le 28 octobre**, séance sur le PC à faire |

## 1. Objectif

Ce lot répond à la demande du propriétaire du 28 octobre : « Il faudra des bateaux pour lacs et mers ». Il fait partie de la deuxième vague du décor vivant (P22 à P29) et vient après le ciel (P26) et les cyclistes (P28), avant l'intégration de toute la vague (P27).

Aujourd'hui, les lacs, les étangs, les rivières et les canaux de la couche `water` sont des surfaces vides qui scintillent (P12). Ce lot y met des bateaux, de loin et sans en faire trop :

- sur les lacs et les réservoirs, des voiliers, des barques à rames et, près du bord, des pédalos ;
- sur les canaux et les grandes rivières, des péniches lentes ; sur les rivières, des canoës et des kayaks ;
- en mer, des voiliers près de la côte, un ferry et un porte-conteneurs au large. Le code est prêt, mais l'engine ne lira la mer (aire `sea`) qu'avec le lot U9, version 3.0.

## 2. À lire

1. `docs/lots/LOT_P12_eoliennes_drapeaux_eau.md`, `LOT_P25_vehicules_au_sol.md` (maillages et shader des véhicules, chemins calculés dans la tâche de fond d'un tronçon), `LOT_P26_ciel.md`, `LOT_Y14_personnages_animaux.md` (Builder de `people_mesh.gd`), `LOT_U9_mer_et_plages.md`.
2. Contrat : `docs/contracts/world_format_v1.md` §8 (couche `water` : `lines` `river`, `stream`, `canal` avec `width_m` ; `areas` `lake`, `pond`, `reservoir`, `sea` avec `level_y`).
3. Code : `engine/scripts/osm_streamer.gd` (lecture de la couche `water`, `cut_lines_at_road`), `road_traffic_model.gd` (modèle suivi), `vehicle_mesh.gd`, `sky_mesh.gd`, `shaders/vehicle.gdshaderinc`, `living_decor.gd`, `quality_presets.gd`, `sound_player.gd`.

## 3. Prérequis

P12, P25, P26 et Y14. Pour la mer : U9 (lecture de l'aire `sea` par `osm_layers.gd`, mer animée).

## 4. Travail demandé

- **`boat_mesh.gd`** (nouveau) : maillages construits par code avec le Builder de `people_mesh.gd` et les pièces de `vehicle_mesh.gd` et `sky_mesh.gd`, dans les zones de couleur des véhicules. Ligne de flottaison à y = 0, avant vers -z.
  - Les coques sont faites de sections en travers le long de z (demi-largeur, pont, quille). L'étrave est pointue, l'arrière est à tableau ou pointu. Les œuvres vives sont dans la seconde zone, sous la flottaison.
  - Huit sortes :
    - `sailboat` : voilier de 8 m (rouf, cockpit, quille, mât, foc, barreur) ; la grand-voile et sa bôme forment le maillage `sail`, qui pivote autour du mât ;
    - `rowboat` : barque de 4 m, avec ses bancs, son rameur et ses avirons ;
    - `pedalo` : pédalo de 2,6 m, avec son toit et deux personnes ;
    - `canoe` : canoë de 5 m et deux pagayeurs ;
    - `kayak` : kayak de 3,6 m, son pagayeur et sa pagaie double ;
    - `barge` : péniche de 38,5 m, avec ses cales bâchées, son logement, sa timonerie et son pavillon ;
    - `ferry` : ferry de 120 m, avec ses ponts vitrés, sa cheminée et ses canots ;
    - `cargo` : porte-conteneurs de 180 m, avec ses piles de conteneurs de couleur et son château.
  - Sillage `wake` : ruban à plat de longueur 1.
  - Personnes : pièces simples (gilet de la seconde couleur, peau, jambes sombres), comme le motard de `vehicle_mesh.gd`. Le shader gagne deux zones, peau (8) et bois (9).
  - Palettes : `colors(kind, i)`.
- **`shaders/wake.gdshader`** (nouveau) : écume sans éclairage, avec brouillard. Elle s'efface vers son bout et sur ses bords, et ses deux bras sont plus marqués que le milieu.
- **`boat_model.gd`** (nouveau, sans nœud) : les chemins sont calculés dans la tâche de fond d'un tronçon (`water_paths(areas, lines, road)`).
  - **Plans d'eau** `lake`, `reservoir` (et `sea` quand U9 la passe) : chaque bateau tourne sur une boucle en ellipse. Toute la boucle reste dans l'eau, à 15 m au moins du bord, des îles et de 25 m de la route (40 m du bord pour la mer). Les boucles sont à 20 m au moins l'une de l'autre.
    - Voiliers : un pour 8 ha, au plus 6, sur 5 ha au moins ; boucle de 40 à 120 m, à 2,2 m/s.
    - Barques : une pour 4 ha, au plus 3, sur 1 ha au moins ; boucle de 15 à 40 m, à 0,8 m/s.
    - Pédalo : un lac de 2 ha au moins en a un une fois sur deux, à moins de 60 m du bord ; boucle de 8 à 15 m, à 0,6 m/s.
    - Étang (`pond`) : une barque, une fois sur trois, s'il fait 0,5 ha au moins.
  - **Eau courante** (lignes coupées à la route, comme l'eau affichée) :
    - péniches sur un `canal` de 10 m de large au moins ou une `river` de 30 m au moins : une tous les 2 km en moyenne, à 2 m/s, dans un sens ou l'autre, à un quart de la largeur sur la droite de l'axe ;
    - canoës et kayaks sur une `river` de 8 m au moins : un tous les 1,5 km, à 1,2 m/s dans le sens du courant (sens des points) ou 0,7 m/s à contre-courant, près du bord droit ;
    - rien sur un `stream`.

    Sur une voie, tous les bateaux d'un même sens vont à la même vitesse et ne se rattrapent jamais. Ils disparaissent entre deux passages et grandissent sur 8 m aux bouts.
  - **Mer** (branchée par U9) : des voiliers à moins de 2 km de la côte. Des lignes droites de 4 à 6 km, à 3 à 6 km au large, une pour 150 km² de mer, au plus 4 :
    - le ferry y repasse toutes les 15 min ;
    - le porte-conteneurs, toutes les 10 min, à 8 m/s.

    Les navires sont à leur vraie place et suivent le brouillard.
  - **Sur l'eau** : roulis, tangage et pilonnement selon la sorte, plus forts par vent fort et en mer. Le voilier gîte sous le vent, davantage vent de travers, et sa bôme passe du côté sous le vent (`sail`). Le sillage est de 10 s de route pour un voilier, 14 s pour une péniche et 25 s pour un navire, sans sillage pour les petits bateaux.
  - **Temps** : par grand vent (force > 0,7), les voiliers, les barques et les pédalos sont rentrés. Sous la pluie (`rain` ≥ 0,3), ce sont les pédalos, les canoës et les kayaks qui rentrent. Les péniches et les navires naviguent par tous les temps.
  - **Règles générales** :
    - déterministe (identifiant du plan d'eau ou du cours d'eau) ;
    - horloge figée en pause ;
    - un plan d'eau vu par deux tronçons ne compte qu'une fois.
  - **Budget** : au plus `boats` bateaux et `MAX_AT_ONCE` de chaque sorte. Les plus proches de la caméra sont gardés, à moins de 1 500 m (8 km pour les navires en mer), triés toutes les 0,5 s.
- **`boat_renderer.gd`** (nouveau) :
  - Petits bateaux : un MultiMesh par sorte, sans ombre, en mode `instanced`.
  - Voiliers, péniches, ferry et porte-conteneurs : `MAX_AT_ONCE` nœuds par sorte, avec leur matériau (couleurs, feux allumés avec les phares de P25), leur sillage et la grand-voile du voilier.
  - Lecteurs 3D sur le bus Ambience : le diesel des péniches (`barge_engine`, audible à 300 m) et la corne du ferry, une fois par passage (`ship_horn`).
  - Tous les nœuds sont créés au démarrage.
- **`sound_player.gd`** : `barge_engine` (en boucle) et `ship_horn` (joué une fois) sont synthétisés comme les autres sons. On peut les remplacer par `~/OpenRide/Sounds/<sorte>.ogg`.
- **`osm_streamer.gd`** : `boats_enabled` ; la tâche de fond qui lit la couche `water` calcule les chemins des bateaux sur l'eau affichée (lignes coupées à la route, relief exagéré appliqué) et les met dans `extras.boats` de `chunk_loaded`.
- **`living_decor.gd`** : il règle le budget et ajoute ou retire les chemins des tronçons. Il passe le vent et la météo évalués. La mise à jour est figée en pause et les feux s'allument avec les phares. `test_info` donne `boats`.
- **`quality_presets.gd`** : clé `boats` de `LIVING`, 4, 8 et 16 en `low`, `medium` et `high`.

## 5. Fichiers concernés

- **Nouveaux :**
  - `engine/scripts/boat_mesh.gd`, `boat_model.gd`, `boat_renderer.gd`, `engine/shaders/wake.gdshader` ;
  - `engine/tests/unit/test_boat_model.gd`, `engine/tests/render/test_boat_render.gd`.
- **Modifiés :**
  - `engine/scripts/osm_streamer.gd`, `living_decor.gd`, `quality_presets.gd`, `sound_player.gd`, `vehicle_mesh.gd` (zones peau et bois), `engine/shaders/vehicle.gdshader` et `vehicle.gdshaderinc` ;
  - `engine/tests/unit/test_living_decor.gd`, `test_quality_presets.gd`, `test_sound_player.gd`, `engine/tests/perf_budgets.json` (lignes `boats_frame` et `boats_view_frame`), `engine/tests/README.md` ;
  - `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** `osm_layers.gd` (la lecture de la mer revient à U9), `people_mesh.gd`, `crowd_renderer.gd`, `water_mesh.gd` (surface de l'eau inchangée), le compilateur, le core, les contrats.

## 6. Modifications de contrat autorisées

Aucune : ni IPC, ni format `.world`, ni thème, ni touche. Les bateaux sont désactivés avec le reste par `[render] living = false`. Sans couche `water`, il n'y a pas de bateau.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Maillages :
   - longueur à 6 % près ;
   - largeur hors tout au moins celle de la coque ;
   - 2 000 triangles au plus (6 000 pour le ferry et le porte-conteneurs) ;
   - coque de part et d'autre de la flottaison ;
   - faces dans le sens de leurs normales.
3. Chemins :
   - un lac de synthèse de 40 ha avec une île porte de 3 à 6 voiliers et de 1 à 3 barques ; pendant 10 min, ils restent tous sur l'eau, à 15 m du bord et de l'île, jamais à moins de 20 m l'un de l'autre ;
   - pédalos près du bord sur une partie des lacs ;
   - aucune boucle près d'une route qui traverse le lac ;
   - un étang de 0,3 ha et un ruisseau n'ont rien ; un étang de 0,8 ha a une barque une fois sur trois environ ;
   - canal de 15 m : péniches dans les deux sens, chacune sur sa moitié droite ;
   - rivière de 12 m : canoës et kayaks plus rapides dans le sens du courant ;
   - grande rivière : péniches et canoës ; canal de 8 m : rien ;
   - mer passée directement au modèle : voiliers près de la côte, ferry et porte-conteneurs au large, et le ferry passe puis repart.
4. Comportement :
   - la bôme du voilier est sous le vent et sa gîte est plus forte par vent fort ;
   - par grand vent et sous la pluie, les bons bateaux sont rentrés ;
   - avec un budget de 3, ce sont les 3 plus proches ;
   - déterministe, figé en pause, retiré avec son tronçon ;
   - mise à jour sous `boats_frame` (0,15 ms) et affichage sous `boats_view_frame` (0,1 ms) par image.
5. Rendu :
   - la coque est à la couleur de sa palette et le plancher de la barque en bois ;
   - le sillage est marqué à la poupe et s'efface vers son bout.
6. Décor vivant complet : barque, pédalo et péniches chargés avec les tronçons, jamais sur le parcours, feux allumés sous la pluie, figés en pause, coupés avec `living = false`.

**Sur le PC cible (le propriétaire) :** séance sur un parcours qui longe un lac et un canal, compilé avec la couche `water`. On doit voir des voiliers, une barque et une péniche qui passe avec son moteur, et aucun bateau sur la berge. La perte doit rester sous 0,5 image/s en `low`. P27 fera la mesure complète. La mer viendra avec U9.

## 8. Hors périmètre

- Lecture de la mer par l'engine, vagues, écume et plages : U9, version 3.0. P29 prépare seulement les navires.
- Bords tirés au près (les voiliers tournent sur leur boucle), avirons et pagaies animés, ports, pontons, bateaux amarrés, planches à voile : plus tard si le propriétaire les demande.
- Écluses des canaux : les péniches disparaissent en douceur à leurs bouts, comme les véhicules lointains de P25.
- Feux de navigation de nuit : P19, version 2.0.

## 9. Livraison

- Mesures sur la machine partagée (Godot 4.3 sans écran), avec 16 bateaux sur un lac, un canal et une rivière : modèle en 0,15 ms par image et affichage en 0,05 ms.
- Tests : `test_boat_model.gd` (29 vérifications), `render/test_boat_render.gd` (3), `test_living_decor.gd` (36), `test_quality_presets.gd` (26), `test_sound_player.gd` (17).
- Reste à faire sur le PC cible : la séance décrite au §7.
