# Lot I5 – Chargeur de thèmes en GDScript

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Chargeur de thèmes en GDScript (sans shader) | GDScript | H7 (livré), E1 fusionné | Petite | **Livré le 23 octobre** (PR #24) |

## 1. Objectif

Donner à l'engine Godot la lecture des thèmes (`theme.json`) avec les mêmes règles que le validateur Python du lot H7, testée sans écran. Le shader triplanaire et l'application du thème à l'écran viendront dans le lot E2 : ce lot ne livre que la lecture, la fusion avec le thème par défaut et le chargement des textures avec repli sur une couleur unie.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/contracts/world_format_v1.md` §9 (thèmes, règles) et le schéma `docs/contracts/world/theme.schema.json`.
3. `docs/SRS_v1.1.md` §8.1 et §10 (thèmes), §11 (`render.theme`, dossier `~/OpenRide/Themes/<nom>/`).
4. Lot H7 et son code : `compiler/src/openride_compiler/theme.py` (règles et messages), `compiler/tests/test_theme.py` (cas de test), `engine/themes/default/theme.json`.
5. Côté Godot : `engine/scripts/route_data.gd` (style des scripts chargés par `preload`), `engine/tests/run_engine_tests.sh`, `engine/tests/README.md`.

## 3. Prérequis

- Lot H7 livré.
- **Lot E1 fusionné** (PR #7) : ce lot ajoute une étape à `run_engine_tests.sh`, que E1 modifie aussi. Partir de `main` à jour après cette fusion.

## 4. Travail demandé

### 4.1 Script `engine/scripts/theme_loader.gd` (nouveau, sans `class_name`, chargé par `preload`)

```gdscript
# Renvoie un dictionnaire : {"theme": Dictionary complet, "warnings": PackedStringArray, "errors": PackedStringArray}
static func load_theme(theme_dir: String) -> Dictionary
# Thème complet pour un nom de configuration : ~/OpenRide/Themes/<nom>/, sinon res://themes/default/
static func load_named(name: String) -> Dictionary
# Texture d'un matériau du thème, ou null si absente (l'appelant utilise alors la couleur)
static func texture_for(theme: Dictionary, theme_dir: String, key_path: String) -> Texture2D
```

**Règles (identiques au lot H7) :**
- clé absente : valeur du thème `default` (lu dans `res://themes/default/theme.json`, jamais recopié en dur dans le script) ;
- texture absente, illisible ou `null` : avertissement, couleur unie `color` utilisée ;
- couleur mal formée, valeur hors bornes du schéma, `theme.json` mal formé : erreur ; le chargeur retombe alors entièrement sur le thème `default` et le dit dans le journal de l'engine ;
- clé inconnue : avertissement ;
- les textures d'un dossier utilisateur (hors `res://`) sont chargées avec `Image.load_from_file` puis `ImageTexture.create_from_image`.

### 4.2 Tests sans écran : `engine/tests/unit/test_theme_loader.gd` (nouveau ; déplacé dans `engine/tests/unit/` par le lot K1)

- Reprendre les cas de `compiler/tests/test_theme.py` (thème minimal `{"version": "1.0"}`, thème complet, couleur invalide, seuil de pente hors bornes, texture manquante, clé inconnue, JSON mal formé), avec des dossiers de thème créés dans `user://` ou un dossier temporaire par le test.
- Vérifier que le thème complet obtenu pour `{"version": "1.0"}` est égal, clé par clé, au thème `default`.
- Un petit PNG 4 × 4 écrit par le test sert de texture réelle.
- Ajouter l'étape « Thèmes (lot I5) » à `engine/tests/run_engine_tests.sh`, sur le modèle des étapes existantes (code de sortie, recherche de `SCRIPT ERROR`).

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/theme_loader.gd`, `engine/tests/unit/test_theme_loader.gd` (déplacé par le lot K1).
- **Modifiés :** `engine/tests/run_engine_tests.sh` (une étape), `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdit :** `main.gd` et les scripts de rendu de E1 (le branchement à l'écran est pour E2).

## 6. Modifications de contrat autorisées

Aucune. Une divergence entre le §9, le schéma et le validateur Python est signalée, pas tranchée.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier avec Godot 4.3 sans écran, en local et dans l'intégration continue.
2. Chaque cas de `test_theme.py` a son équivalent GDScript, avec la même issue (valide, avertissement ou erreur).
3. `load_named("inexistant")` renvoie le thème `default` avec un avertissement, sans erreur Godot.
4. Aucun `class_name` ; aucune ligne `WARNING:` ou `SCRIPT ERROR` dans la sortie de Godot.

## 8. Hors périmètre

- Shader triplanaire, matériaux, ciel, brouillard (lot E2).
- Packs de textures réels (sprint 6).

## 9. Livraison (23 octobre 2026, PR #24)

- `engine/scripts/theme_loader.gd` (`load_theme`, `load_named`, `texture_for`), fusion récursive avec `res://themes/default/theme.json`, validation des couleurs, bornes numériques et dimensions PNG/JPEG.
- `engine/tests/unit/test_theme_loader.gd` (40 vérifications sans écran ; déplacé par le lot K1) et étape « Thèmes (lot I5) », remplacée depuis par l'étape « Tests unitaires » du lot K1, dans `engine/tests/run_engine_tests.sh`.
