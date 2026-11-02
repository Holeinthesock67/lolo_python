# Lot DS8 – Jusqu'à 11 adversaires

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série DS : jusqu'à 11 adversaires dans le mode, après le peloton d'environ 12 bots prévu après Y18 | Python, GDScript | DS2, Y18 | Moyenne | En attente du peloton (après Y18) |

Série DS (mode « Dernier survivant », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/3.0/PLAN_SERIE_DS.md`.

## 1. Objectif

Porter le plateau du mode de 4 à 11 bots une fois le peloton d'environ 12 bots livré, et mesurer le coût.

## 2. À lire

`docs/3.0/PLAN_SERIE_DS.md` §2.1 et §7 ; cahier du lot Y18 ; `core/src/openride_core/ipc_budget.py`.

## 3. Travail demandé

- Réglage `survivor.opponents` étendu à 11 ; liste `bots` de la trame étendue par le contrat du peloton.
- Mesure au départ (pire cas) en `low`, `medium` et `high` ; repli : distances de LOD réduites.

## 4. Critères d'acceptation

1. Budgets GPU tenus au départ avec 11 bots : low 6 ms, medium 12 ms, high 14 ms.
2. Pire trame `state` sous 4 096 octets ; captures validées par le propriétaire.
