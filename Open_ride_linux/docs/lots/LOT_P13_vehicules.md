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
