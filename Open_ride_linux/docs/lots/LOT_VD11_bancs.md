# Lot VD11 – Bancs GPU

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : bancs GPU `low`, `medium`, `high` du vélodrome et captures | Mesure | VD4, VD5, VD7, VD9 | Petite | Prêt (version 4.0) |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Plan validé par le propriétaire le 6 novembre (lot VD0).

## 1. Objectif

Mesurer le vélodrome sur le PC cible dans les trois préréglages, au pire cas.

## 2. À lire

§7.3 du plan ; `engine/tests/sim_bench.py`, `perf_targets.json`.

## 3. Travail demandé

- Scénario de banc `velodrome` (départ du scratch avec 11 bots, tribunes pleines).
- Mesure `low`, `medium`, `high` sur le PC cible, par la file du PC.
- Endurance de 30 min.

## 4. Critères d'acceptation

1. Sous le budget dans les trois préréglages ; salle couverte sous 70 %.
2. Captures validées par le propriétaire.

## 5. Fichiers touchés

- `engine/tests/sim_bench_scenarios/`, résultats dans le dossier des mesures du projet.

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 6, 12 et 14 ms) et ses captures sont validées par le propriétaire avant la fusion.
