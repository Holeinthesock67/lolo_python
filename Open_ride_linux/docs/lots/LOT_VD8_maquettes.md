# Lot VD8 – Maquettes

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : maquettes du HUD de piste, du tableau d'affichage et du bilan, validées par le propriétaire | Maquettes | VD6 | Petite | Livré (version 4.0) |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Plan validé par le propriétaire le 6 novembre (lot VD0).

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

## 6. Livraison (7 novembre)

Douze maquettes dessinées sur les captures validées de la salle (lot VD5), en `low`, `medium` et `high`, en 1280 × 720 et 1024 × 600 : course aux points, cloche du dernier tour (scratch), élimination (dernier en course), poursuite (anneau et écart), keirin (derny), kilomètre (chrono et record), record de l'heure, américaine (relais), tableau d'affichage de la salle, bilan d'un chrono (tours, meilleur tour, records), bilan d'une course (points et tours pris), écran Prêt (épreuve, options, tactique des bots). Validées par le propriétaire le 7 novembre à 22 h 06 (« Ok »). Dossier du projet : `velodrome/vd8/` (script `maquettes_vd8.py`).
