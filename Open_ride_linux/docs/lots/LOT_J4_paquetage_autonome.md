# Lot J4 – Paquets installables hors du dépôt (dépendances et ressources)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Paquets installables hors du dépôt (dépendance `jsonschema`, ressources embarquées) | Python | — | Petite | **Livré le 8 novembre** (issue #50 ; dépendance `jsonschema` faite le 23 octobre) |

## 1. Objectif

Les deux paquets ne fonctionnent qu'installés en mode éditable depuis le dépôt, et l'un dépend d'une bibliothèque déclarée seulement pour les tests (audit J, constats J-M3 et J-F2) :
- `compiler/src/openride_compiler/theme.py` importe `jsonschema` au chargement, et `cli.py` importe `theme.py` : **sans l'extra `[dev]`, toute commande `openride-compiler` échoue** (`ModuleNotFoundError`), alors que `jsonschema` n'est déclaré que dans `dev` ;
- `theme.py` lit `docs/contracts/world/theme.schema.json` par `Path(__file__).parents[3]`, et `tools/workouts.py` lit `core/workouts/` par `parents[3]` : hors installation éditable (roue `pip install .`), `theme-check` et `workouts install` ne trouvent pas leurs fichiers.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `core/pyproject.toml`, `compiler/pyproject.toml`, `constraints.txt`.
3. Code : `compiler/src/openride_compiler/theme.py`, `core/src/openride_core/tools/workouts.py`, `core/src/openride_core/tools/route_vectors.py` (même procédé, mais outil de développement : hors périmètre).
4. `docs/lots/LOT_H7_schema_themes.md` et `LOT_H8_outils_entrainements.md` (livraisons).

## 3. Prérequis

Aucun. Partir de `main` à jour.

## 4. Travail demandé

- `jsonschema>=4` passe dans les dépendances d'exécution du compilateur (`[project] dependencies`) ; il reste dans `dev` du core.
- **Ressources embarquées :**
  - copie de `theme.schema.json` dans `compiler/src/openride_compiler/data/theme.schema.json`, déclarée en `package-data` ;
  - copie des 5 `.zwo` de référence dans `core/src/openride_core/data/workouts/`, déclarée en `package-data` ;
  - lecture par `importlib.resources` ; les fichiers de `docs/contracts/` et `core/workouts/` restent la **référence** (contrat et bibliothèque) ;
  - un test vérifie que chaque copie est identique octet pour octet à sa référence, pour qu'elles ne divergent jamais (le message d'échec donne la commande de recopie).
