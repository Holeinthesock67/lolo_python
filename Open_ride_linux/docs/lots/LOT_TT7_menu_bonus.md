# Lot TT7 – Menu « Bonus » et guide

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série TT : réglage « Bonus » à trois choix au menu et guide d'utilisation (quand lancer chaque bonus) | GDScript + Markdown | TT1, TT6 | Petite | Prêt (version 4.0) |

Série TT (bonus tactiques, version 4.0). Plan de la série : `docs/4.0/PLAN_SERIE_TT.md`, recommandations retenues par le propriétaire le 29 octobre (« ok pour tout », §6 du plan). Cahier rédigé le 8 novembre 2026 (le plan les annonçait, aucun n'existait).

## 1. Objectif

Rendre le choix `off` / `classiques` / `tactiques` réglable au menu et expliquer les bonus dans le guide.

## 2. À lire

Plan §1 et §3 ; `core/src/openride_core/settings.py` (`powerups.mode`) ; `docs/GUIDE_UTILISATION.md`.

## 3. Travail demandé

- Légende des trois choix (champ `help`) dans Réglages › Séance › Bonus.
- Paragraphe du guide : chaque bonus, son terrain idéal, ses refus.

## 4. Critères d'acceptation

1. `core/tests/test_options_menus.py` vert.
2. Capture du menu validée par le propriétaire.

## 5. Fichiers touchés

`core/src/openride_core/settings.py`, `docs/GUIDE_UTILISATION.md`.
