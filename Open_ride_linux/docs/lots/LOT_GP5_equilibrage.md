# Lot GP5 – Équilibrage au banc simulé

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : simulateur de courses (cycliste virtuel X27 et bots), rapport et valeurs de `grandprix.toml` | Python | GP1, GP3 | Moyenne | Prêt (version 4.0 proposée) |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Régler forces, poids et fréquences pour que le mode soit amusant sans être une loterie.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` §3 et §4.2 ; `core/src/openride_core/sim_rider.py` (X27) ; `core/src/openride_core/sim_scenarios.py`.

## 3. Travail demandé

- Outil `grandprix_sim` : N courses simulées par configuration (adversaires, chaos, niveau du joueur), rapport Markdown.
- Cibles : à niveau égal, le joueur gagne entre 1/(N + 1) et 2/(N + 1) des courses ; à 10 % sous les bots, il en gagne au moins 10 % en chaos normal ; aucun objet ne représente plus de 35 % du temps total gagné ou perdu.
- Valeurs retenues écrites dans les valeurs par défaut de `grandprix.toml`.

## 4. Critères d'acceptation

1. Rapport joint à la PR, avec les trois niveaux de chaos et 2, 4 et 11 bots.
2. Les cibles sont tenues, ou l'écart est expliqué et soumis au propriétaire.