- Alternative acceptée si elle est justifiée dans le rapport : générer les copies à la construction. Pas de lien symbolique (le dépôt est aussi cloné sous Windows par le propriétaire).
- `constraints.txt` inchangé (aucune nouvelle dépendance).

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/data/theme.schema.json`, `core/src/openride_core/data/workouts/*.zwo`, `core/tests/test_packaging.py`, `compiler/tests/test_packaging.py`.
- **Modifiés :** `compiler/pyproject.toml`, `core/pyproject.toml` (`package-data`), `compiler/src/openride_compiler/theme.py`, `core/src/openride_core/tools/workouts.py`, `docs/SUIVI_AVANCEMENT.md` (une ligne), `CLAUDE.md` (une phrase sur les copies embarquées).

## 6. Modifications de contrat autorisées

Aucune. `theme.schema.json` de `docs/contracts/` reste la référence.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/` et `compiler/`.
2. Test d'identité des copies (rapide, toujours exécuté).
3. Test marqué `slow` : construire la roue de chaque paquet (`pip wheel --no-deps --no-build-isolation`, sans réseau), l'installer dans un environnement virtuel temporaire **avec `--no-deps` pour le paquet et les seules dépendances déclarées** (déjà présentes dans le cache pip ou l'environnement courant ; le test est sauté proprement si l'installation demande le réseau), puis depuis un dossier hors du dépôt :
   - `openride-compiler theme-check <copie de engine/themes/default>` renvoie 0 ;
   - `python -m openride_core.tools.workouts install` vers un dossier temporaire copie 5 fichiers.
4. `python -c "import openride_compiler.cli"` réussit dans un environnement sans les extras `dev` (même test, ou test qui masque `pytest`).

## 8. Hors périmètre

- Publication sur PyPI, paquet Debian, lanceur de bureau (lot G).
- `route_vectors.py` (outil de développement, utilisé depuis le dépôt).

## 9. Livraison partielle (23 octobre 2026)

- **Fait directement :** `jsonschema>=4` passe dans les dépendances d'exécution du compilateur (`compiler/pyproject.toml`) ; `openride-compiler` démarre sans l'extra `[dev]`.
- **Reste à confier :** ressources embarquées (`theme.schema.json`, `.zwo` de référence) avec test d'identité, et essai d'installation par roue (critères 2 et 3).

## 10. Livraison (8 novembre 2026)

- **Copies embarquées :** `compiler/src/openride_compiler/data/theme.schema.json` et `data/default_theme.json` (copie de `engine/themes/default/theme.json`), `core/src/openride_core/data/workouts/` (les 10 entraînements de `core/workouts/`) et `core/src/openride_core/data/plans/` (les 2 plans de `core/plans/`), déclarées en `package-data`. Les dossiers du dépôt restent la référence.
- **Tests :** `core/tests/test_packaging.py` et `compiler/tests/test_packaging.py` vérifient chaque copie octet pour octet (le message d'échec donne la commande de recopie), que le code lit bien les copies, et l'import de `openride_compiler.cli` avec `pytest`, `hypothesis` et `Pillow` masqués (critère 4). Le test `slow` de chaque paquet (critère 3) passe par `scripts/essai_roue.py` : copie du paquet hors du dépôt, `pip wheel --no-deps --no-build-isolation --no-index`, environnement virtuel neuf sans pip, roue installée par `pip --python … install --no-deps --no-index`, dépendances déclarées prises dans les `site-packages` de l'environnement courant par un `.pth` (les installations éditables du dépôt ne sont donc pas visibles) ; puis, depuis un dossier hors du dépôt, `openride-compiler theme-check` sur une copie du thème par défaut (code 0), `workouts install` (toute la bibliothèque copiée) et `plans.install_builtin` (les 2 plans).

**Écarts assumés :**

- **Thème par défaut embarqué aussi :** `theme-check` lit le `theme.json` par défaut pour signaler les clés inconnues ; sans cette copie, le critère 3 échouait hors du dépôt. `DEFAULT_THEME_DIR` (dossier du thème avec ses textures, utilisé par `theme_packs.py` et `resolve_theme`) reste celui de l'engine.
- **Plans embarqués aussi :** `plan install` et « Réglages › Contenus » (lot O25) lisent `core/plans/` de la même façon que les entraînements ; même procédé pour rester cohérent. Le cahier comptait 5 `.zwo` : la bibliothèque en compte 10 depuis les lots O9 à O11 (8 `.zwo`, un `.erg`, un `.mrc`), toutes copiées.
- **Lecture par `Path(__file__).parent / "data"` au lieu d'`importlib.resources` :** c'est déjà la règle de tout le paquet pour ses fichiers embarqués (`progression.toml`, `coach.toml`, `collection.toml`, `places.json`, packs de parcours du compilateur) ; une roue s'installe toujours décompressée, le résultat est le même. Un seul `BUILTIN_WORKOUTS_DIR`, dans `workout.py`, importé par `plans.py` et `tools/workouts.py` (il y en avait deux).
- **Sans `setuptools` dans l'environnement**, le test `slow` est sauté avec la commande à lancer (`pip install "setuptools>=68"`) : la construction sans réseau ne peut pas aller chercher le moteur de construction. C'est le cas des Python 3.12 et plus de la CI ; l'essai complet se fait sur le PC.
- Dépendent encore du dépôt (hors périmètre, pour l'installeur final) : le dossier de l'engine (`launcher.DEFAULT_ENGINE_DIR`), `scripts/config.example.toml` et `session.DEFAULT_THEME_JSON`, tous liés à l'engine Godot livré à côté.
