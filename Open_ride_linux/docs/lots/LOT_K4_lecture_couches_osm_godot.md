# Lot K4 – Lecture des couches OpenStreetMap dans l'engine (sans affichage)

## 1. Objectif

Le compilateur produit les couches `buildings`, `vegetation`, `poi` et `water` (lots I3 et I4), mais l'engine ne sait pas les lire. Ce lot écrit le lecteur GDScript, testé sans écran contre des `.world` produits par le vrai compilateur. Le rendu (bâtiments extrudés, forêts, eau, sons des points d'intérêt) reste au lot E4.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_I3_osm_batiments_forets.md` et `LOT_I4_osm_poi_eau.md` (livraisons).
2. `docs/contracts/world_format_v1.md` §2 (manifeste, couches présentes), §6, §7, §8 et §10 (règles de lecture : champ inconnu ignoré, version majeure) ; schémas `docs/contracts/world/buildings.schema.json`, `vegetation.schema.json`, `poi.schema.json`, `water.schema.json`.
3. Code : `engine/scripts/route_data.gd` (lecture du manifeste et repli), `engine/scripts/theme_loader.gd` (validation sans `jsonschema`) ; `compiler/tests/data/osm/*.json` et `compiler/tests/test_osm*.py` (production des couches à partir de réponses Overpass enregistrées).

## 3. Prérequis

Lot K1 livré.

## 4. Travail demandé

- Nouveau `engine/scripts/osm_layers.gd` (`extends RefCounted`, sans `class_name`) :
  - `load_chunk(world_dir: String, layer: String, k: int) -> Dictionary` : lit `<layer>/chunk_<k>.json`, valide les champs obligatoires du format (types, anneaux d'au moins 3 points, `density` dans [0, 1], `kind` connu sinon élément ignoré et compté), renvoie `{ok, items, ignored, error}` ;
  - `layers_present(manifest: Dictionary) -> Array` ;
  - `chunks_for_window(s_from: float, s_to: float, route) -> Array[int]` : tronçons de 1 km à charger pour une fenêtre de distance (boucle comprise) ;
  - un fichier absent ou illisible donne `ok = false` et un message, jamais une erreur Godot ; une version majeure supérieure à 1 est refusée.
- **Données de test :** un script `engine/tests/make_osm_world.py` (bibliothèque standard + compilateur installé) produit dans un dossier temporaire un `.world` avec les quatre couches, à partir des réponses Overpass enregistrées du compilateur (`compiler/tests/data/osm/`) et de l'altitude synthétique des tests, **sans réseau**. Le test GDScript reçoit ce dossier en argument ; il est appelé par une étape de `run_engine_tests.sh` qui génère d'abord les données (seule modification de ce script, à placer après l'étape « Tests unitaires » de K1).

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/osm_layers.gd`, `engine/tests/make_osm_world.py`, `engine/tests/test_osm_layers.gd`.
- **Modifiés :** `engine/tests/run_engine_tests.sh` (une étape), `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, scripts de rendu d'E1, code du compilateur (s'il manque une fonction pour produire les données de test, le signaler).

## 6. Modifications de contrat autorisées

Aucune. Un écart entre le format écrit et ce que produit le compilateur est signalé, pas corrigé ici.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier, sans réseau.
2. Pour chaque couche, le nombre d'éléments lus par `osm_layers.gd` égale celui que compte le compilateur dans le même `.world` (relu en Python par `make_osm_world.py`, qui écrit les attendus dans un fichier JSON lu par le test).
3. Fichiers corrompus fabriqués par le test dans `user://` (JSON invalide, anneau de 2 points, `density` 1,5, `kind` inconnu, version `2.0`) : chaque cas donne le résultat attendu, sans `SCRIPT ERROR`.
4. `chunks_for_window` : bornes exactes sur un parcours ouvert et à travers l'arrivée d'une boucle.
5. Lecture d'un tronçon de 200 bâtiments en moins de 20 ms (mesure affichée).

## 8. Hors périmètre

- Triangulation, maillages, matériaux, sons (E4).
- Placement des arbres dans les zones (K3).
