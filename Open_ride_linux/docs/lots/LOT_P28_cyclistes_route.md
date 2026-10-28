# Lot P28 – Cyclistes du décor sur la route du parcours

## 1. Objectif

Demande du propriétaire du 28 octobre : « plutôt plus de vélos » que plus de voitures. La deuxième vague du décor vivant (P22 à P27) met des véhicules sur la route du parcours et au loin (P25, véhicules au sol), mais aucun autre cycliste que les bots. Ce lot ajoute des cyclistes du décor sur la route : seuls ou en petits groupes, en face, qui doublent le cycliste ou qu'il double, plus nombreux dans les montées. Ils ne sont pas des bots : aucune aspiration, aucun écart dans le HUD, aucun classement.

Ce cahier reprend le §4.2 du premier cahier P25 (PR #462). Ce paragraphe a été séparé quand les véhicules au sol ont été livrés par un autre lot P25 (PR #466).

## 2. À lire

1. `docs/lots/LOT_P13_vehicules.md` (cases de 250 m), `docs/lots/LOT_P21_passants_villages.md` (voix brèves), `docs/lots/LOT_P25_vehicules_au_sol.md`, `docs/lots/LOT_Y14_personnages_animaux.md` (coureur et vélo par `people_mesh.gd`).
2. Code : `engine/scripts/traffic_model.gd` (`vehicles`), `living_decor.gd`, `climb_detector.gd` (montées), `people_mesh.gd` et `shaders/crowd.gdshader` (animations 7 et 8 du pédalage, sans les modifier), `sound_player.gd`, `quality_presets.gd`.

## 3. Prérequis

P13, P17, P21, Y14 et P25 (#466) livrés : P28 est empilé sur #466, qui touche les mêmes fichiers (`living_decor.gd`, `quality_presets.gd`, `perf_budgets.json`).

## 4. Travail demandé

- **Modèle sans nœud** (nouveau `road_cyclists_model.gd`), sur le principe de `traffic_model.gd` : le parcours est découpé en cases de 250 m. Chaque case tire un groupe, d'après la graine et son indice, avec une probabilité qui dépend de l'endroit : plaine, montée de `climbs`, ou moins de 1 km d'un village. Il faut de 15 à 30 groupes sur 20 km de plaine et de 20 à 40 sur 10 km de montée. Un groupe compte 1 cycliste (55 %), 2 (25 %) ou 3 à 6 (20 %). Il roule en file ou à deux de front, à 0,6 m d'écart latéral et 1,5 m l'un derrière l'autre.
- **Trois cas**, tirés par groupe :
  - **en face** (40 %) : sur le bord gauche, de 22 à 35 km/h sur le plat, de 35 à 55 km/h en descente ;
  - **devant, plus lent** (35 %) : sur le bord droit, de 18 à 28 km/h (de 9 à 16 km/h en montée). Le cycliste les rattrape et les double, à au moins 1,2 m sur sa droite ;
  - **qui double** (25 %) : arrive de 150 m derrière, 4 à 8 km/h plus vite que le cycliste (au moins 25 km/h sur le plat). Il passe à au moins 1,2 m sur sa gauche, se rabat 20 m devant et s'éloigne. Si le cycliste va plus vite que lui, le groupe reste derrière et disparaît au bout de 60 s.
- **Vitesse en pente** : puissance constante (formule simple, sans le modèle physique du core) ; jamais plus de 70 km/h.
- **Sécurité visuelle** : aucun cycliste du décor à moins de 1,2 m latéralement du cycliste ou d'un bot à la même abscisse. Pas de groupe en face pendant qu'un véhicule de `traffic_model.gd` est sur la route.
- **Budget** : nouvelle clé `cyclists` de `LIVING`, 4 / 8 / 16 en `low` / `medium` / `high`. Les cyclistes à plus de 300 m derrière ou 1 200 m devant sont retirés.
- **Affichage** (nouveau `road_cyclists_renderer.gd`) :
  - coureur casqué et vélo de `people_mesh.gd` (`build_person(false, true)`, `build_bike`), avec le shader de pédalage des bots ;
  - cadence déduite de la vitesse (braquet de 50 × 17) ;
  - maillot tiré d'une palette de 8 couleurs ;
  - un `MultiMeshInstance3D` pour les coureurs et un pour les vélos, créés au démarrage.
- **Son** : un groupe qui double dit « Salut ! » (`voice_salut`, même synthèse que les voix des passants de P21), sur un seul lecteur 3D.
- **`living_decor.gd`** : création dans `configure`, parcours et montées dans la tâche de fond, mise à jour dans `step` avec la position des bots.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/living_decor.gd`, `quality_presets.gd` (clé `cyclists`), `sound_player.gd` (`voice_salut`) ; `engine/tests/unit/test_quality_presets.gd`, `test_living_decor.gd` ; `engine/tests/perf_budgets.json` (ligne `road_cyclists_frame`) ; `engine/tests/README.md`, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `engine/scripts/road_cyclists_model.gd`, `road_cyclists_renderer.gd`, `engine/tests/unit/test_road_cyclists_model.gd`.
- **Interdits :** `people_mesh.gd`, `crowd_renderer.gd`, `fauna_*.gd`, les fichiers des véhicules de P25, `main.gd`, le compilateur, le core, les contrats.

## 6. Modifications de contrat autorisées

Aucune. Désactivé avec le reste par `[render] living = false`.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Sur 20 km de plaine puis 10 km de montée : de 15 à 30 groupes en plaine et de 20 à 40 en montée. Le tirage est déterministe : même graine, mêmes groupes.
3. Des groupes devant sont doublés et des groupes doublent, toujours avec au moins 1,2 m d'écart. Aucun cycliste du décor n'est à moins de 1,2 m latéralement du cycliste ou d'un bot.
4. Jamais plus que `living(preset).cyclists` cyclistes, jamais plus de 70 km/h. Le pédalage suit la cadence attendue. Tout est figé en pause et aucun nœud n'est créé après le démarrage.
5. Mise à jour de 16 cyclistes sous 0,1 ms par image (`road_cyclists_frame`).

**Sur le PC cible (le propriétaire) :** séance de moins de 10 minutes en `medium` sur un parcours avec une montée. On doit croiser, doubler ou se faire doubler par des cyclistes à peu près à chaque kilomètre, et plus souvent dans la montée. Aucun cycliste ne doit passer à travers le cycliste ou un bot. La perte doit rester sous 1 image/s en `low`. Donner un avis sur la densité.

## 8. Hors périmètre

- Geste de la main des cyclistes en face (le shader des personnages n'a pas de geste pour un coureur sur son vélo).
- Cyclistes qui réagissent à l'aspiration, aux attaques ou au classement : ce sont les bots (O7, T12, Y10).

## 9. Livraison

Livré le 28 octobre (PR #469, empilée sur #466).

- Taux par case retenus : 0,25 en plaine, 0,75 en montée, 0,4 près d'un village. Le premier cahier P25 proposait 0,12, 0,30 et 0,20, qui ne pouvaient pas donner les nombres de groupes du §7 ; on mesure 22 groupes en plaine et 30 en montée.
- L'angle du pédalier est cumulé dans le rendu et passé en phase au shader : un changement de vitesse ne fait pas sauter les jambes.
- Mesures ici (machine partagée, Godot 4.3 sans écran) : 16 cyclistes en 0,03 ms par image ; décor vivant complet en 0,43 ms en `high`.
- Tests : `test_road_cyclists_model.gd` (21 vérifications), `test_living_decor.gd` (33), `test_quality_presets.gd` (25), `test_sound_player.gd` (16).
- Reste sur le PC cible : la séance du §7.
