# Lot DS4 – Maquettes de l'arche, du HUD et du bilan

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série DS : maquettes de l'arche d'élimination, du HUD de course, des bandeaux et du bilan, validées par le propriétaire | Maquettes | DS1 | Petite | Prêt (version 3.0 proposée) |

Série DS (mode « Dernier survivant », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/3.0/PLAN_SERIE_DS.md`.

## 1. Objectif

Montrer au propriétaire, avant tout code d'affichage, l'arche d'élimination, le bloc de course, la liste des coureurs, les bandeaux (élimination d'un bot, joueur dernier, joueur éliminé, vainqueur) et le bilan.

## 2. À lire

`docs/3.0/PLAN_SERIE_DS.md` §5 ; `engine/scripts/segment_markers.gd` (styles d'arche) ; `engine/scripts/hud_view.gd` ; `engine/scripts/summary_view.gd`.

## 3. Travail demandé

- Planches en 1680×1050 et 1024×600, en `low`, `medium` et `high`.
- Arche gonflable de la famille des portiques, style propre (bandes rouges et noires, bandeau « ÉLIMINATION »).
- Pas de flash plein écran ; le rouge « DERNIER ! » reste lisible sans clignoter vite.

## 4. Critères d'acceptation

1. Le propriétaire valide les planches ; la date de validation est notée dans ce cahier avant le début de DS5 et DS6.
