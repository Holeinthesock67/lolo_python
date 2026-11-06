# Lot VD0 – Décisions du propriétaire

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : décisions du propriétaire (pistes, relèvement, surfaces, épreuves, version) | Décision | — | Petite | À valider (version 4.0 proposée) |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Rien ne se code avant la validation du plan par le propriétaire (lot VD0).

## 1. Objectif

Consigner les réponses du propriétaire aux questions du §10 du plan avant tout code.

## 2. À lire

§1, §3 et §10 du plan.

## 3. Travail demandé

- Recueillir les réponses aux six questions du §10 (taille des pistes, relèvement, surface, épreuves de la première livraison, braquet fixe, version).
- Reporter les décisions au §10 du plan (date et réponse), corriger les tableaux des §3.3 et §5 en conséquence.
- Mettre à jour la ligne de la 4.0 dans le plan des versions.

## 4. Critères d'acceptation

1. Chaque question du §10 a une réponse datée.
2. Aucun lot VD1 à VD12 ne démarre avant cette mise à jour.

## 5. Fichiers touchés

- `docs/4.0/PLAN_SERIE_VD.md` seulement.

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 6, 12 et 14 ms) et ses captures sont validées par le propriétaire avant la fusion.
