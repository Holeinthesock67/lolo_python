# Lot DS9 – Recette du mode sur le vélo

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série DS : recette du mode sur le vélo (étapes de 10 min) et banc `low`, `medium`, `high` | Essai sur le vélo | DS3, DS5, DS6, DS7 | Petite | Interne (propriétaire, version 3.0 proposée) |

Série DS (mode « Dernier survivant », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/3.0/PLAN_SERIE_DS.md`.

## 1. Objectif

Vérifier sur le PC cible et le home trainer que la course est jouable, juste et lisible.

## 2. À lire

`docs/3.0/PLAN_SERIE_DS.md` ; `docs/PLAN_DE_TESTS.md`.

## 3. Travail demandé

- Étapes de 10 min au plus : course de 2 bots à 1 km d'écart ; course de 4 bots à 2 km ; élimination volontaire du joueur (continuer, puis terminer) ; victoire.
- Banc sans vélo, séquencé par le fil de fusion : départ du mode en `low`, `medium` et `high`.

## 4. Critères d'acceptation

1. Une élimination par arche, sans erreur au journal du core ; place du bilan juste.
2. Budgets GPU tenus dans les trois préréglages ; captures validées par le propriétaire.
