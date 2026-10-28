# Lot P25 – Cyclistes et véhicules, deuxième vague : cyclistes sur la route, camionnettes, camions, bus, motos, routes voisines et tracteurs au champ

## 1. Objectif

Demande du propriétaire du 27 octobre (« ça manque de vie : animaux, oiseaux, véhicules sur terre et dans le ciel »), quatrième lot de la deuxième vague du décor vivant (P22 à P27, dossier du 27 octobre validé le même soir, ordre P23, P22, P24, P25, P26, P27). Aujourd'hui (P13), la route du parcours ne voit passer que deux modèles de voiture et un tracteur, sur 3 % des cases de 250 m hors village, soit environ une voiture tous les 8 km, et rien ne bouge au loin. Ce lot ajoute :

- sur la route du parcours, des **cyclistes** : seuls ou en petits groupes, en face, qui doublent le cycliste ou qu'il double, plus nombreux dans les montées (demande du propriétaire du 28 octobre : « plutôt plus de vélos » que plus de voitures) ;
- quatre sortes de véhicules de plus : camionnette, camion, bus (près des villages) et moto, **sans** rendre les voitures plus fréquentes ;
- sur les routes voisines de la couche `roads` (P22), des véhicules lointains qui roulent dans le bon sens, à la vitesse de leur route ;
- dans les champs cultivés (`farmland`, P22), un tracteur qui fait des allers-retours ;
- des phares et des feux allumés par la brume et la pluie (la nuit viendra avec P19, version 2.0).

## 2. À lire

1. `docs/lots/LOT_P13_vehicules.md`, `docs/lots/LOT_P17_integration_decor_complet.md`, `docs/lots/LOT_P22_pres_champs_routes_voisines.md` (couche `roads`, terrains ouverts), `docs/lots/LOT_P8_meteo_legere.md`, `docs/lots/LOT_Y14_personnages_animaux.md` (Builder de `people_mesh.gd`).
2. Code : `engine/scripts/traffic_model.gd`, `traffic_renderer.gd`, `living_decor.gd`, `osm_layers.gd`, `osm_streamer.gd` (tronçons chargés), `weather_model.gd`, `sound_player.gd`, `people_mesh.gd` (classe `Builder`, à utiliser sans la modifier), `quality_presets.gd`.
3. Maquette navigateur du dossier du 27 octobre : [décor vivant](https://claude.ai/artifact/KWfbsN9dkHFJahzntRaZZt).

## 3. Prérequis

P13, P17, P22 (couche `roads` et terrains ouverts lus par `osm_layers.gd`) et Y14 (Builder) livrés. P24 n'est pas nécessaire, mais il touche `sound_player.gd` : faire P25 après sa fusion.

## 4. Travail demandé

### 4.1 Route du parcours (`traffic_model.gd`, `traffic_renderer.gd`)

- **Sortes** : `KINDS` gagne `van` (camionnette, demi-largeur 1,0 m, 5,0 m), `truck` (camion porteur, 1,25 m, 9,5 m), `bus` (car, 1,25 m, 12,0 m) et `moto` (0,4 m, 2,1 m). Tirage par case dans une table `KIND_SHARES` : voitures 55 % (`car_a` et `car_b` à parts égales), camionnette 15 %, camion 8 %, moto 7 %, tracteur 10 % (hors village, comme aujourd'hui), bus 5 % (à moins de `VILLAGE_NEAR_M` d'un point `village` seulement, sinon tiré comme une voiture). Les parts sont dans la table, modifiables.
- **Densité** : inchangée (`BASE_RATE` 0,03, `VILLAGE_RATE` 0,25) : les nouvelles sortes prennent une part des véhicules existants, elles n'en ajoutent pas (décision du propriétaire du 28 octobre : la vie de la route vient des cyclistes du §4.2).
- **Vitesses** : camion et bus de 45 à 65 km/h, camionnette comme une voiture, moto de 60 à 85 km/h ; tracteur inchangé.
- **Dépassement** : mêmes règles qu'en P13 (écart latéral d'au moins `LATERAL_CLEARANCE_M` entre la carrosserie et le cycliste). Un véhicule trop large pour dépasser sur la route du parcours (`road_width_m` trop étroite pour sa largeur plus l'écart et le cycliste) suit le cycliste à `FOLLOW_GAP_M` jusqu'à la fin de la zone étroite, puis dépasse ; s'il n'y en a pas avant `REMOVE_AHEAD_M`, il tourne (il disparaît derrière un virage, hors du champ de la caméra). Aucun camion ni bus sur une pente de plus de `MAX_GRADE_PCT`, comme les autres.
- **Affichage** : carrosseries des quatre nouvelles sortes construites par code avec le Builder de `people_mesh.gd` (cabine, caisse, vitres sombres, roues qui tournent ; moto avec son pilote casqué, construit avec `build_person(false, true)`), dans le même pool de `MAX_VEHICLES` nœuds créés au démarrage (une carrosserie par sorte et par emplacement, une seule visible). Couleurs : palette de P13 pour les voitures et les camionnettes, blanc ou gris clair pour les camions et les bus.
- **Sons** (`sound_player.gd`) : `truck_pass` (moteur diesel grave et souffle plus long que `vehicle_pass`) et `moto_pass` (moteur aigu qui monte puis descend), synthétisés comme les autres, remplaçables par `~/OpenRide/Sounds/<sorte>.ogg` ; le bus joue `truck_pass`, la camionnette `vehicle_pass`.

### 4.2 Cyclistes sur la route du parcours (nouveaux `road_cyclists_model.gd` et `road_cyclists_renderer.gd`)

- **Modèle sans nœud**, sur le principe de `traffic_model.gd` : le parcours est découpé en cases de 250 m ; chaque case tire, d'après la graine et son indice, un groupe de cyclistes avec une probabilité `CYCLIST_RATE` (proposition : 0,12 en plaine, 0,30 dans une montée de `climbs`, 0,20 à moins de 1 km d'un village), soit à peu près un groupe par kilomètre en plaine et trois par kilomètre dans un col. Taille du groupe : 1 (55 %), 2 (25 %), 3 à 6 (20 %), roulant en file ou à deux de front, à 0,6 m d'écart latéral et 1,5 m l'un derrière l'autre.
- **Trois cas**, tirés par groupe :
  - **en face** (40 %) : sur le bord gauche de la route, de 22 à 35 km/h sur le plat, de 35 à 55 km/h en descente ;
  - **devant, plus lent** (35 %) : sur le bord droit, de 18 à 28 km/h (de 9 à 16 km/h en montée) ; le cycliste les rattrape et les double ; ils restent à au moins 1,2 m sur sa droite pendant le dépassement (ils se serrent sur le bord) ;
  - **qui double** (25 %) : arrive de 150 m derrière, 4 à 8 km/h plus vite que le cycliste (au moins 25 km/h sur le plat), passe à au moins 1,2 m sur sa gauche, puis se rabat 20 m devant et s'éloigne. Si le cycliste accélère au-dessus de sa vitesse, le groupe reste derrière et disparaît au bout de 60 s.
