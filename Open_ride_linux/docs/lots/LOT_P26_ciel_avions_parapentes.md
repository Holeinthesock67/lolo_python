# Lot P26 – Ciel : avions de ligne et traînées, avion de tourisme, hélicoptère, parapentes, montgolfières

## 1. Objectif

Demande du propriétaire du 27 octobre (« ça manque de vie : animaux, oiseaux, véhicules sur terre et dans le ciel »), cinquième lot de la deuxième vague du décor vivant (P22 à P27, dossier du 27 octobre validé le même soir). En dehors des nuages (P6) et des oiseaux (P11, P23), le ciel est vide. Ce lot y ajoute, rarement et de loin :

- des avions de ligne très hauts, avec une traînée de condensation qui s'élargit et s'efface, absente par ciel couvert ;
- un petit avion de tourisme et, plus rarement, un hélicoptère, chacun avec son bruit ;
- des parapentes qui tournent près des sommets des montées ;
- des montgolfières qui dérivent quand le vent décoratif est faible.

## 2. À lire

1. `docs/lots/LOT_P6_nuages.md`, `docs/lots/LOT_P8_meteo_legere.md`, `docs/lots/LOT_P9_ambiance_sonore.md`, `docs/lots/LOT_P17_integration_decor_complet.md`, `docs/lots/LOT_P23_oiseaux_campagne.md`, `docs/lots/LOT_Y1_brouillard_distance_prereglage.md` (distance de la caméra par préréglage), `docs/lots/LOT_Y14_personnages_animaux.md` (Builder).
2. Code : `engine/scripts/living_decor.gd` (montées `climbs`, météo évaluée, `step`), `sky_clouds.gd` (couverture des nuages), `wind_model.gd` (vent évalué), `weather_model.gd`, `render_quality.gd` et `quality_presets.gd` (`fog_end_m`, `camera.far`), `sound_player.gd`, `people_mesh.gd` (Builder, sans le modifier).

## 3. Prérequis

P6, P8, P17 et Y14 livrés ; P25 avant celui-ci (même fichier `living_decor.gd`, même nouvelle famille de clés `LIVING`).

## 4. Travail demandé

