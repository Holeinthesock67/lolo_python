# Lot TT5 – Rouleau compresseur

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série TT : bonus Rouleau compresseur (Crr du bitume sur une surface non revêtue pendant 25 s) | Python | TT2, U20, U21 | Petite | En revue (version 4.0) |

Série TT (bonus tactiques, version 4.0). Plan de la série : `docs/4.0/PLAN_SERIE_TT.md`, recommandations retenues par le propriétaire le 29 octobre (« ok pour tout », §6 du plan). Cahier rédigé le 8 novembre 2026 (le plan les annonçait, aucun n'existait).

## 1. Objectif

Faire rouler le cycliste comme sur le bitume pendant 30 s sur un chemin non revêtu.

## 2. À lire

Plan §2 ; `core/src/openride_core/surface_physics.py` (U21) ; colonne `surface` de la route (U1, U20).

## 3. Travail demandé

- Effet `crr` : facteur de roulement du bitume, transitions de 20 m comme le fondu de U21.
- Condition : gravel actif et au moins 1 km non revêtu dans les 5 km devant, sinon refus `no_gravel` ; tiré seulement dans ce cas.
- En SIM, le supplément du gravel disparaît pendant l'effet (−0,6 point environ).

## 4. Critères d'acceptation

1. Gain d'environ 2,5 s dans le terrain idéal (test).
2. Sans gravel, jamais tiré.

## 5. Fichiers touchés

`core/src/openride_core/surface_physics.py`, `core/src/openride_core/powerups.py`, tests.
