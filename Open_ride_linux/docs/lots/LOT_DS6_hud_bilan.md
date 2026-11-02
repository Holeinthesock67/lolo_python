# Lot DS6 – Engine : HUD de course, bandeaux et bilan

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série DS : engine, HUD de course (arche suivante, rang, écart au dernier, liste des coureurs), bandeaux et bilan | GDScript | DS2, DS4 | Moyenne | Prêt (version 3.0 proposée) |

Série DS (mode « Dernier survivant », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/3.0/PLAN_SERIE_DS.md`.

## 1. Objectif

Afficher `state.survivor`, les messages `elimination` et `summary.survivor` selon les maquettes validées.

## 2. À lire

`docs/3.0/PLAN_SERIE_DS.md` §5 et §6 ; maquettes validées de DS4 ; `engine/scripts/hud_view.gd` ; `engine/scripts/summary_view.gd`.

## 3. Travail demandé

- Modèle sans affichage (formatage, ordre, couleurs) testé à part, vue mince.
- Bloc en haut à droite, liste à gauche (12 lignes au plus), bandeaux de 3 s, écran du joueur éliminé, bilan arche par arche.
- Doublons de `elimination` ignorés.

## 4. Critères d'acceptation

1. Captures en `low`, `medium` et `high` en 1680×1050 et 1024×600 validées par le propriétaire.
2. Tests du modèle : joueur dernier, joueur éliminé, vainqueur, 11 adversaires.
