# Lot P17 – Intégration, deuxième vague : abri, météo, animaux, objets mobiles, bord de route

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Intégration, deuxième vague : abri, météo, animaux, objets mobiles, bord de route | GDScript | P16, P3, P8, P11 à P15, O7 | Grande | **Livré le 27 octobre** (sans l'affichage des bots d'O7), recette sur le PC à faire (issue #141) |

## 1. Objectif

Brancher le reste de la série P dans la scène principale et le recetter sur le matériel :
- l'indicateur « Abri » derrière les bots (P3, modèle P4) ;
- la météo légère (P8) ;
- les animaux (P11) ;
- les éoliennes, drapeaux et l'eau qui scintille (P12) ;
- les véhicules croisés (P13) ;
- les panneaux, bornes et marquages (P14) ;
- les spectateurs (P15) et les passants des villages et de la campagne (P21).

Lot interne : il modifie `main.gd`, `hud_view.gd`, `osm_streamer.gd` et le matériau de la route.

## 2. À lire

1. `docs/lots/00_INDEX.md` (paragraphe « Série P »), cahiers P3, P8 et P11 à P16.
2. Code : `engine/scripts/main.gd`, `engine/scripts/hud_view.gd`, `engine/scripts/road_builder.gd`, `engine/scripts/osm_streamer.gd`, `engine/scripts/world_streamer.gd`, `engine/scripts/render_quality.gd`.

## 3. Prérequis

P16 livré et recetté ; P3, P8, P11 à P15 et P21 livrés ; O7 (bots à l'écran) pour l'abri. Version 1.0 publiée.

## 4. Travail demandé

- Météo (P8) : `fog_boost` appliqué par `render_quality.gd`, particules autour de la caméra, route assombrie sous la pluie (`wetness`).
- `osm_streamer.gd` : animaux (P11), éoliennes et drapeaux (P12), objets de bord de route (P14), spectateurs (P15) et passants (P21) chargés et retirés avec les tronçons, sans à-coup (même règle qu'E4 : préparation hors du fil principal, au plus 3 nœuds par tronçon et par sorte).
- Route : matériau de P14 (marquages) à la place du matériau actuel, via `road_builder.gd`.
- Véhicules (P13) : un nœud suivi par `main.gd`, figé en pause.
- HUD : « Abri 30 % » sous l'indicateur du vent.
- `visual_check.py` : scènes `pluie`, `col` (panneau lisible, spectateurs) ; références mises à jour.
- Nouveau `docs/RECETTE_P17.md`.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/main.gd`, `engine/scripts/hud_view.gd`, `engine/scripts/osm_streamer.gd`, `engine/scripts/world_streamer.gd`, `engine/scripts/road_builder.gd`, `engine/scripts/render_quality.gd`, `engine/tests/visual_check.py`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `docs/RECETTE_P17.md`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Tous les tests passent (`core`, `compiler`, `run_engine_tests.sh`, `run_e2e.sh`, `run_visual_tests.sh`).
2. **Performance sur le PC cible, qualité `low`, toute la série P activée, col avec village, éoliennes, prés et forêt, deux bots, pluie légère :** `[perf-rendu]` à 55 images/s ou plus en moyenne sur 30 min, p99 sous 25 ms, aucune saccade à l'arrivée des tronçons ; sinon, réduire les budgets `low` de `living` jusqu'à tenir l'objectif (valeurs retenues dans la recette).
3. Derrière un bot : « Abri » affiché, résistance plus faible en SIM ; sortie de la roue progressive.
4. Animaux, véhicules et spectateurs jamais sur le cycliste, ni enterrés, ni en l'air.
5. Une heure de séance sans plantage, mémoire stable (écart de moins de 10 % entre la 10e et la 60e minute).

## 8. Hors périmètre

- Jour et nuit, saisons (P7, P18, P19 : version 2.0).
- Multijoueur, peloton de bots, routes voisines.

## 9. Livraison

Livré sur la branche `lot-p17-integration-decor`, qui part de P16 (PR #320) et réunit P3 (#305), P11 (#311), P12 (#312) et P21 (#319, qui contient P13 à P15). Sans modification du contrat. L'affichage des bots (O7) n'existe pas encore : l'abri s'affiche d'après le champ `draft` des trames, sans silhouette.

- **`living_decor.gd`** (nouveau, créé par `main.gd` à côté de `living_world.gd`) rassemble le branchement, testable sans la scène :
  - À chaque parcours, une tâche de fond lit les couches OSM de tout le parcours (bâtiments, eau, points d'intérêt) et prépare :
    - les montées (`climb_detector.gd`), les panneaux et bornes, et les chiffres peints ;
    - les spectateurs du dernier kilomètre des cols et les passants.
    Le fil principal pose ensuite les éoliennes, les drapeaux et la circulation.
  - Une fois par image :
    - météo du thème : particules autour de la caméra, chaussée mouillée, pluie dans l'ambiance de P9, brume qui rapproche le brouillard (au plus 2 fois par seconde) ;
    - animaux, éoliennes, drapeaux, reflets de l'eau ;
    - véhicules, figés en pause ;
    - spectateurs (clameur selon la puissance rapportée à la FTP et les bots doublés) et passants (aucun son pendant un bip).
  - Core non joignable : tout le décor se fige avec la caméra (comme P16).
- **`osm_streamer.gd`** :
  - La tâche de fond de chaque tronçon place aussi ses animaux (P11), posés sur les tuiles proches du terrain.
  - `chunk_loaded` et `chunk_freed` font arriver et partir animaux et panneaux avec les tronçons, sans travail lourd sur le fil principal.
  - Eau qui scintille (P12) selon `living(preset).water_shimmer`.
- **`world_streamer.gd`, `road_builder.gd`** : matériau des marquages de P14 à la place du matériau de la route quand le décor vivant est actif. Les tronçons qui portent des chiffres peints ont leur propre copie du matériau (8 chiffres au plus par tronçon). `road_markings.gdshader` gagne `wetness` (chaussée assombrie et plus brillante sous la pluie).
- **`render_quality.gd`** : `weather_fog_range` et `apply_weather_fog`, pour la brume de P8 (`fog_boost`).
- **`hud_view.gd`** : pastille bleue « Abri 30 % » sous l'indicateur du vent, à sa place quand il n'y a pas de vent, cachée sans abri.
- **`main.gd`** :
  - création de `living_decor` et appel une fois par image ;
  - fin des bips suivie, pour les passants ;
  - message de test `weather` (météo imposée) ;
  - état du décor dans les captures de test (nombres affichés, météo, panneau le plus proche devant la caméra et hauteur de ses lettres à l'écran).
- **`visual_check.py`** : trois nouvelles scènes.
  - `abri` : pastille, texte, place sous l'indicateur du vent.
  - `pluie` : particules et chaussée mouillée.
  - `col` : panneau du sommet lisible, spectateurs.
  - Les images de référence sont à refaire (`--update-golden`), car la route porte maintenant des marquages et des panneaux.
- **Tests** :
  - `test_living_decor.gd` : 28 vérifications sur un parcours OSM de synthèse avec col, village, troupeau, forêt, éolienne, drapeau et lac. Coût de 0,23 ms par image ici en `high`.
  - `test_render_quality.gd` : brume.
- **Reste sur le PC cible (le propriétaire)** : [`docs/RECETTE_P17.md`](../RECETTE_P17.md).
  - Performance sur 30 min en `low` avec tout le décor, et budgets `low` à réduire si besoin.
  - Abri derrière un bot.
  - Décor sur le vélo.
  - Une heure sans plantage, mémoire stable.
