# Lot VD7 – Bots en piste

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : bots du peloton PL1 sur la piste (hauteur, relais, attaques, stratégies d'épreuve) | Python | VD3, VD6, PL1 | Moyenne | À valider (version 4.0 proposée) |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Rien ne se code avant la validation du plan par le propriétaire (lot VD0).

## 1. Objectif

Faire courir le peloton d'environ 12 bots sur la piste, avec des stratégies propres à chaque épreuve et la physique commune.

## 2. À lire

§6 du plan ; `core/src/openride_core/bots.py`, `draft.py` ; cahier PL1.

## 3. Travail demandé

- Hauteur sur la piste par bot (corde, ligne des stayers, attaque par le haut).
- Stratégies : élimination (DS), points (sprints), scratch, poursuite à allure constante.
- Aucune règle physique propre aux bots.

## 4. Critères d'acceptation

1. Courses simulées de 4 et 11 bots, reproductibles.
2. Pas de bots superposés à la même place (écart minimum testé).

## 5. Fichiers touchés

- `bots.py` (après PL1), `track/`, leurs tests.

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 6, 12 et 14 ms) et ses captures sont validées par le propriétaire avant la fusion.
