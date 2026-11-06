# Lot VD8 – Maquettes

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : maquettes du HUD de piste, du tableau d'affichage et du bilan, validées par le propriétaire | Maquettes | VD6 | Petite | À valider (version 4.0 proposée) |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Rien ne se code avant la validation du plan par le propriétaire (lot VD0).

## 1. Objectif

Montrer au propriétaire, avant le code d'affichage, ce que le HUD et le bilan du vélodrome affichent.

## 2. À lire

§5 et §8 du plan ; `docs/PRESENTATION_MENUS.md`.

## 3. Travail demandé

- Maquettes : HUD de chaque épreuve (tours restants, cloche, écart en poursuite, points, éliminé), tableau d'affichage de la salle, bilan (temps au tour, meilleur tour, classement), écran Prêt du vélodrome.

## 4. Critères d'acceptation

1. Maquettes validées par le propriétaire, captures déposées dans le dossier du projet.

## 5. Fichiers touchés

- Images seulement, aucun code.

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 6, 12 et 14 ms) et ses captures sont validées par le propriétaire avant la fusion.