- **Vitesse en pente** : vitesse de départ du groupe corrigée par la pente sous lui (une formule simple de puissance constante, sans le modèle physique du core) ; jamais plus de 70 km/h en descente.
- **Sécurité visuelle** : jamais un cycliste du décor à moins de 1,2 m latéralement du cycliste ou d'un bot à la même abscisse ; pas de groupe en face pendant qu'un véhicule de §4.1 croise ou double ; aucun cycliste dans un tunnel ni en ville (`village` dense) à plus de 3 de front.
- **Pas d'effet sur la physique** : ce ne sont pas des bots (O7, T12) ; ils ne donnent ni aspiration, ni écart dans le HUD, ni classement.
- **Budget** : nouvelle clé `cyclists` de `LIVING` dans `quality_presets.gd`, 4 / 8 / 16 en `low` / `medium` / `high` ; les plus proches d'abord ; supprimés à plus de 300 m derrière ou 1 200 m devant.
- **Affichage** : vélo et coureur casqué construits par `people_mesh.gd` (`build_bike`, `build_person(false, true)`, sans modifier ce fichier), même shader de pédalage que les bots, cadence déduite de la vitesse (braquet fixe de 50 × 17), maillots tirés d'une palette de 8 couleurs par la graine du cycliste ; un `MultiMeshInstance3D` pour les vélos et un pour les coureurs, créés au démarrage. Un cycliste en face lève la main quand il croise le cycliste à moins de 15 m, une fois sur deux, si le shader des personnages le permet (geste des passants de P21) ; sinon il ne fait rien.
- **Son** : aucun son propre (le roulement d'un vélo ne s'entend pas par-dessus celui du cycliste) ; un groupe qui double dit « Salut ! » une fois sur trois, avec les voix brèves des passants de P21 (`sound_player.gd`).

