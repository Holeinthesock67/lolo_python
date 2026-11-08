# Lot O37 – Mondes demo dans le jeu de base

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Mondes demo gardés dans le jeu de base, nettoyés des artefacts de test et renommés en parcours explicites | Python + GDScript | U19, O25 | Moyenne | En PR (8 novembre, version 5.0, avant J9) |

Demande du propriétaire du 5 novembre 2026 (9 h 28 et 9 h 30) : garder à la fin les mondes demo déjà créés dans le jeu de base, les nettoyer des artefacts de test et leur donner un nom de parcours explicite ; **à faire avant l'installeur** (lot J9). Cahier rédigé le 8 novembre (la demande n'était notée que dans la feuille de route).

## 1. Objectif

Que les parcours livrés avec le jeu ressemblent à des parcours, pas à des bancs d'essai.

## 2. À lire

`core/src/openride_core/demo_world.py` (`demo`, `ensure_demo_world`, `write_biome_demo_worlds`) ; `engine/tests/make_biome_world.py` (`DEMO_SET` : `demo-biomes-tour`, `demo-biomes-gravel`, `demo-biomes-cote`, `demo-biomes-alpin`, lot U19) ; `core/src/openride_core/contents.py` (contenus de départ, O25) ; `docs/lots/LOT_A2_trace_demo.md`.

## 3. Travail demandé

- **Inventaire** des mondes demo et de ce qui y relève du test : consignes et panneaux d'essai, marqueurs de mesure, kilomètres repères des fiches de recette, noms techniques.
- **Noms explicites** affichés au menu (par exemple « Tour des six paysages », « Boucle gravel », « Route de la côte », « Montée alpine », « Col de démonstration ») ; l'identifiant de fichier peut rester, l'engine affiche le nom du manifeste. Liste des noms validée par le propriétaire.
- **Génération hors des tests :** le générateur des démos de biomes vit aujourd'hui dans `engine/tests/` ; le déplacer dans le compilateur ou le core pour qu'un jeu installé sans les tests puisse les produire.
- **Artefacts de test** gardés pour les bancs et les recettes dans une variante séparée (par exemple `--recette`), jamais dans le jeu de base.
- Les fiches de recette qui citent `demo` ou `demo-biomes-gravel` sont mises à jour avec les nouveaux noms.

## 4. Critères d'acceptation

1. Au premier lancement d'une installation neuve, les parcours demo apparaissent sous leur nom explicite, sans consigne de test à l'écran.
2. Bancs et recettes existants verts avec la variante de recette.
3. Captures de chaque parcours validées par le propriétaire.

## 5. Fichiers touchés

`core/src/openride_core/demo_world.py`, `core/src/openride_core/contents.py`, `engine/tests/make_biome_world.py` (déplacé), fiches de recette, `docs/GUIDE_UTILISATION.md`.

## 6. Réalisation (8 novembre)

**Inventaire.** Les cinq parcours livrés sont `demo` (core et engine, `demo_world.py`, copie embarquée `engine/demo/demo.world`) et les quatre `demo-biomes-*` (installés par les contenus de départ, O25). Rien d'un banc dans leurs couches : pas de consigne, de panneau d'essai ni de marqueur de mesure ; les segments sont ceux de la détection automatique (« Montée 1 », « Sprint 1 »), les bornes kilométriques celles de tout parcours. Ce qui relevait du test : le nom affiché au menu (identifiant technique `demo`, `demo-biomes-tour`…), les lieux « Port Fictif », « Pointe Fictive », « Mas Fictif », « Hameau Fictif », « Étang Fictif » et « Col Fictif » (ce dernier écrit sur le panneau du sommet) et le générateur `make_biome_world` des tests de l'engine.

**Noms affichés** (`name` du manifeste ; les identifiants de fichier ne changent pas) : `demo` « Col du lacet » ; `demo-biomes-tour` « Tour des six paysages » ; `demo-biomes-gravel` « Chemins des six paysages » (ce n'est pas une boucle) ; `demo-biomes-cote` « Route de la côte » ; `demo-biomes-alpin` « Montée alpine ». Lieux : un nom inventé par bloc (`PLACE_NAMES`), le sommet alpin « Col des Edelweiss ». Liste à valider par le propriétaire.

**Génération hors des tests.** `compiler/src/openride_compiler/demo_biomes.py` (générateur) et `fake_osm.py` (réponse Overpass fabriquée, route en S, partagée avec `engine/tests/make_sim_world.py`) ; `engine/tests/make_biome_world.py` n'en est plus que la ligne de commande des essais. Le core l'importe directement (`demo_world._biome_demo_module`), sans chercher le dossier de l'engine.

**Variante de recette.** `recette=True`, `--recette` (`openride-core demo-biomes`, `make_biome_world.py`) : nom de parcours égal à l'identifiant et lieux « Fictif », géométrie identique au bit près à celle d'avant le lot. `recette_u18.py`, `reglage_image.py` et `cout_rendu.py` la prennent ; `run_engine_tests.sh` contrôle l'herbe sur les parcours du jeu de base.

**Installations existantes.** `FAKE_WORLD_VERSION` 0.3.0 : la démo du dossier des parcours est réécrite par `ensure_demo_world`. Une démonstration des biomes dont le manifeste vient de `make_biome_world` est remplacée par les contenus de départ (`demo_world.biome_demo_outdated`) ; un parcours du joueur au même identifiant n'est jamais touché.

**Affichage.** Seuls des textes changent (nom au menu et sur la carte du départ, nom du sommet) : aucun coût GPU à mesurer en `low`, `medium` et `high`, mais les captures de chaque parcours sont à valider par le propriétaire avant la fusion (critère 3).

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 8, 13 et 16 ms depuis le 8 novembre) et ses captures sont validées par le propriétaire avant la fusion.
