# Lot DS7 – Menu : entrée « Dernier survivant » et réglages

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série DS : menu, entrée « Dernier survivant » à l'accueil et écran des réglages du mode | GDScript | DS2 | Petite | Prêt (version 3.0 proposée) |

Série DS (mode « Dernier survivant », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/3.0/PLAN_SERIE_DS.md`.

## 1. Objectif

Lancer le mode et régler ses options depuis le menu, sans ligne de commande.

## 2. À lire

`docs/3.0/PLAN_SERIE_DS.md` §4 ; `engine/scripts/menu_flow.gd` (entrée « Mode WTF » du lot WTF3) ; `docs/PRESENTATION_MENUS.md`.

## 3. Travail demandé

- Entrée à l'accueil quand le core annonce le mode ; écran : parcours (longueur de course, mention « trop court »), adversaires, écart entre arches, niveau, écart de niveau, après élimination, « Lancer ».
- Réglages envoyés par `set_setting`, repris à la séance suivante ; `start` avec `mode` = `survivor`.
- Scénario du banc des menus pour le nouvel écran.

## 4. Critères d'acceptation

1. Tests du menu : entrée absente si le core ne l'annonce pas, parcours trop court refusé, réglage modifié puis relu.
2. Captures de l'écran validées par le propriétaire.
