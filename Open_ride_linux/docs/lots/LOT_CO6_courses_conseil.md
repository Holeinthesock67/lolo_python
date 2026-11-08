# Lot CO6 – Courses et prochaine course dans le conseil

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Séance conseillée : causes de perte des courses disputées (S5) et prochaine course (S6), règles R1, R2 et R7 complètes | Python | CO1, DS2, T4 (livrés sauf CO1) ; CT13 quand il existe | Moyenne | Prêt (version 5.0) |

Série CO (version 5.0, séance conseillée par OpenRide). Plan de la série : `docs/5.0/PLAN_SERIE_CO.md`.

## 1. Objectif

Faire entrer les courses dans le conseil : récupérer après une course, s'affûter avant, et travailler ce qui coûte des places.

## 2. Travail demandé

- Lecture des journaux de course existants (lignes `survivor_summary` du Dernier survivant, segments chronométrés T4, courses avec bots) : cause de perte « montée », « sprint », « fin de course » ou aucune, selon les règles du plan §4 ; rien n'est déduit quand le journal ne permet pas de le dire.
- Le journal des courses de la Course tactique (CT13) est lu dès qu'il existe, par la même fonction.
- Prochaine course (CO3) : R2 deux jours avant, R1 le lendemain.

## 3. Critères d'acceptation

`pytest -q` passe ; un cas synthétique par cause, un journal de course sans cause lisible, et une course annoncée dans 2 jours.
