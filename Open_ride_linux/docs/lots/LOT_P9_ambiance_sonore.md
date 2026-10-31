# Lot P9 – Sons d'ambiance selon le décor

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Sons d'ambiance selon le décor (forêt, champs, eau, village, altitude) | GDScript | P1, P4 | Moyenne | **Livré le 27 octobre** (issue #133) |

## 1. Objectif

Les sons actuels (E4, L5) sont le vent, la roue libre et quatre sources ponctuelles sur les points d'intérêt (cloche, rivière, bétail, village). Ce lot ajoute un **fond d'ambiance** qui dépend de ce qui entoure le cycliste : oiseaux en forêt, insectes et alouettes dans les champs, ruissellement près de l'eau, rumeur et cloches au village, vent plus marqué en altitude, silence relatif la nuit quand l'heure sera simulée (P7, version 2.0). Les fondus sont lents, pour qu'on sente le changement de paysage sans l'entendre basculer.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_L5_modele_sonore.md`, `docs/lots/LOT_E4_osm_eau_sons.md` (sons, fichiers `.ogg` de remplacement), `docs/lots/LOT_P1_contrat_vent_decor.md` §4.4 (`ambience`).
2. Code : `engine/scripts/sound_model.gd`, `engine/scripts/sound_player.gd` (synthèse procédurale, `~/OpenRide/Sounds/`), `engine/scripts/osm_layers.gd` et `engine/scripts/osm_streamer.gd` (zones de végétation, eau, bâtiments chargées), `engine/scripts/tree_renderer.gd` (arbres proches).

## 3. Prérequis

P1 et P4 livrés. Version 1.0 publiée.

## 4. Travail demandé

- Nouveau modèle `engine/scripts/ambience_model.gd` (`extends RefCounted`) :
  - entrée : description du voisinage dans un rayon de 150 m, calculée par l'appelant ou par une fonction du modèle à partir des couches chargées : part de forêt, part de bâti, distance à l'eau la plus proche et sa sorte, altitude, heure solaire (facultative : P7, version 2.0 ; à défaut, heure locale du PC), pluie (P8), vent (P4) ;
  - sortie : volume cible de chaque fond `forest_birds`, `field_insects`, `water_flow`, `village_murmur`, `high_wind`, `rain` ; au plus `living(preset).ambience_voices` fonds non muets à la fois (les plus forts gagnent) ;
  - fondus de 4 s, hystérésis comme les points d'intérêt ; oiseaux réduits la nuit et sous la pluie, insectes seulement en journée (saison : P18, version 2.0) ;
  - volume général `ambience.volume` du thème ; tout à zéro en pause.
- `sound_player.gd` : nouveaux sons synthétisés au lancement (chants d'oiseaux par motifs aléatoires déterministes, stridulation, eau, rumeur, pluie), remplaçables par `~/OpenRide/Sounds/<sorte>.ogg` comme aujourd'hui ; lecteurs non spatialisés pour les fonds ; synthèse totale toujours sous le budget `sound_generation` (1 200 ms depuis le 28/10).
- Cloches au village : les points `church_bell` existants sonnent aussi l'heure pleine (nombre de coups selon l'heure fournie, celle du PC par défaut).

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/ambience_model.gd`, `engine/tests/unit/test_ambience_model.gd`.
- **Modifiés :** `engine/scripts/sound_player.gd`, `engine/tests/unit/test_sound_player.gd`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd` (P16 fournit le voisinage et l'heure), `sound_model.gd` (P10), le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Voisinage 80 % forêt, jour : `forest_birds` est le fond le plus fort ; 0 % forêt et 0 % bâti, midi : `field_insects` ; eau à 20 m : `water_flow` audible ; nuit : oiseaux au moins 20 dB plus bas qu'à midi.
3. Jamais plus de `ambience_voices` fonds audibles.
4. Passage brusque de la forêt au champ : aucune variation de plus de 3 dB en 0,5 s.
5. Synthèse de tous les sons (anciens et nouveaux) sous le budget `sound_generation` (1 200 ms) ; fichier `.ogg` de remplacement utilisé s'il existe.
6. Cloche : 3 coups à 15 h, aucun hors de l'heure pleine.
7. `evaluate` sous 0,1 ms.

**Sur le PC cible (le propriétaire) :** une séance de 20 min sur un parcours avec forêt, village et rivière : ambiance qui change avec le paysage, sans clic ni coupure, et qui ne couvre pas les bips du Click.

## 8. Hors périmètre

- Vent et roue libre (P10), foule et encouragements (P15), passage des véhicules (P13).
- Sons enregistrés fournis avec le dépôt (droits) : seuls la synthèse et les fichiers du propriétaire.

## 9. Livraison

Livré sur la branche `lot-p9-ambiance`, sans toucher à `main.gd`, à `sound_model.gd`, au core ni au contrat.

- **`ambience_model.gd`** : six fonds (`forest_birds`, `field_insects`, `water_flow`, `village_murmur`, `high_wind`, `rain`), chacun avec un niveau maximal entre −20 et −14 dB pour rester sous les bips du Click, multiplié par `ambience.volume` du thème (0,6 par défaut ; `birds` et `insects` règlent leurs fonds).
  - Oiseaux : part de forêt, 24 dB plus bas la nuit (22 h à 4 h 30, rampes d'1 h 30), réduits de 80 % sous la pluie. Insectes : hors forêt et hors bâti, de 9 h à 19 h (rampes de 2 h), coupés par la pluie, réduits par le vent et au-dessus de 1 800 m. Eau : à moins de 100 m, plus fort pour une rivière que pour un lac. Village : part de bâti, plus bas la nuit. Vent d'altitude : au-dessus de 1 200 m, avec la force du vent (P4). Pluie : intensité de P8.
  - Heure : `solar_hour` (P7, version 2.0), à défaut l'heure locale du PC (`local_hour`).
  - Voix : au plus `voices` fonds audibles (`living(preset).ambience_voices`) ; un fond déjà joué garde 3 dB d'avance, et un nouveau fond ne monte qu'une fois une voix libérée, donc la limite tient aussi pendant les fondus.
  - Fondus en dB à 5,5 dB/s (4 s de −36 dB au niveau d'un fond, 2,75 dB au plus en 0,5 s) ; un fond qui démarre part de −36 dB, sous les autres sons. En pause : 40 dB/s jusqu'au silence.
  - `describe(rider_xz, forests, buildings, waters, radius_m)` : parts de forêt et de bâti sur une grille de 9 × 9 points dans le disque de 150 m, distance et sorte de l'eau la plus proche (lignes et surfaces), à partir des couches chargées (P16 les lui passe).
  - `bell_strikes(prev_hour, hour)` : coups à l'heure pleine franchie (1 à 12), rien quand l'horloge recule ou saute de plus d'une demi-heure.
- **`sound_player.gd`** : six lecteurs non spatialisés de plus, créés au démarrage ; fonds synthétisés en boucles de 2 s (glissades d'oiseaux par motifs déterministes, stridulation hachée, bruits filtrés pour l'eau, le village, le vent et la pluie avec gouttes), remplaçables par `~/OpenRide/Sounds/<fond>.ogg`. Synthèse de tous les sons : 190 ms ici. `update_ambience(neigh, now_s)` à chaque image ; `update_bells(hour, now_s)` fait sonner les lecteurs des points `church_bell` en cours (hors de portée : rien), un coup toutes les 2,2 s.
- **Fichier de test** : `engine/tests/data/sounds/rain.ogg` (bip de 0,3 s généré par ffmpeg, avec un `.gdignore`) sert au test du remplacement.
- **Tests** : `test_ambience_model.gd` (24 vérifications, `evaluate` en 0,02 ms), `test_sound_player.gd` (10 vérifications, dont 5 nouvelles).
- **Reste sur le PC cible (le propriétaire)** : séance de 20 min avec forêt, village et rivière, après le branchement par P16.

