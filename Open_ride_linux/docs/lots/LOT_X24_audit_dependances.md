# Lot X24 – Audit des dépendances

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
