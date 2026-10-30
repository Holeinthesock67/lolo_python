# Lot MJ9 – Outils et documentation des profils

Série MJ, plan `docs/2.0/PLAN_SERIE_MJ.md` §4.2.

## 1. Objectif

Les outils de recette roulent sur le profil d'essai au lieu de sauvegarder et restaurer le vrai profil ; la documentation décrit les profils.

## 2. À lire

Plan §4.2 ; `tools/recette_v10.py`, `docs/GUIDE_UTILISATION.md`, `docs/OUTILS_DE_TEST.md`.

## 3. Prérequis

MJ7, MJ8. (La « Session simulée » sur `_essai`, prévue ici par l'étude, est faite dès MJ2.)

## 4. Travail demandé

- Recette V10 et suivantes sur `_essai` (plus de sauvegarde ni de restauration du vrai profil).
- Guide d'utilisation : profils, profil d'essai, raccourci `openride --profil` (vérifié par `test_docs_coherence`).
- `OUTILS_DE_TEST.md`, suivi, index.

## 5. Fichiers concernés

`tools/recette_v10.py`, documentation, tests.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

`(cd core && pytest -q)` passe ; recette V10 n'écrit rien hors de `Profils/_essai/`.

## 8. Hors périmètre

Recette PC (MJ10).
