# Lot VD9 – HUD et sons

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : HUD de piste, tableau d'affichage, cloche, pistolet de départ et ambiance du public | GDScript | VD6, VD8 | Moyenne | À valider (version 4.0 proposée) |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Rien ne se code avant la validation du plan par le propriétaire (lot VD0).

## 1. Objectif

Coder ce que les maquettes de VD8 ont validé.

## 2. À lire

Maquettes VD8 ; `engine/scripts/hud_view.gd`, `summary_view.gd`, `sound_player.gd`.

## 3. Travail demandé

- HUD d'épreuve lu dans l'objet `track` de `state`.
- Tableau d'affichage de la salle.
- Sons : cloche du dernier tour, pistolet, public qui monte au sprint (sons libres de droits, provenance notée).

## 4. Critères d'acceptation

1. Captures `low`, `medium`, `high` validées par le propriétaire avant fusion.
2. Lisibilité vérifiée par l'outil de galerie du HUD.

## 5. Fichiers touchés

- `hud_view.gd`, `summary_view.gd`, `sound_player.gd`, sons dans `engine/assets/`.

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 6, 12 et 14 ms) et ses captures sont validées par le propriétaire avant la fusion.