- **Modèle sans nœud** (nouveau `sky_traffic_model.gd`) : planning déterministe tiré de la graine du parcours et de créneaux de temps de séance (les objets du ciel ne dépendent pas de la position du cycliste, sauf les parapentes et les montgolfières) :
  - `airliner` : un passage par créneau de 150 s avec une chance de 6 sur 10, cap tiré au hasard, altitude apparente de 9 à 11 km, vitesse 230 m/s ; pas de passage si la couverture des nuages de `sky_clouds.gd` dépasse 0,6 ou si la météo est à la pluie ou à la brume (`kind`) ;
  - `light_plane` : un passage par créneau de 600 s avec une chance de 4 sur 10, de 600 à 1 200 m au-dessus du sol, 50 m/s, trajectoire droite qui passe à moins de 1 500 m du cycliste ;
  - `helicopter` : un passage par créneau de 1 200 s avec une chance de 3 sur 10, de 150 à 300 m au-dessus du sol, 45 m/s, qui croise la route à moins de 600 m du cycliste ;
  - `paraglider` : 1 à 3 voiles près du sommet de chaque montée de `climbs` d'au moins 150 m de dénivelé, avec une chance de 1 sur 2 par montée, sur un cercle de 60 à 150 m de rayon, de 100 à 300 m au-dessus du versant, si le vent évalué est sous 8 m/s et sans pluie ; visibles quand le cycliste est à moins de 3 km du sommet ;
  - `balloon` : 1 ou 2 montgolfières par tronçon de 5 km avec une chance de 1 sur 4, de 300 à 800 m du sol, de 1 à 3 km de la route, qui dérivent dans le sens du vent évalué à sa vitesse, seulement si ce vent est sous 3 m/s et sans pluie.
  Tous les objets sont figés en pause et disparaissent en douceur (réduction d'échelle sur 2 s) quand la météo ou le vent ne les permet plus.
- **Distance d'affichage** : la caméra s'arrête à `fog_end_m` + 3 % (Y1), soit 4,1 km en `low`. Un avion de ligne réel serait au-delà : il est dessiné sur la même direction de vue, à 85 % de la distance de la caméra, à l'échelle qui lui donne la même taille apparente, avec un matériau qui ignore le brouillard de profondeur (mode de rendu `fog_disabled` du shader, à vérifier en Godot 4.3 ; sinon brouillard du matériau coupé à la main). Les autres objets sont à leur vraie place et suivent le brouillard.
- **Traînée** : ruban construit par code derrière chaque avion de ligne (40 segments au plus), qui s'élargit de 2 à 16 fois l'envergure et s'efface sur 60 s ; même matériau sans brouillard. Aucune traînée pour les autres objets.
- **Affichage** (nouveau `sky_traffic_renderer.gd`) : maillages construits par code avec le Builder de `people_mesh.gd` (avion de ligne bimoteur blanc, petit avion à aile haute, hélicoptère avec rotor qui tourne, voile de parapente en arc et pilote, enveloppe de montgolfière à bandes de couleur et nacelle), un nœud par emplacement du budget, tous créés au démarrage.
- **Budget** : nouvelle clé `aircraft` de `LIVING` dans `quality_presets.gd`, 2 / 4 / 6 en `low` / `medium` / `high` ; quand le planning en demande plus, priorité aux parapentes et aux montgolfières proches, puis à l'avion de ligne, puis au reste.
- **Sons** (`sound_player.gd`) : `helicopter` (battement du rotor, audible à moins de 1 200 m) et `light_plane` (bourdonnement de moteur à pistons, à moins de 2 000 m), synthétisés comme les autres sons brefs, remplaçables par `~/OpenRide/Sounds/<sorte>.ogg`, joués par un seul lecteur 3D posé sur l'objet audible le plus proche, au volume `ambience.volume` du thème. Ni les avions de ligne, ni les parapentes, ni les montgolfières ne font de bruit.
- **`living_decor.gd`** : création du modèle et du rendu dans `configure`, mise à jour dans `step` (montées, couverture, météo et vent déjà évalués).

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/living_decor.gd`, `quality_presets.gd` (clé `aircraft`), `sound_player.gd` ; `engine/tests/unit/test_quality_presets.gd`, `test_sound_player.gd`, `test_living_decor.gd` ; `engine/tests/perf_budgets.json` (ligne `sky_traffic_frame`) ; `engine/tests/README.md`, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `engine/scripts/sky_traffic_model.gd`, `sky_traffic_renderer.gd`, `engine/tests/unit/test_sky_traffic_model.gd`.
- **Interdits :** `sky_clouds.gd` (lecture de la couverture seulement), `people_mesh.gd`, `crowd_renderer.gd`, `fauna_*.gd`, `traffic_*.gd`, `main.gd`, le compilateur, le core, les contrats.

## 6. Modifications de contrat autorisées

Aucune : ni IPC, ni format `.world`, ni thème, ni touche. Désactivé avec le reste par `[render] living = false`.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Planning déterministe : même graine et même temps, mêmes objets ; sur 10 h simulées en `high` par ciel clair, de 120 à 170 avions de ligne, de 25 à 45 avions de tourisme et de 6 à 12 hélicoptères ; aucun avion de ligne avec une couverture de 0,7 ou par pluie.
3. Parapentes : aucun sur un parcours plat ; sur une montée de 400 m de dénivelé, au plus 3 voiles, sur leur cercle, au-dessus du sol ; aucune avec un vent de 9 m/s. Montgolfières : aucune avec un vent de 4 m/s ; dérive dans le sens du vent.
4. Avion de ligne : à 85 % de `camera.far` dans les trois préréglages, taille apparente constante quand `fog_end_m` change ; traînée de 40 segments au plus, opacité nulle après 60 s.
5. Jamais plus que `living(preset).aircraft` objets affichés ; aucun nœud créé après le démarrage ; tout figé en pause ; mise à jour sous 0,1 ms par image (`sky_traffic_frame`).
6. Son : hélicoptère audible à 1 000 m, muet à 1 500 m ; un seul lecteur 3D pour tout le ciel.

**Sur le PC cible (le propriétaire) :** séance de 30 min en `medium` sur un parcours avec une montée : au moins un avion de ligne et sa traînée, un parapente près du sommet par vent faible, aucun objet qui apparaît d'un coup ni qui traverse un nuage bas de façon choquante ; perte de moins de 0,5 image/s en `low` (P27 fait la mesure complète).

## 8. Hors périmètre

- Feux de navigation et ciel de nuit (P19, version 2.0) ; avions qui décollent ou atterrissent ; ombre des objets du ciel au sol.
- Planeurs, drones, oiseaux de proie de montagne (U12, version 3.0).
- Objets du ciel pendant le Cyber-Rogue (série R, scène à part).
