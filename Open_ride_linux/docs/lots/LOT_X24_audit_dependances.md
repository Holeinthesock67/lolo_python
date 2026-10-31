# Lot X24 – Audit des dépendances

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : Audit des dépendances (pip-audit, versions des actions) | Python + YAML | — | Petite | **Livré le 28 octobre** (branche `claude/project-thread-818r6t-x24`) ; issue #222 |

## 1. Objectif

`pip-audit` a été lancé une seule fois (24 octobre) et les actions GitHub sont référencées par version, sans rappel quand une nouvelle sort.

## 2. À lire

`constraints.txt`, `core/pyproject.toml`, `compiler/pyproject.toml`, `.github/workflows/*.yml`, `scripts/recette_pc.py`.

## 3. Travail demandé

- **`scripts/audit_dependances.py`** : `pip-audit -r constraints.txt` (vulnérabilités connues, avec l'identifiant et la version corrigée) ; liste des `uses: action@vN` des workflows comparée à la dernière version publiée (API GitHub sans jeton, ou `--hors-ligne` pour sauter ce contrôle) ; paquets de `constraints.txt` plus vieux de 12 mois. Sortie : `resume.txt` et `resume.json` ; code 1 si une vulnérabilité est trouvée.
- **Hebdomadaire** : job `dependances` dans le run du lundi de `openride.yml` (seulement sur `schedule` et `workflow_dispatch`).
- **PC** : étape facultative `deps` de `recette_pc.py` (`--seulement deps`), sautée sans réseau.

## 4. Fichiers

- **Nouveaux :** `scripts/audit_dependances.py`, `core/tests/test_audit_dependances.py` (lecture des workflows, comparaison des versions, sortie de pip-audit fabriquée).
- **Modifiés :** `.github/workflows/openride.yml`, `scripts/recette_pc.py`, `core/pyproject.toml` (extra `dev` : `pip-audit`), `constraints.txt`, `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. Tests sans réseau : workflows lus, action en retard signalée, vulnérabilité fabriquée → code 1.
2. `audit_dependances.py` tourne au cloud.

## 6. Hors périmètre

Mettre à jour les dépendances trouvées.

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x24`).

- **`scripts/audit_dependances.py`** fait trois contrôles :
  - **Vulnérabilités** : `python -m pip_audit -r constraints.txt --format json` ; chaque avis est donné par paquet, avec son identifiant et la version corrigée.
  - **Actions GitHub** : les `uses: propriétaire/action@vN` de `.github/workflows/*.yml` sont comparés à la plus grande étiquette `vN` publiée. Les étiquettes sont lues par `git ls-remote --tags`, sans jeton : l'API GitHub n'est pas joignable depuis toutes les sessions cloud.
  - **Paquets anciens** : date de publication de la version fixée, lue dans l'API JSON de PyPI ; un paquet publié il y a plus de 365 jours est listé.
- Sortie et codes : `resume.txt` et `resume.json` ; `--hors-ligne` saute les deux contrôles réseau. Code 1 si une vulnérabilité est connue, 2 si `pip-audit` manque, 75 sans réseau.
- **`pip-audit`** est dans l'extra `dev` du core, fixé à 2.10.1 dans `constraints.txt`.
- **Job `dependances`** de `openride.yml` : seulement sur `schedule` (lundi 5 h UTC) et `workflow_dispatch`. Le résumé est publié en artefact (30 jours).
- **`recette_pc.py`** : étape facultative `deps` (`--seulement deps`). Elle n'est pas dans la liste par défaut, et le code 75 la marque SAUTÉ.
- **Mesuré au cloud le 28 octobre** : aucune vulnérabilité connue sur les 13 paquets fixés. Les écarts trouvés seront corrigés dans une PR à part (hors périmètre) :
  - quatre actions en retard : `checkout` v5 → v7, `setup-python` v6 → v7, `cache` v4 → v6, `upload-artifact` v4 → v7 ;
  - `pyproj` 3.7.2, publié le 14 août 2025.
- **Tests** :
  - `core/tests/test_audit_dependances.py` (5 tests, sans réseau) : fichiers réels lus, workflows fabriqués, action en retard, sortie de `pip-audit` fabriquée qui donne le code 1, `pip-audit` absent, pas de réseau ;
  - `test_recette_pc` : étape `deps`.
