# Lot GP10 – Jusqu'à 11 adversaires

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : jusqu'à 11 bots avec objets, après le peloton d'environ 12 bots du lot Y18 | Python + GDScript | GP2, GP3, Y18 | Moyenne | Prêt (version 4.0 proposée) |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Porter le mode à 11 adversaires quand le core et l'engine savent afficher un peloton.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` §8 ; plan du peloton après Y18.

## 3. Travail demandé

- Réglage « Adversaires » de 2 à 11 ; tirage et usage inchangés.
- Trame `gp` et `bots` sous la limite de 4 096 octets.

## 4. Critères d'acceptation

1. `ipc_budget` vert avec 11 bots et 12 objets.
2. Banc en `low`, `medium` et `high` au départ (pire cas), captures validées.
