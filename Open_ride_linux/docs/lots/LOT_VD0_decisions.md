# Lot VD0 – Décisions du propriétaire

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : décisions du propriétaire (pistes, relèvement, surfaces, épreuves, version) | Décision | — | Petite | Livré le 6 novembre (décisions au §10 du plan) |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Plan validé par le propriétaire le 6 novembre.

## 1. Objectif

Consigner les réponses du propriétaire aux questions du §10 du plan avant tout code. Le 6 novembre, le propriétaire a tranché la taille, les virages et la surface : une piste de 250 m en bois à virages relevés.

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

## 6. Livraison (6 novembre 2026)

Toutes les questions du §10 du plan sont tranchées par le propriétaire le 6 novembre : une seule piste de 250 m en bois à virages relevés, décor unique intérieur, toutes les épreuves dès la première livraison (dont tempo, keirin, omnium, vitesse et poursuite par équipes, américaine), aucune épreuve à surplace, option « Braquet fixe » coupée par défaut, version 4.0.
