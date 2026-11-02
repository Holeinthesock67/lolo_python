# Lot GP11 – Recette sur le vélo et banc

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : recette sur le vélo en étapes de 10 min et banc `low`, `medium`, `high` | Recette | GP3, GP5, GP7, GP8, GP9 | Petite | Prêt (version 4.0 proposée) |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Vérifier sur le PC cible et le home trainer que le mode est jouable, lisible et sans à-coup sous les pieds.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` ; `docs/PLAN_DE_TESTS.md`.

## 3. Travail demandé

- Étapes de 10 min au plus : course de 2 bots sur circuit ; course de 4 bots en ligne ; chaque objet lancé et reçu au moins une fois ; esquive au Click et au clavier.
- Banc sans vélo, séquencé par le fil de fusion : départ du mode en `low`, `medium` et `high`.

## 4. Critères d'acceptation

1. Aucun à-coup de résistance ressenti à la réception d'un objet ; pente envoyée du journal lisse.
2. Budgets GPU tenus dans les trois préréglages ; captures validées par le propriétaire.
