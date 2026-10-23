# Lot I1 – Tests de cohérence entre la documentation et le code

## 1. Objectif

Faire échouer les tests dès que la documentation s'écarte du code, au lieu de le découvrir lors d'un audit. Trois dérives ont été constatées le 23 octobre : modules et commandes absents de `CLAUDE.md`, tâche déjà faite encore listée « à faire », exemple de configuration qui peut diverger des valeurs par défaut.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `CLAUDE.md` (sections « Architecture » et « Commandes »), `README.md` (section des commandes).
3. `docs/SRS_v1.1.md` §11 (exemple de `config.toml`).
4. Code : `core/src/openride_core/config.py` (dataclasses et `from_dict`), `core/src/openride_core/__main__.py`, `compiler/src/openride_compiler/cli.py` (`build_parser`), `core/src/openride_core/tools/*.py`.

## 3. Prérequis

Aucun. Partir de `main` à jour.

## 4. Travail demandé

Nouveau fichier `core/tests/test_docs_coherence.py` (le core est installé dans tous les environnements de test ; les tests qui ont besoin du compilateur sont ignorés avec `pytest.importorskip` s'il n'est pas installé).

**Contrôles :**

| Contrôle | Méthode |
| --- | --- |
| Exemple `config.toml` de la SRS §11 | Extraire le bloc ```` ```toml ```` qui suit « ## 11. » ; le lire avec `tomllib` ; chaque clé doit exister dans `Config` et sa valeur être égale à la valeur par défaut. Exceptions permises et listées en tête du test : les valeurs que la SRS présente explicitement comme « exemples à adapter » (FTP, masses). Toute clé de `Config` absente de l'exemple est signalée. |
| Modules cités dans `CLAUDE.md` | Tout nom de fichier `*.py` cité dans la section « Architecture » existe dans `core/src/openride_core/`, `core/src/openride_core/tools/` ou `compiler/src/openride_compiler/`. Inversement, chaque module de `core/src/openride_core/` (hors `__init__`, `__main__`) est cité. |
| Commandes de `README.md` et `CLAUDE.md` | Pour chaque ligne de bloc de code qui commence par `openride-core`, `openride-compiler` ou `python -m openride_core.tools.<x>` : la sous-commande existe et chaque option `--xxx` citée est acceptée par l'`argparse` correspondant (construire le parseur, ou appeler avec `--help` et lire la sortie). Les alternatives écrites `a|b` et les crochets `[...]` sont gérés. |
| Statut des lots | Chaque lot noté « Livré » dans `docs/lots/00_INDEX.md` a une section « Livraison » dans son cahier ; chaque cahier de `docs/lots/` figure dans l'index. |
| Vecteurs et schémas | Chaque fichier de `docs/contracts/**/*.schema.json` est un JSON Schema valide (`jsonschema.Draft202012Validator.check_schema`, ou la version déclarée par le fichier). |

Les messages d'échec disent quoi corriger et où (fichier et ligne de la documentation).

**Si un contrôle échoue sur `main` au moment du lot :** corriger la **documentation** (pas le code) et lister chaque correction dans le rapport.

## 5. Fichiers concernés

- **Nouveau :** `core/tests/test_docs_coherence.py`.
- **Modifiés :** `CLAUDE.md`, `README.md`, `docs/SRS_v1.1.md` §11, `docs/lots/00_INDEX.md`, seulement pour corriger un écart trouvé ; `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune. Les schémas JSON ne sont que lus.

## 7. Critères d'acceptation

1. `cd core && pytest -q` passe en entier, en local et dans l'intégration continue.
2. Chaque contrôle du §4 a au moins un test, et un test « négatif » montre qu'il échoue sur un document modifié pour l'occasion (texte passé en paramètre à la fonction de contrôle, sans toucher aux vrais fichiers).
3. Ajouter une option fictive `--inexistante` dans une ligne de commande du README fait échouer le test (démonstration dans le rapport).
4. Durée totale des nouveaux tests : moins de 5 s.

## 8. Hors périmètre

- Vérification orthographique ou de style.
- Liens internes des documents Markdown (possible plus tard).

## 9. Livraison (23 octobre 2026, PR #20)

- `core/tests/test_docs_coherence.py` livré avec les 5 contrôles automatiques et leurs tests négatifs.
- Écarts corrigés dans la documentation : ajout de `mock_driver.py` dans `CLAUDE.md`, alignement de `drivers.trainer = "mock"` et `drivers.input = "keyboard"` dans `docs/SRS_v1.1.md` §11, et ajout des sections `Livraison` dans `LOT_B1` et `LOT_D`.
