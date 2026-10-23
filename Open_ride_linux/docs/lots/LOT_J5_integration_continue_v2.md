# Lot J5 – Intégration continue : vérifier `main` après chaque fusion

## 1. Objectif

Le 23 octobre au soir, les fusions des PR #20 à #25 se sont suivies en quelques minutes. Le groupe de concurrence de `.github/workflows/openride.yml` (`cancel-in-progress: true`, une file par branche) a **annulé** les exécutions sur `main` des fusions de I2, I3/I4, I5 et I6 (runs 39, 42, 45 et 48). La première exécution complète sur `main` (run 49) a révélé une régression d'intégration : I2 (`build-all`) et I3 (couches OSM) passaient chacun seuls, mais ensemble `build-all` interrogeait Overpass (audit J, constat J-E1, corrigé dans la PR de l'audit). Ce lot fait en sorte que chaque état de `main` soit testé.

## 2. À lire

1. `docs/lots/00_INDEX.md` et `docs/lots/LOT_H1_integration_continue.md` (livraison).
2. `.github/workflows/openride.yml` (exception approuvée : seul fichier hors de `Open_ride_linux/` modifiable).

## 3. Prérequis

Aucun. Partir de `main` à jour.

## 4. Travail demandé

- **Concurrence :** annuler une exécution en cours seulement pour les demandes de fusion (`pull_request`) ; sur `main`, chaque envoi est testé jusqu'au bout (par exemple `cancel-in-progress: ${{ github.event_name == 'pull_request' }}` ou groupe propre à `github.sha` sur `main`).
- **Exécution hebdomadaire** (`schedule`, une fois par semaine) : détecte une dérive des dépendances non bornées de la colonne Python 3.11 (installée sans `constraints.txt`).
- **Actions à jour :** les journaux du run 49 signalent la fin de Node.js 20 pour `actions/checkout@v4` et `actions/setup-python@v5`. Passer aux versions majeures suivantes publiées (vérifier sur GitHub la dernière version stable de chaque action, et l'écrire dans le rapport).
- **Contrôle de cohérence des paquets :** étape `pip check` après l'installation.
- **Rapport lisible :** résultats `pytest` au format JUnit (`--junitxml`) publiés en artefact de l'exécution, pour les deux suites et les deux versions de Python.
- **Durée :** la suite complète reste sous 10 minutes par tâche.

## 5. Fichiers concernés

- **Modifiés :** `.github/workflows/openride.yml`, `docs/SUIVI_AVANCEMENT.md` (une ligne), `docs/lots/LOT_H1_integration_continue.md` (note de renvoi vers J5).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. La PR du lot exécute les trois tâches au vert.
2. Le rapport montre, sur un dépôt de test ou par lecture commentée du YAML, que deux envois rapides sur `main` donnent deux exécutions complètes (aucune `cancelled`), et que deux envois rapides sur une PR annulent la première.
3. `on.schedule` présent, avec un commentaire qui explique pourquoi.
4. Artefacts JUnit visibles sur l'exécution de la PR.
5. Plus aucun avertissement « Node.js 20 is deprecated » dans les journaux.

## 8. Hors périmètre

- Test de bout en bout core + Godot (lot J8, qui ajoutera une étape à ce fichier après J5).
- Publication de paquets ou de versions.
