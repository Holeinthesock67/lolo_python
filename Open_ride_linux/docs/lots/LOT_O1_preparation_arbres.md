# Lot O1 – Arbres : préparer une tuile en moins de 150 ms

## 1. Objectif

Le cahier d'E3 fixe à 150 ms le temps CPU de préparation des arbres d'une tuile de 1 km en qualité `high`. Sur le PC cible (GTX 1060, processeur de 2017), `engine/tests/unit/test_tree_renderer.gd` mesure environ **210 ms** : le test échoue en local (la CI tolère 200 ms). Une préparation trop lente retarde l'apparition des arbres devant le cycliste et peut provoquer des à-coups quand plusieurs tuiles arrivent ensemble. Ce lot ramène la préparation sous 150 ms **sans changer le résultat** (mêmes arbres, au bit près).

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_E3_ciel_arbres_hud.md` (budget et seuil), `docs/lots/LOT_K3_placement_vegetation.md`, `docs/lots/LOT_E4_osm_eau_sons.md` §4.3 (semis hors des zones OSM).
2. Code : `engine/scripts/tree_renderer.gd` (`prepare_tile`), `engine/scripts/vegetation_placer.gd` (`place_tile`, `_place_noise`, `_place_area`, `_filter`, `_road_buckets`, `_in_ring`, `_packed_ring`), `engine/tests/unit/test_tree_renderer.gd`, `engine/tests/unit/test_vegetation_placer.gd`.

## 3. Prérequis

Aucun (E3 et E4 livrés). Ne touche ni `main.gd` ni le contrat.

## 4. Travail demandé

- **Mesurer d'abord** : ajouter au test une ventilation du temps (bruit, filtre route/pente, semis hors zones OSM, répartition en cases) imprimée dans la sortie, pour cibler l'effort.
- Pistes, à confirmer par la mesure :
  - dans `prepare_tile`, le test « dans une zone OSM » refait `_packed_ring(outer)` pour **chaque arbre et chaque zone** : préparer les anneaux une fois par tuile, avec leur boîte englobante, et éliminer d'abord par la boîte ;
  - éviter `theme.duplicate(true)` à chaque tuile (copie profonde du thème) : ne copier que la section `vegetation` ;
  - réduire les appels de `Callable` (`height_at`) dans les boucles chaudes : précalculer la grille 101 × 101 en accès direct quand c'est possible ;
  - dans `vegetation_placer.gd`, préallouer les `Packed*Array` (`resize`) au lieu d'`append` répétés.
- Le résultat doit rester **identique** : mêmes positions, hauteurs et échelles, dans le même ordre, pour toutes les tuiles des tests existants. Ajouter un test de non-régression qui compare une empreinte (somme de contrôle) des arbres produits à une valeur relevée avant l'optimisation, avec et sans zones OSM.
- Garder le seuil de 150 ms en local ; ramener le seuil de CI de 200 à 170 ms si la marge le permet (le noter dans la section « Livraison »).

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/tree_renderer.gd`, `engine/scripts/vegetation_placer.gd`, `engine/tests/unit/test_tree_renderer.gd`, `engine/tests/unit/test_vegetation_placer.gd`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, `world_streamer.gd`, les thèmes, le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier (sans écran), y compris `UNIT=test_tree_renderer` et `UNIT=test_vegetation_placer`.
2. Empreinte des arbres identique avant et après, pour une tuile sans zone, une tuile avec deux zones OSM (dont une avec trou) et une tuile en relief.
3. Temps de préparation mesuré par le test inférieur à 150 ms sur une machine de développement courante (valeur relevée dans la PR, avec la ventilation).
4. Aucun changement visible dans les tests graphiques (`engine/tests/run_visual_tests.sh`).

**Sur le PC cible (le propriétaire) :** `UNIT=test_tree_renderer engine/tests/run_engine_tests.sh` doit afficher moins de 150 ms ; puis une séance en `high` pour vérifier l'absence d'à-coups à l'arrivée des tuiles.

## 8. Hors périmètre

- Changer la densité, les modèles d'arbres ou le budget d'instances.
- Déplacer la préparation dans un autre fil (déjà asynchrone via `world_streamer.gd`).
