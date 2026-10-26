# Lot P17 – Intégration, deuxième vague : abri, météo, animaux, objets mobiles, bord de route

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
