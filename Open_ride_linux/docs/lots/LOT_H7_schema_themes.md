# Lot H7 – Schéma, validateur et thème par défaut

## 1. Objectif

Préparer le lot E2 (shader triplanaire et chargeur de thèmes dans Godot) sans toucher à Godot :
- un schéma JSON du fichier `theme.json` ;
- un validateur en ligne de commande ;
- un thème `default` complet, en couleurs unies, qui servira de référence à E2.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/contracts/world_format_v1.md` §9 (thèmes) en entier, et §12 (journal des changements).
3. `docs/SRS_v1.1.md` §8.1 (shader triplanaire) et §10 (thèmes et textures).
4. Les schémas existants dans `docs/contracts/world/` (style à reprendre) et leur utilisation dans `compiler/src/openride_compiler/verify.py`.

## 3. Prérequis

Aucun. Partir de `main` à jour.

## 4. Travail demandé

### 4.1 Schéma : `docs/contracts/world/theme.schema.json` (nouveau)

- Fidèle à l'exemple et aux règles du §9 : clés `version`, `name`, `terrain` (`grass`, `rock`, `snow`, seuils), `road`, `buildings`, `vegetation`, `sky`.
- **Toutes les clés sont facultatives** sauf `version` (règle du §9 : une clé absente prend la valeur par défaut de l'engine).
- Couleurs au format `#rrggbb` ; textures en chemin relatif au dossier du thème, ou `null`.
- Bornes raisonnables et documentées (échelles positives, seuil de pente de 0 à 90°, densités positives, etc.).
- `additionalProperties` autorisé, pour la compatibilité future, avec un avertissement du validateur.

### 4.2 Validateur : `compiler/src/openride_compiler/theme.py` (nouveau)

- Fonction `check_theme(theme_dir: Path) -> list[Issue]` (gravité `error` ou `warning`, message en français) :
  - `theme.json` absent ou mal formé : erreur ;
  - non-conformité au schéma : erreur ;
  - texture citée mais absente : **avertissement** (l'engine utilisera la couleur unie, §9) ;
  - texture présente mais pas en PNG ou JPEG, ou de taille non puissance de deux : avertissement ;
  - clé inconnue : avertissement.
- Fonction `resolve_theme(theme_dir) -> dict` : le thème complet, valeurs par défaut comprises. Les valeurs par défaut sont celles de l'exemple du §9 ; les écrire une seule fois, dans le thème `default`, et les relire de là.
- Sous-commande `openride-compiler theme-check DOSSIER` dans `cli.py` : affiche les problèmes ; code de sortie 1 s'il y a une erreur.

### 4.3 Thème par défaut : `engine/themes/default/theme.json` (nouveau)

- Toutes les clés du §9 renseignées, **sans texture** (`texture: null` partout), couleurs de l'exemple.
- Placé dans l'engine pour qu'E2 le charge par `res://themes/default/`.

### 4.4 Journal des changements du format

Ajouter une ligne au §12 de `world_format_v1.md` : publication du schéma `theme.schema.json`, sans changement de format.

## 5. Fichiers concernés

- **Nouveaux :** `docs/contracts/world/theme.schema.json`, `compiler/src/openride_compiler/theme.py`, `compiler/tests/test_theme.py`, `engine/themes/default/theme.json`.
- **Modifiés :** `compiler/src/openride_compiler/cli.py` (sous-commande), `docs/contracts/world_format_v1.md` (une ligne au §12, rien d'autre), `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Ajout compatible seulement : publication du schéma des thèmes et ligne au journal des changements. Si le §9 paraît incomplet ou ambigu (par exemple les valeurs par défaut des clés absentes de l'exemple), **s'arrêter et poser la question**.

## 7. Critères d'acceptation

1. `cd compiler && pytest -q` passe en entier.
2. L'exemple de thème du §9, recopié tel quel, est valide.
3. Le thème `default` est valide, sans aucun avertissement.
4. Un thème réduit à `{"version": "1.0"}` est valide, et `resolve_theme` le complète avec les valeurs du thème `default`.
5. Une couleur `"vert"`, un seuil de pente de 120° ou un `theme.json` mal formé donnent une erreur, et `theme-check` sort avec le code 1.
6. Une texture citée mais absente donne un avertissement, et `theme-check` sort avec le code 0.

## 8. Hors périmètre

- Chargement du thème et shader dans Godot (lot E2).
- Production de vraies textures (thèmes avec packs de textures, sprint 6).


## 9. Livraison (23 octobre 2026, PR #17)

- `docs/contracts/world/theme.schema.json` : schéma JSON Draft 2020-12 du format `.world` v1 §9.
- `engine/themes/default/theme.json` : thème par défaut complet servant d'unique source des valeurs par défaut.
- `compiler/src/openride_compiler/theme.py` et sous-commande `openride-compiler theme-check DOSSIER` : validation du schéma (`error`), contrôle des clés inconnues et des textures PNG/JPEG (présence et dimensions en puissances de 2 lues en pur Python, `warning`), fusion récursive `resolve_theme`.
- `compiler/tests/test_theme.py` : 17 tests unitaires passants.