### 4.3 Routes voisines (nouveaux `distant_traffic_model.gd` et `distant_traffic_renderer.gd`)

- **Modèle sans nœud** : pour chaque morceau de la couche `roads` d'un tronçon chargé, une probabilité d'avoir des véhicules qui dépend de la sorte de route (`ROAD_RATE`, de 0,1 pour `track` à 1,0 pour `motorway` et `trunk`, tirée du hachage de l'identifiant du morceau) ; au plus un véhicule par voie et par 400 m de route ; sens tiré au hasard sur une route à double sens, dans le sens du tracé sur une route à sens unique ; vitesse : `speed_kmh` de la couche, moins 0 à 15 % ; sorte tirée comme sur la route du parcours, sans tracteur ni bus sur `motorway`. Un véhicule arrivé au bout de son morceau repart du début (le morceau est coupé avant la route du parcours : rien ne la traverse).
- **Budget** : nouvelle clé `distant_vehicles` de `LIVING` dans `quality_presets.gd` : 6 / 12 / 24 en `low` / `medium` / `high` ; les véhicules les plus proches du cycliste d'abord ; rien au-delà de 1 500 m ni sur un tronçon déchargé.
- **Affichage** : un `MultiMeshInstance3D` par sorte, créé au démarrage, avec deux niveaux : la carrosserie détaillée de 4.1 jusqu'à 400 m, une boîte simple (`DISTANT_BOX`) au-delà ; sans son (trop loin pour s'entendre, sauf une rumeur d'autoroute laissée à P9 plus tard). Mise à jour par quart du budget à chaque image, comme le bétail de P11.

### 4.4 Tracteur au champ (dans `distant_traffic_model.gd`)

- Un champ (`farmland`) d'au moins 2 ha, à moins de 400 m de la route, reçoit un tracteur avec une chance de 3 sur 10 (hachage de l'identifiant de la zone), au plus un par tronçon de 1 000 m. Il fait des allers-retours à 8 km/h le long du grand axe du champ, en se décalant de 6 m à chaque demi-tour, sans sortir du contour ; demi-tour en 4 s. Il compte dans le budget `distant_vehicles` et joue `tractor_engine` à moins de 150 m (même lecteur 3D que P13, un seul pour tous les tracteurs au champ, posé sur le plus proche).

### 4.5 Phares et feux

- Chaque carrosserie a des phares (blanc chaud) et des feux arrière (rouges) en matériau émissif, éteints par défaut. `living_decor.gd` les allume quand la météo évaluée donne `fog_boost` au-dessus de 0,3 ou `rain` au-dessus de 0,2 (`weather_model.gd`), et les éteint sous 0,2 et 0,1 (hystérésis), par un seul paramètre partagé du matériau (aucun nœud de lumière). Une méthode `set_lights(on)` sert aussi à la nuit de P19 (version 2.0), qui n'est pas faite ici.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/traffic_model.gd`, `traffic_renderer.gd`, `living_decor.gd` (création et branchement des cyclistes et des véhicules lointains, phares), `quality_presets.gd` (clés `cyclists` et `distant_vehicles`), `sound_player.gd` ; `engine/tests/unit/test_traffic_model.gd`, `test_quality_presets.gd`, `test_sound_player.gd`, `test_living_decor.gd` ; `engine/tests/perf_budgets.json` (lignes `road_cyclists_frame` et `distant_traffic_frame`) ; `engine/tests/README.md`, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `engine/scripts/road_cyclists_model.gd`, `road_cyclists_renderer.gd`, `distant_traffic_model.gd`, `distant_traffic_renderer.gd`, `engine/tests/unit/test_road_cyclists_model.gd`, `test_distant_traffic_model.gd`.
- **Interdits :** `people_mesh.gd` et `crowd_renderer.gd` (fil des personnages), `fauna_*.gd`, `main.gd`, le compilateur, le core, les contrats.

## 6. Modifications de contrat autorisées

