# Lot P15 – Spectateurs et encouragements dans les dernières côtes

## 1. Objectif

Dans le dernier kilomètre des montées repérées par P14, des spectateurs se tiennent au bord de la route, plus nombreux près du sommet ; ils s'animent au passage du cycliste (bras levés, drapeaux), et une clameur monte quand il approche, plus forte s'il accélère ou s'il dépasse un bot. Effet de « grand col » sans coût notable : silhouettes en `MultiMesh`, animation dans le shader.

## 2. À lire

1. `docs/lots/00_INDEX.md` (budget de la série P), `docs/lots/LOT_P14_bord_de_route.md` (`climb_detector.gd`), `docs/lots/LOT_P9_ambiance_sonore.md`, `docs/lots/LOT_O7_affichage_bots.md`.
2. Code : `engine/scripts/sound_player.gd`, `engine/scripts/tree_renderer.gd` (`MultiMesh`), `engine/scripts/route_data.gd`.

## 3. Prérequis

P9 et P14 livrés. Version 1.0 publiée.

## 4. Travail demandé

- Nouveau modèle pur `engine/scripts/crowd_model.gd` :
  - placement déterministe de spectateurs dans le dernier kilomètre de chaque montée (de 0 à 3 m du bord, des deux côtés), densité croissante vers le sommet, groupes ; aucun sur la route ni dans l'eau ; aucun pour une montée de moins de 3 km sauf si `crowd_all_climbs` ;
  - réaction : état « calme », « encourage » (cycliste à moins de 25 m), avec un décalage aléatoire par spectateur ;
  - intensité de la clameur selon la distance au groupe le plus proche, la puissance relative à la FTP (si fournie) et un dépassement de bot récent (après N9 et O7).
- Nouveau nœud `engine/scripts/crowd_renderer.gd` : silhouettes simples (corps, tête, bras, drapeau) construites par code, couleurs variées, animation par shader ; au plus `living(preset).spectators`, les plus proches en priorité.
- Son : clameur et applaudissements synthétisés dans `sound_player.gd` (remplaçables par des `.ogg`), source 3D sur le groupe le plus proche.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/crowd_model.gd`, `engine/scripts/crowd_renderer.gd`, `engine/shaders/crowd.gdshader`, `engine/tests/unit/test_crowd_model.gd`.
- **Modifiés :** `engine/scripts/sound_player.gd` (un son), `engine/tests/unit/test_sound_player.gd`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Montée de 8 km : spectateurs seulement dans le dernier kilomètre, plus nombreux dans les 200 derniers mètres que dans les 200 premiers ; montée de 2 km : aucun.
3. Aucun spectateur à moins de 0,3 m du bord de la route ni dans l'eau.
4. Spectateurs à moins de 25 m : état « encourage » ; à 100 m : « calme ».
5. Clameur nulle hors des zones de spectateurs, croissante à l'approche, plus forte avec un dépassement récent.
6. Jamais plus que le budget ; mise à jour sous 0,2 ms par image pour 200 spectateurs.

**Sur le PC cible (le propriétaire) :** fin de col en `low` : foule visible, clameur qui monte, perte de moins de 2 images/s.

## 8. Hors périmètre

- Spectateurs qui courent à côté du cycliste, banderoles écrites, commentateur.

## 9. Livraison

Livré sur la branche `lot-p15-spectateurs`, après P13 (même `sound_player.gd`), avec P14 fusionné (`climb_detector.gd`). Sans toucher à `main.gd`, au core ni au contrat.

- **`crowd_model.gd`** :
  - Placement : cases de 2 m de chaque côté de la route, dans le dernier kilomètre des montées d'au moins 3 km (toutes avec `crowd_all_climbs`). Probabilité de 12 % au début de la zone à 85 % au sommet, par groupes de 25 m (un groupe sur trois clairsemé), jusqu'à 2 personnes par case. Écart au bord de 0,3 à 3 m. Aucun spectateur dans l'eau. Tirage déterministe par graine.
  - Réaction : « encourage » à moins de 25 m, après un délai propre de 0 à 0,6 s, sinon « calme ». Seuls les spectateurs à ± 60 m sont examinés (dichotomie).
  - Clameur de 0 à 1 : distance au groupe le plus proche (nulle au-delà de 150 m), taille du groupe, puissance relative à la FTP si elle est fournie (× 0,8 à × 1,3). `observe_bots` repère un bot qui passe de devant à derrière : + 0,35 qui décroît en 5 s.
- **`crowd_renderer.gd`** et **`crowd.gdshader`** : silhouettes (jambes, buste, tête, bras, drapeau pour un sur quatre) construites par code, deux `MultiMesh`, huit couleurs d'instance. Bras levés et drapeaux agités par le shader à partir de `TIME`. Budget `living(preset).spectators`, les plus proches de la caméra (tri tous les 20 m). La donnée d'instance n'est réécrite que quand un état change. Un lecteur 3D joue la clameur sur le groupe le plus proche.
- **`sound_player.gd`** : son `crowd_cheer` (clameur et applaudissements), remplaçable par `.ogg`. Le vent n'est plus synthétisé deux fois (P10) : synthèse de tous les sons en 240 ms ici.
- **Tests** : `test_crowd_model.gd` (16 vérifications ; 200 spectateurs en 0,11 ms par image ici), `render/test_crowd_render.gd` (2), `test_sound_player.gd` (son de plus).
- **Reste sur le PC cible (le propriétaire)** : fin de col en `low`, après le branchement par P17 (qui passe la FTP de la configuration et les bots de la trame).
