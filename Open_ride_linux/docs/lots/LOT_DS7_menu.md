# Lot DS7 – Menu : entrée « Dernier survivant » et réglages

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série DS : menu, entrée « Dernier survivant » à l'accueil et écran des réglages du mode | GDScript | DS2 | Petite | **Livré le 3 novembre** (version 2.0), captures à valider |

Série DS (mode « Dernier survivant », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/2.0/PLAN_SERIE_DS.md`.

## 1. Objectif

Lancer le mode et régler ses options depuis le menu, sans ligne de commande.

## 2. À lire

`docs/2.0/PLAN_SERIE_DS.md` §4 ; `engine/scripts/menu_flow.gd` (entrée « Mode WTF » du lot WTF3) ; `docs/PRESENTATION_MENUS.md`.

## 3. Travail demandé

- Entrée à l'accueil quand le core annonce le mode ; écran : parcours (longueur de course, mention « trop court »), adversaires, écart entre arches, niveau, écart de niveau, après élimination, « Lancer ».
- Réglages envoyés par `set_setting`, repris à la séance suivante ; `start` avec `mode` = `survivor`.
- Scénario du banc des menus pour le nouvel écran.

## 4. Critères d'acceptation

1. Tests du menu : entrée absente si le core ne l'annonce pas, parcours trop court refusé, réglage modifié puis relu.
2. Captures de l'écran validées par le propriétaire.

## Livraison

Livré le 3 novembre 2026 (version 2.0, PR unique DS1 à DS7). « Dernier survivant » à l'accueil quand le core l'annonce (`menu_model.gd`), écran Prêt du mode (`menu_flow.gd` : « Lancer » avec « 4 arches, 8 km » ou « parcours trop court », « Changer de parcours », puis adversaires, écart des arches, niveau des bots, écart de niveau et suite après élimination modifiés en place par `set_setting`) ; `select_workout` nul à l'entrée (SIM seulement), `start` avec `mode` « survivor » sans `bots`, refus du core sur la ligne d'état. Tests : `engine/tests/unit/test_survivor_menu.gd` et scénario `engine/tests/menu_scenarios/dernier_survivant.json`.
