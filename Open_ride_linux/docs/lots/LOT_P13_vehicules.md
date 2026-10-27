# Lot P13 – Véhicules croisés : voitures et tracteurs sur la route du parcours

## 1. Objectif

De temps en temps, une voiture ou un tracteur croise le cycliste en sens inverse sur la route du parcours, ou le double prudemment, avec le bruit de son passage. Rare (quelques véhicules par dizaine de kilomètres), plus fréquent près des villages, jamais dans les cols de haute montagne. Les routes voisines ne sont pas dans le format `.world` : elles restent hors périmètre.

## 2. À lire

1. `docs/lots/00_INDEX.md` (budget de la série P), `docs/lots/LOT_P4_modele_vent_engine.md` (`living`), `docs/lots/LOT_P9_ambiance_sonore.md`.
2. Code : `engine/scripts/route_data.gd` (position et cap à `s`, largeur de route du thème), `engine/scripts/road_builder.gd` (lecture seulement), `engine/scripts/sound_player.gd`, `engine/scripts/osm_layers.gd` (points `village`).

## 3. Prérequis

P4 et P9 livrés (même `sound_player.gd`). Version 1.0 publiée.

## 4. Travail demandé

- Nouveau modèle pur `engine/scripts/traffic_model.gd` :
  - apparition déterministe (graine + tronçon) d'un véhicule à 600 à 1 200 m devant le cycliste, en sens inverse sur la voie de gauche, ou derrière lui pour un dépassement ; fréquence selon la proximité d'un village, nulle au-dessus de `snow_line_m` du thème ou si la pente dépasse 8 % ;
  - vitesse constante (voiture 50 à 70 km/h, tracteur 20 à 30 km/h), ralentie à 30 km/h en dépassant le cycliste avec un écart latéral de 1,5 m au moins ; jamais de dépassement si un véhicule arrive en face ;
  - au plus `living(preset).vehicles` à la fois ; suppression au-delà de 300 m derrière.
- Nouveau nœud `engine/scripts/traffic_renderer.gd` : carrosseries simples construites par code (deux silhouettes de voiture, un tracteur), quatre couleurs ; roues qui tournent.
- Son : sifflement de passage (effet Doppler par `AudioStreamPlayer3D`), moteur grave du tracteur ; ajoutés à la synthèse de `sound_player.gd` et remplaçables par des `.ogg`.
- Pause : véhicules figés.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/traffic_model.gd`, `engine/scripts/traffic_renderer.gd`, `engine/tests/unit/test_traffic_model.gd`.
- **Modifiés :** `engine/scripts/sound_player.gd` (deux sons), `engine/tests/unit/test_sound_player.gd`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, `road_builder.gd`, le core (les véhicules sont décoratifs, sans effet sur la physique ni le journal), le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Séance simulée de 30 km à 30 km/h (sans affichage) : nombre de véhicules entre 3 et 15, dont au moins un dépassement ; aucun au-dessus de la limite de neige ni sur une pente de plus de 8 %.
3. Jamais deux véhicules au même endroit, jamais un véhicule à moins de 1,5 m latéralement du cycliste, jamais de dépassement face à un véhicule venant en sens inverse.
4. Même graine, même parcours : même suite de véhicules.
5. Jamais plus que le budget ; 0 en budget nul.
6. Mise à jour sous 0,1 ms par image.

**Sur le PC cible (le propriétaire) :** séance de 20 min : passages crédibles, son qui suit le véhicule, aucun véhicule qui traverse le cycliste.

## 8. Hors périmètre

- Routes voisines (couche OSM des routes non prévue par le format), carrefours, stationnement, piétons.

## 9. Livraison

Livré sur la branche `lot-p13-vehicules` (après P10, pour `sound_player.gd`), sans toucher à `main.gd`, à `road_builder.gd`, au core ni au contrat.

- **`traffic_model.gd`** : le parcours est découpé en cases de 250 m. Chaque case tire, d'après la graine et son indice, s'il porte un véhicule : 3 % de chances, 28 % à moins d'1 km d'un village. Rien au-dessus de `terrain.snow_line_m` ni sur une pente de plus de 8 %. Le tirage fixe aussi la sorte (20 % de tracteurs), la couleur et la vitesse (voiture 50 à 70 km/h, tracteur 20 à 30 km/h). Il fixe enfin le sens : 40 % de dépassements, sinon en face, à 600 à 1 200 m devant.
  - Le cycliste roule sur l'axe ; un véhicule le croise ou le double à 1,5 m au moins de sa carrosserie (2,7 m de l'axe pour une voiture, 2,9 m pour un tracteur).
  - Le véhicule qui double se déporte à gauche de 60 m derrière à 30 m devant, à 30 km/h ou 10 km/h de plus que le cycliste, puis revient à droite. Il ne se déporte que si aucun véhicule venant en face ne peut le croiser avant la fin du dépassement ; sinon, il suit à 25 m. Pas de nouveau véhicule en face pendant un dépassement, et un véhicule en face qui en rattrape un autre se cale à sa vitesse.
  - Au plus `budget` véhicules (`living(preset).vehicles`), supprimés à 300 m derrière. En pause, rien ne bouge. Coût : 0,001 ms par image.
- **`traffic_renderer.gd`** : pool de 8 véhicules créés au démarrage : berline, petite voiture haute et tracteur en boîtes, quatre couleurs, roues qui tournent avec la distance parcourue. Un `AudioStreamPlayer3D` par véhicule, avec suivi Doppler : P17 devra activer `doppler_tracking` sur la caméra.
- **`sound_player.gd`** : sons `vehicle_pass` (pneus et souffle) et `tractor_engine` (moteur grave), remplaçables par `~/OpenRide/Sounds/<kind>.ogg`, lus par `stream(kind)`.
- **Tests** : `test_traffic_model.gd` (16 vérifications ; modèle et affichage en 0,008 ms par image ici), `test_sound_player.gd` (+1).
- **Reste sur le PC cible (le propriétaire)** : séance de 20 min, après le branchement par P17.
