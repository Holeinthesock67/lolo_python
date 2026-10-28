# Lot P27 – Intégration et recette de la deuxième vague du décor vivant

## 1. Objectif

Dernier lot de la deuxième vague du décor vivant (P22 à P27, demande du propriétaire du 27 octobre : « ça manque de vie »). Chaque lot P22 à P26 a été testé seul ; ce lot vérifie qu'ensemble ils restent dans les budgets de la GTX 1060, règle les parts et les densités sur l'avis du propriétaire, et met la documentation à jour :

- mesure de toute la série activée, au banc simulé puis sur le PC cible ;
- réglage des budgets `LIVING` (`birds`, `animals`, `vehicles`, `distant_vehicles`, `aircraft`) si la mesure dépasse, en réduisant `low` d'abord ;
- fiche de recette sur le vélo, en blocs de moins de 10 minutes ;
- index des lots, suivi, guide d'utilisation et compteurs de tests.

## 2. À lire

1. Cahiers de P22 à P26, `docs/lots/LOT_P17_integration_decor_complet.md` (première intégration), `docs/RECETTE_P17.md` (forme de la fiche de recette), `docs/OUTILS_DE_TEST.md` (banc simulé, sonde X13, seuils X2).
2. Code : `engine/scripts/living_decor.gd`, `quality_presets.gd`, `perf_probe.gd` ; `engine/tests/sim_bench.py`, `engine/tests/perf_budgets.json`, `engine/tests/visual_check.py`.

## 3. Prérequis

P22, P23, P24, P25 et P26 livrés.

## 4. Travail demandé

- **Branchement** : relire `living_decor.gd` de bout en bout après les cinq lots ; un seul ordre de mise à jour par image (météo, oiseaux, animaux, véhicules de la route, véhicules lointains, ciel), une seule lecture de la météo et du vent ; aucun nœud créé après `configure` (`test_living_decor.gd`, avec toutes les sortes activées).
- **Banc simulé** : scénario `decor_vivant_2` dans `engine/tests/sim_bench_scenarios/` sur le monde de test OSM (`make_osm_world.py`, avec prés, champs et routes voisines), 5 min à 30 km/h, en `low`, `medium` et `high`, avec la sonde X13 ; tableau avant (P23 seul, fusionné) et après (toute la série) : images/s médianes, p99 du temps d'image, temps CPU et GPU, appels de dessin, objets du décor vivant actifs.
- **Budgets** : enveloppe de la deuxième vague, P23 à P26 ensemble, de 0,8 ms de processeur par image au plus en `medium` (somme des lignes `fauna_frame_200`, `traffic_frame`, `distant_traffic_frame`, `sky_traffic_frame` de `perf_budgets.json`) ; sur le PC, 55 images/s ou plus en `low` et p99 sous 25 ms avec tout le décor vivant (spécification générale). Si la mesure dépasse, réduire les budgets `LIVING` de `low` d'abord, puis de `medium`, et noter les valeurs retenues dans ce cahier.
- **Captures** : scène `decor_vivant` de `visual_check.py` (route de campagne avec un troupeau, un véhicule croisé, un véhicule lointain et un objet du ciel en vue fixe), vérifiée par présence d'objets et sans image de référence (le décor bouge).
- **Fiche de recette** `docs/RECETTE_P27.md`, sur le modèle de `docs/RECETTE_P17.md` : trois blocs de moins de 10 minutes (campagne en `medium`, montée avec parapentes, thème à brume pour les phares), chacun avec ce qu'il faut voir et entendre, et une ligne pour noter l'avis sur la densité des véhicules (`BASE_RATE` de P25) et des animaux.
- **Documentation** : `docs/lots/00_INDEX.md` (P22 à P27 livrés), `docs/SUIVI_AVANCEMENT.md`, `docs/GUIDE_UTILISATION.md` (paragraphe du décor vivant : ce qu'on voit, comment le couper avec `[render] living = false`), `engine/tests/README.md`, compteurs de tests.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/living_decor.gd` (ordre et lecture commune seulement), `quality_presets.gd` (budgets, si la mesure le demande) ; `engine/tests/unit/test_living_decor.gd`, `engine/tests/visual_check.py`, `engine/tests/perf_budgets.json`, `engine/tests/make_osm_world.py` (si le monde de test manque d'une sorte) ; `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`, `docs/GUIDE_UTILISATION.md`, `engine/tests/README.md`, `README.md` (compteurs).
- **Nouveaux :** `engine/tests/sim_bench_scenarios/decor_vivant_2.json` (forme des autres scénarios du dossier), `docs/RECETTE_P27.md`.
- **Interdits :** le comportement des animaux, des véhicules et du ciel (lots P23 à P26 : un défaut trouvé ici est corrigé dans une PR à part, citée dans ce cahier), le compilateur, le core, les contrats.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh`, `pytest -q` (core et compilateur) et `visual_check.py` passent en entier.
2. Banc simulé : tableau avant et après dans ce cahier pour les trois préréglages ; enveloppe de 0,8 ms par image tenue en `medium` sur la machine des tests.
3. Aucun nœud créé après le démarrage avec toutes les sortes activées ; `[render] living = false` : aucun objet de P23 à P26 et rendu identique à la 1.0.
4. Documentation : index, suivi, guide et compteurs à jour ; `core/tests/test_docs_coherence.py` passe.

**Sur le PC cible (le propriétaire) :** la fiche `docs/RECETTE_P27.md` en `medium` puis en `low` ; mesure `sim_bench.py --native --probe` en `low` : 55 images/s ou plus, p99 sous 25 ms. Avis sur les densités, à reporter dans les budgets.

## 8. Hors périmètre

- Nouvelles sortes d'animaux, de véhicules ou d'objets du ciel ; texture des prés et des cultures (plus tard, série Y).
- Nuit (P19) et saisons (P18), version 2.0 : leurs effets sur les phares, les troupeaux et les oiseaux se règlent dans P19.
