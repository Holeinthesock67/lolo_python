# Lot TT8 – Équilibrage et recette des bonus tactiques

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série TT : équilibrage au banc simulé (cycliste virtuel X27), puis recette sur le vélo en étapes de 10 min | Python + recette | TT2 à TT7 | Petite | En revue (banc fait le 8 novembre ; recette du propriétaire à faire) |

Série TT (bonus tactiques, version 4.0). Plan de la série : `docs/4.0/PLAN_SERIE_TT.md`, recommandations retenues par le propriétaire le 29 octobre (« ok pour tout », §6 du plan). Cahier rédigé le 8 novembre 2026 (le plan les annonçait, aucun n'existait).

## 1. Objectif

Vérifier que chaque bonus vaut 1,5 à 2,5 s dans son terrain idéal, puis le ressentir sur le vélo.

## 2. À lire

Plan §2 ; outil du cycliste virtuel (lot X27) ; `recettes-physiques/PLAN_SESSIONS_10MIN.md` (forme des sessions, hors dépôt).

## 3. Travail demandé

- Banc simulé : chaque bonus dans son terrain idéal, 50 passages, rapport des gains et des refus.
- Valeurs ajustées dans le fichier des valeurs par défaut si un bonus sort de la fourchette.
- Recette : deux sessions de 10 min au plus (jeu `tactiques` avec 4 bots ; gravel avec le Rouleau), compte-rendu `OK|KO note/5`.

## 4. Critères d'acceptation

1. Rapport du banc dans `docs/4.0/`.
2. Recette notée par le propriétaire.

## 5. Fichiers touchés

`core/src/openride_core/tools/` (banc), `docs/4.0/RAPPORT_EQUILIBRAGE_TT8.md`.
