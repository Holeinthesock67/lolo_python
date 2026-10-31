# Lot E4 – Bâtiments, forêts OSM, eau et sons du parcours

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Bâtiments, forêts OSM, eau et sons du parcours | GDScript | E3, K3, K4, L1, L2, L5 (livrés) | Grande | **Livré le 24 octobre** (PR #91, recette visuelle et sonore sur la GTX 1060 à faire) |

## 1. Objectif

Afficher les couches facultatives du `.world` qui viennent d'OpenStreetMap (SRS §8 « Modules ajoutés ensuite », §10, §13 sprints 5 et 6) : bâtiments extrudés, forêts et vergers, rivières et lacs, et faire entendre le vent, la roue libre et les points d'intérêt. Les calculs sont déjà faits sans affichage par K3, K4, L1, L2 et L5 : ce lot les **branche dans la scène**, par tronçons, sans à-coups et dans le budget de la GTX 1060.

Recette du sprint 5 (SRS §13) : traverser un village sans trous ni artefacts, à 30 images par seconde au moins en préréglage `low` (objectif 55 sur la GTX 1060, comme E3).

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/REVUE_E2_2026-10-24.md`, `docs/lots/LOT_E3_ciel_arbres_hud.md` (le gestionnaire d'arbres et le budget d'instances viennent de là).
2. `docs/SRS_v1.1.md` §8 (bâtiments, audio, performance), §10 (couches), §13 (sprints 5 et 6).
3. `docs/contracts/world_format_v1.md` §2 (manifeste), §3 (repère), §6 (bâtiments), §7 (végétation), §8 (points d'intérêt et eau), §9 (palettes du thème), §10 (couche absente, fichier invalide).
4. Cahiers livrés : `LOT_I3_osm_batiments_forets.md`, `LOT_I4_osm_poi_eau.md`, `LOT_K3_placement_vegetation.md`, `LOT_K4_lecture_couches_osm_godot.md`, `LOT_L1_maillage_batiments.md`, `LOT_L2_maillage_eau.md`, `LOT_L5_modele_sonore.md`.
5. Code : `engine/scripts/osm_layers.gd`, `engine/scripts/building_mesh.gd`, `engine/scripts/water_mesh.gd`, `engine/scripts/vegetation_placer.gd`, `engine/scripts/sound_model.gd`, `engine/scripts/world_streamer.gd`, `engine/tests/make_osm_world.py`, `engine/tests/test_osm_layers.gd`.

## 3. Prérequis

- E3 fusionné : arbres par tuile (`tree_renderer.gd`), table unique des préréglages, mesure `[perf-rendu]`.
- K3, K4, L1, L2 et L5 livrés (c'est le cas sur `main`).
- Données : `engine/tests/make_osm_world.py` (K4) pour les tests ; une trace réelle compilée avec `openride-compiler add-layer` (I3, I4) qui traverse un village, pour la recette.

## 4. Travail demandé

### 4.1 Chargement des couches OSM par tronçons

- Les couches présentes sont lues dans le manifeste (`layers_present` de K4) ; une couche absente, un fichier absent ou invalide ne donne aucune erreur Godot (format §10), seulement une ligne de journal par tronçon.
- **Fenêtre :** tronçons donnés par `chunks_for_window` (K4) sur la même fenêtre que le ruban de route (E1, réglée par le préréglage depuis E3). Les tronçons sortis de la fenêtre sont libérés tout de suite.
- **Tâches de fond :** lecture (`load_chunk`) et maillage (`building_mesh.build`, `water_mesh.build_lines`, `build_areas`) dans `WorkerThreadPool` ; création des `ArrayMesh` et des nœuds sur le fil principal, dans le budget `MAX_NEW_PER_FRAME` d'E1, partagé avec route, terrain et arbres.
- **Un tronçon = au plus trois nœuds** : bâtiments, cours d'eau, plans d'eau (un `ArrayMesh` chacun), pour garder peu d'appels de dessin.

### 4.2 Bâtiments (format §6, L1)

- Matériau unique `StandardMaterial3D` avec couleur de sommet (couleurs de L1 tirées des palettes du thème), rugosité élevée, ombres portées seulement à l'intérieur de la distance d'ombre du préréglage.
- **Pied des bâtiments :** `base_y` est le minimum du terrain fin sous l'empreinte. Loin de la caméra, le bâtiment repose sur une tuile lointaine, plus grossière et abaissée de 2 m (E1) : il paraîtrait flotter. Les murs descendent donc d'une **jupe de 3 m sous `base_y`**, cachée sous le sol. Ajout à faire dans `building_mesh.gd` (paramètre facultatif, défaut 0, pour ne pas casser les tests de L1).
- **Distance d'affichage :** `visibility_range_end` par tronçon selon le préréglage (`low` 1 500 m, `medium` 2 500 m, `high` 4 000 m ; constantes à ajouter à `quality_presets.gd`).
- `roof: "gabled"` est dessiné en toit plat (comportement de L1), compté dans le rapport.

### 4.3 Forêts OSM (format §7, K3 et E3)

- Pour chaque tuile proche, les polygones `vegetation` des tronçons qui la touchent sont passés à `place_tile(..., areas)` ; l'affichage, les niveaux de détail et le budget sont ceux d'E3, sans second chemin de rendu.
- **Zones OSM et arbres au hasard en dehors** (choix du propriétaire, 24 octobre) : les zones OSM portent leurs arbres (K3 avec `areas`), et le bruit d'E3 sème aussi des arbres **hors de ces zones**, gardés avec une probabilité `p_region` qui dépend de la région. OSM est lacunaire en montagne : sans ce semis, une vallée mal cartographiée resterait nue.
  - **Réalisation sans toucher à K3 :** pour chaque tuile, deux appels à `place_tile`, l'un avec les zones OSM, l'autre avec `areas = []` (bruit). Les arbres du bruit qui tombent dans une zone OSM (trous exclus) sont retirés ; les autres sont gardés si un tirage déterministe, haché de leur position (même hachage que K3), est inférieur à `p_region(x, z)`.
  - **`p_region`** est le produit de trois facteurs, chacun dans [0, 1], calculés au centre de chaque tuile proche puis **interpolés de façon bilinéaire** entre centres, pour n'avoir aucune bordure nette entre tuiles :
    - couverture OSM : `f` est la part boisée OSM des 3 × 3 tuiles autour. Une région bien cartographiée (beaucoup de forêts OSM) a des trouées sans doute réelles (prés, champs), donc moins d'arbres au hasard : `1 − 0,8 × min(1, f / 0,4)` ;
    - habitat : `b` est la part de surface bâtie (empreintes de la couche `buildings`) des 3 × 3 tuiles. Pas d'arbres au hasard en plein village : `1 − min(1, b / 0,1)` ;
    - altitude : forêt qui s'éclaircit en approchant la limite des arbres, `smoothstep(treeline_m, treeline_m − 300 m, altitude)`.
  - **Couche `vegetation` absente ou vide** sur le parcours : `p_region` vaut le seul facteur d'altitude, et le résultat est alors celui d'E3 hors de la bande des 300 m sous la limite.
  - Les seuils (0,8 ; 0,4 ; 0,1 ; 300 m) sont des constantes en tête de `tree_renderer.gd`, à ajuster à l'écran ; la région n'est pas une donnée du `.world` ni du thème.
- `kind` : `wood`, `scrub`, `orchard` avec les densités de K3 ; les vergers en rangées ne sont pas demandés.

### 4.4 Eau (format §8, L2)

- **Matériau :** `StandardMaterial3D` opaque en `low` (bleu-vert foncé, rugosité 0,1, reflets du ciel d'E3) ; transparence légère permise en `medium` et `high` si la mesure le permet. Couleur en constante documentée : le thème v1 n'a pas de couleur d'eau (candidate pour la version 1.1 du format §9).
- **Rivières :** les rubans de L2 sont 5 cm au-dessus des points du compilateur. Sur une grille de terrain de 10 m, un ruban de 2 à 6 m peut passer sous une bosse du maillage : mesurer sur la trace de recette, et si besoin relever le ruban au maximum de (point du compilateur, surface du terrain dessinée) + 5 cm.
- **Lacs :** surface à `level_y`, îles découpées (L2). Pas de vagues ni de réflexion en temps réel.

### 4.5 Sons (SRS §8 « Audio », L5)

- **Lecteurs :** un `AudioStreamPlayer` pour le vent, un pour la roue libre, au plus 4 `AudioStreamPlayer3D` pour les points d'intérêt (`MAX_POI_SOURCES` de L5), réutilisés d'un point à l'autre (aucune création de nœud par image).
- **Pilotage :** volumes et hauteur viennent de `sound_model.gd` (`on_state`, `evaluate`) appelé à chaque trame d'état ; ce lot ne recalcule ni lissage ni hystérésis.
- **Sons générés au démarrage** dans des `AudioStreamWAV` en boucle, à graine fixe : vent (bruit filtré), roue libre (cliquetis), `church_bell` (partiels amortis), `river` (bruit grave), `livestock` (sonnailles), `village` (murmure grave). `viewpoint` n'a pas de son. Aucun fichier son n'est livré, donc pas de licence à gérer.
- **Remplacement facultatif :** un fichier `~/OpenRide/Sounds/<kind>.ogg` (ou `wind.ogg`, `freewheel.ogg`), s'il existe, remplace le son généré. Convention documentée dans `README.md` ; ce n'est pas un changement du format `.world`.
- Les bips des appuis du Click (déjà dans `main.gd`) et le bip ERG à T − 3 s (F2) restent sur leur propre lecteur, jamais coupés par les sons du parcours.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/osm_streamer.gd` (fenêtre des couches OSM, tâches, nœuds), `engine/scripts/sound_player.gd` (lecteurs et sons générés), `engine/tests/unit/test_sound_player.gd`, `engine/tests/test_osm_streamer.gd` (sur les données de `make_osm_world.py`, lancé par `run_engine_tests.sh`).
- **Modifiés :**
  - `engine/scripts/world_streamer.gd` (branchement d'`osm_streamer.gd`, budget par image partagé) ;
  - `engine/scripts/tree_renderer.gd` (zones OSM, règle du §4.3) ;
  - `engine/scripts/building_mesh.gd` (jupe sous `base_y`) et `engine/tests/unit/test_building_mesh.gd` ;
  - `engine/scripts/quality_presets.gd` (distance d'affichage des bâtiments, transparence de l'eau) ;
  - `engine/scripts/main.gd`, `engine/scenes/main.tscn` (nœuds des couches et du son) ;
  - `engine/tests/make_osm_world.py` (un village dense de 300 bâtiments et un lac à île, si absent) ;
  - `engine/tests/run_engine_tests.sh`, `engine/tests/README.md`, `README.md` (dossier `Sounds`) ;
  - `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne chacun).
- **Interdits :** `osm_layers.gd`, `water_mesh.gd`, `sound_model.gd`, `vegetation_placer.gd` (lecture seule ; un défaut trouvé est signalé), le core, le compilateur, les contrats.

## 6. Modifications de contrat autorisées

Aucune. La couleur de l'eau, les sons par `kind` et la règle de mélange bruit / OSM sont des constantes de l'engine, signalées comme candidates pour une version 1.1 du thème.

## 7. Critères d'acceptation

**Automatiques (intégration continue) :**
1. `engine/tests/run_engine_tests.sh` passe en entier ; `pytest` passe dans `core/` et `compiler/`.
2. Fenêtre : à `s` = 0 puis 2 500 m sur le monde de test, les tronçons OSM chargés sont exactement ceux de `chunks_for_window` ; chaque tronçon a au plus trois nœuds.
3. Défilement de bout en bout à 20 m/s simulés : nœuds vivants bornés, nombre d'objets en fin de parcours à ± 5 % de sa valeur au premier tiers.
4. Couches absentes, fichier absent, fichier à version majeure 2, élément invalide : aucune erreur Godot, éléments ignorés comptés dans le journal.
5. Bâtiments : chaque sommet du bas des murs est à `base_y − 3 m` ; les tests de L1 passent avec la jupe à 0.
6. Forêts :
   - dans une zone OSM, les arbres sont exactement ceux de `place_tile` avec cette zone (empreinte) ; aucun arbre du bruit dans une zone OSM ni dans un trou ;
   - `p_region` : chacun des trois facteurs vérifié sur des cas construits (région sans forêt OSM, région boisée à 40 %, village, 150 m sous la limite des arbres) ; continuité, aucun saut de plus de 0,05 entre deux points distants de 10 m le long d'une ligne qui traverse quatre tuiles ;
   - hors zones OSM, le nombre d'arbres d'une tuile est proche de `p_region` moyen × celui d'E3 (± 10 % sur une tuile à densité maximale) ;
   - parcours sans couche `vegetation` : positions identiques à celles d'E3 (même empreinte) hors de la bande des 300 m sous la limite des arbres ;
   - même parcours relancé : mêmes arbres.
7. Sons, sur une suite de trames simulées (arrêt, 30 km/h, roue libre, passage près de 6 points d'intérêt) : jamais plus de 4 lecteurs 3D actifs, volumes à 0,5 dB près de ceux de `sound_model.gd`, aucun nœud créé après le démarrage ; un fichier `<kind>.ogg` présent remplace le son généré.
8. Temps CPU sans écran, relevés dans le rapport : lecture et maillage d'un tronçon de 300 bâtiments (seuil 40 ms en intégration continue), génération de tous les sons au démarrage (budget `sound_generation`, 1 200 ms depuis le 28/10).

**Sur le PC cible (le propriétaire, GTX 1060, 1 920 × 1 080) :**
9. Trace réelle avec un village, préréglage `low` : lignes `[perf-rendu]` dans le village, moyenne ≥ 55 images/s, jamais sous 30 ; aucun à-coup à l'entrée d'un nouveau tronçon.
10. Aucun bâtiment flottant ni coupé par le terrain, aucune rivière qui disparaît sous le sol à moins de 200 m de la route, pas de scintillement entre l'eau et le terrain.
11. Sons audibles et non gênants pendant 20 min : vent qui suit la vitesse, roue libre en arrêtant de pédaler, cloche qui monte puis s'éteint au passage ; volume des bips du Click inchangé.

## 8. Hors périmètre

- Toits à deux pans (`roof: "gabled"`, réservé par le format), fenêtres, textures de façade.
- Affichage du nom des points d'intérêt, panneaux de belvédère.
- Couche de couverture du sol (ESA WorldCover), bots, sons de foule.
- Vagues, réflexions en temps réel, rivières animées.
## 9. Livraison (24 octobre 2026, branche lot-e3-e4)

- **Jupe des bâtiments** : paramètre skirt_m: float = 0.0 dans engine/scripts/building_mesh.gd, parois descendant à base_y - skirt_m (3 mètres par défaut dans le streamer) pour compenser les irrégularités du relief.
- **Arbres avec forêts OSM** : intégration dans engine/scripts/tree_renderer.gd des polygones de végétation OSM (densité nominale) et peuplement aléatoire hors polygones selon p_region.
- **Modèle sonore spatialisé et synthèse procédurale** : engine/scripts/sound_player.gd synthétisant au lancement sous le budget `sound_generation` (1 200 ms) les sons de vent (modulé par la vitesse), roue libre, cloche d'église, rivière, bétail et clameur de village ; gestion de 4 lecteurs 3D actifs avec fondu ; surcharge possible via fichiers .ogg dans ~/OpenRide/Sounds/.
- **Diffusion continue OSM** : engine/scripts/osm_streamer.gd chargeant les tronçons OSM en arrière-plan sans à-coup, avec au plus 3 nœuds mesh par tronçon (bâtiments, cours d'eau, plans d'eau) ; intégration dans world_streamer.gd et main.gd.
- **Tests unitaires et headless** :
  - engine/tests/unit/test_building_mesh.gd (19 vérifications avec test de la jupe) ;
  - engine/tests/unit/test_sound_player.gd (5 vérifications de synthèse et de lecture) ;
  - engine/tests/test_osm_streamer.gd (6 vérifications de partitionnement et fusion de maillages).
- **Reste à faire par le propriétaire** : validation visuelle et sonore sur le parcours réel avec machine cible (critères 9 à 11).