Aucune : ni IPC, ni format `.world`, ni thème, ni touche. Désactivé avec le reste par `[render] living = false`. Sans couche `roads` ni terrains ouverts (parcours compilé sans OSM ou avant P22), seule la route du parcours change.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Route du parcours, sur 2 000 cases tirées : parts des sortes à ± 3 points de `KIND_SHARES` ; aucun bus à plus de `VILLAGE_NEAR_M` d'un village ; aucun tracteur près d'un village ; déterministe (même parcours, mêmes véhicules) ; un camion qui rattrape le cycliste sur une route de 4 m le suit à `FOLLOW_GAP_M` et ne le double jamais à moins de `LATERAL_CLEARANCE_M` ; jamais plus que `living(preset).vehicles`.
3. Cyclistes : sur 20 km de plaine puis 10 km de montée, de 15 à 30 groupes en plaine et de 20 à 40 en montée ; déterministe ; un groupe devant, plus lent, est doublé par le cycliste avec au moins 1,2 m d'écart ; un groupe qui double passe à gauche avec au moins 1,2 m d'écart puis se rabat ; aucun cycliste du décor à moins de 1,2 m latéralement du cycliste ou d'un bot ; jamais plus que `living(preset).cyclists` ; pédalage à la cadence attendue ; aucune aspiration ni écart au HUD.
4. Routes voisines : sur un tronçon de test avec une route secondaire à double sens, une piste et une autoroute à sens unique, les véhicules restent sur leur ligne, dans le bon sens, à la vitesse de la couche moins 15 % au plus ; aucun véhicule à moins de 20 m de la route du parcours ; jamais plus que `living(preset).distant_vehicles` ; rien sur un tronçon déchargé.
5. Tracteur au champ : toujours dans le contour du champ, demi-tour au bord, décalage de 6 m par passage ; aucun tracteur dans un pré ou une prairie.
6. Phares allumés à `fog_boost` = 0,4, éteints à 0,1 ; aucun changement de nœud ni de matériau par véhicule.
7. Performances : mise à jour de 16 cyclistes, de 8 véhicules sur la route et de 24 véhicules lointains sous 0,25 ms par image (`road_cyclists_frame`, `traffic_frame` et `distant_traffic_frame` de `perf_budgets.json`) ; aucun nœud créé après le démarrage.

**Sur le PC cible (le propriétaire) :** séance en `medium` sur un parcours de campagne compilé avec les couches OSM : des cyclistes croisés, doublés ou qui doublent à peu près à chaque kilomètre, davantage dans une montée ; camions, bus et motos de temps en temps, voitures qui roulent au loin sur les routes voisines, un tracteur dans un champ ; phares allumés dans un thème à brume. Perte de moins de 1 image/s en `low` (P27 fait la mesure complète de la deuxième vague).

## 8. Hors périmètre

- Nuit et éclairage public (P19, version 2.0) ; poussière derrière le tracteur (Y12) ; rumeur sonore des grandes routes (P9 plus tard).
- Carrefours, feux tricolores, véhicules qui tournent vers la route du parcours ou qui s'arrêtent ; aucune interaction avec la physique du cycliste.
- Avions, hélicoptères et autres objets du ciel : P26.
- Cyclistes du décor qui réagissent à l'aspiration, aux attaques ou au classement : ce sont les bots (O7, T12, Y10).

## 9. Livraison

Livré le 28 octobre (PR #469), au-dessus de P22, P24 et Y14 (maillages par le Builder de `people_mesh.gd`, nouveau `vehicle_mesh.gd` et `shaders/vehicle.gdshader`).

- Écarts au cahier :
  - véhicules de la route en MultiMesh par sorte plutôt qu'en réserve de nœuds : peinture et angle des roues par instance, matériau partagé par sorte (même résultat, moins de nœuds) ;
  - la moto porte son propre pilote dans `vehicle_mesh.gd` (un seul maillage) au lieu de `build_person` ;
  - taux des cyclistes relevés à 0,25 en plaine, 0,75 en montée et 0,4 au village (cahier : 0,12, 0,30 et 0,20), qui ne pouvaient pas donner les 15 à 30 groupes sur 20 km et 20 à 40 en montée du §7 ; mesuré 22 et 30 ;
  - « Salut ! » à la voix seulement, sans geste de la main ;
  - véhicules lointains mis à jour une image sur quatre au-delà de 400 m seulement ; routes voisines et champs posés sur le relief exagéré (`visual_grade_scale`, lot Q2) comme le terrain affiché.
- Mesures ici (machine partagée, Godot 4.3 sans écran) : 16 cyclistes en 0,03 ms par image, 24 véhicules lointains en 0,08 ms, décor vivant complet en 0,42 ms en `high`.
- Tests : `test_vehicle_mesh.gd` (79 vérifications), `test_road_cyclists_model.gd` (21), `test_distant_traffic_model.gd` (20), `test_traffic_model.gd` (21), `test_living_decor.gd` (34), `test_quality_presets.gd` (24).
- Reste sur le PC cible : la séance décrite au §7 et la mesure des budgets sur la GTX 1060.
