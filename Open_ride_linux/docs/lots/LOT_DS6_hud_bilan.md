# Lot DS6 – Engine : HUD de course, bandeaux et bilan

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série DS : engine, HUD de course (arche suivante, rang, écart au dernier, liste des coureurs), bandeaux et bilan | GDScript | DS2, DS4 | Moyenne | **Livré le 3 novembre** (version 2.0), captures à valider |

Série DS (mode « Dernier survivant », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/2.0/PLAN_SERIE_DS.md`.

## 1. Objectif

Afficher `state.survivor`, les messages `elimination` et `summary.survivor` selon les maquettes validées.

## 2. À lire

`docs/2.0/PLAN_SERIE_DS.md` §5 et §6 ; maquettes validées de DS4 ; `engine/scripts/hud_view.gd` ; `engine/scripts/summary_view.gd`.

## 3. Travail demandé

- Modèle sans affichage (formatage, ordre, couleurs) testé à part, vue mince.
- Bloc en haut à droite, liste à gauche (12 lignes au plus), bandeaux de 3 s, écran du joueur éliminé, bilan arche par arche.
- Doublons de `elimination` ignorés.

## 4. Critères d'acceptation

1. Captures en `low`, `medium` et `high` en 1680×1050 et 1024×600 validées par le propriétaire.
2. Tests du modèle : joueur dernier, joueur éliminé, vainqueur, 11 adversaires.

## Livraison

Livré le 3 novembre 2026 (version 2.0, PR unique DS1 à DS7). Modèle sans affichage `engine/scripts/survivor/survivor_hud_model.gd` (bloc, liste de 12 lignes au plus, bandeaux de 3 s et 6 s, doublons de `elimination` ignorés, lignes du bilan) et vue mince `engine/scripts/survivor/survivor_view.gd` (bloc sous le profil d'altitude via `hud_view.free_right_top()`, liste à gauche à la place de l'encart des bots). Bilan : lignes ajoutées par `summary_view_model.gd` ; champ `winner_name` ajouté à `summary.survivor` (contrat 1.5). Tests : `engine/tests/unit/test_survivor_hud.gd` (joueur dernier, joueur éliminé, vainqueur, 11 adversaires). Reste : captures en 1680×1050 et 1024×600, `low`, `medium`, `high`.
