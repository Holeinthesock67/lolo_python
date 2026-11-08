# Lot TT6 – Affichage des bonus tactiques

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série TT : engine, icônes des sept bonus, état refusé, compte à rebours, jauge d'abri en couleur, avatar semi-transparent de l'Échappée | GDScript | TT1 ; TT3 à TT5 pour les effets | Moyenne | Prêt (version 4.0) ; maquettes validées avant le code |

Série TT (bonus tactiques, version 4.0). Plan de la série : `docs/4.0/PLAN_SERIE_TT.md`, recommandations retenues par le propriétaire le 29 octobre (« ok pour tout », §6 du plan). Cahier rédigé le 8 novembre 2026 (le plan les annonçait, aucun n'existait).

## 1. Objectif

Montrer les bonus tactiques au HUD (coin supérieur droit, T9) et à l'avatar.

## 2. À lire

Plan §2 et §4 ; `docs/lots/LOT_T9_hud_segment_bonus.md`, `engine/scripts/hud_view.gd`, `engine/scripts/ui_icons.gd`, `docs/PRESENTATION_MENUS.md`.

## 3. Travail demandé

- **Maquettes d'abord**, validées par le propriétaire avant tout code.
- Icônes tracées par le code pour les sept bonus ; état refusé avec la raison 2 s ; compte à rebours (T9).
- Jauge d'abri en couleur pendant Aspiration + ; avatar semi-transparent pendant l'Échappée.

## 4. Critères d'acceptation

1. Captures validées par le propriétaire.
2. Banc `low`, `medium`, `high` sur la GTX 1060 : l'avatar semi-transparent ne dépasse pas le budget.

## 5. Fichiers touchés

`engine/scripts/hud_view.gd`, `engine/scripts/ui_icons.gd`, rendu de l'avatar, tests de rendu.

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 8, 13 et 16 ms depuis le 8 novembre) et ses captures sont validées par le propriétaire avant la fusion.
