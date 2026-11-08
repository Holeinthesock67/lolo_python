# Lot CO5 – Écrans du menu de la séance conseillée

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Séance conseillée : ligne de l'accueil, écran du conseil, détail du calcul, autre besoin, prochaine course | GDScript | CO3, CO4, CO8, CO9 | Moyenne | Prêt (version 5.0) |

Série CO (version 5.0, séance conseillée par OpenRide). Plan de la série : `docs/5.0/PLAN_SERIE_CO.md`.

## 1. Objectif

Afficher le conseil dans le menu selon les maquettes validées (CO4).

## 2. Travail demandé

- `menu_model.gd` : ligne « Séance conseillée » en tête de l'accueil (détail : besoin et séance), envoi de `get_coach` à chaque ouverture.
- `coach_view_model.gd` (nouveau), `menu_flow.gd`, `menu_view.gd` : écran du conseil, « Lancer cette séance » (ERG pour un entraînement, SIM pour un parcours), autre séance du même besoin, autre besoin, objectif, temps disponible, prochaine course, suggestion de la montre (CO8), « Lancer la course » pour une séance de jeu calibrée (CO9), détail du calcul.
- Couleurs par jetons de `ui_theme.gd` seulement (`test_menu_style.gd`).
- `GUIDE_UTILISATION.md` : section du menu ; scénarios `menu_scenarios/` de l'accueil.

## 3. Critères d'acceptation

`run_engine_tests.sh` passe ; captures low, medium et high validées par le propriétaire avant la fusion ; banc des menus (X55) sans régression.
