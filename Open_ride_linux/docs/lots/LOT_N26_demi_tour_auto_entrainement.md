# Lot N26 – Demi-tour automatique au bout du parcours pendant un entraînement

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 1.x série N : demi-tour automatique au bout d'un parcours en ligne pendant un entraînement ERG ou un test de FTP | Python + GDScript | N17 | Petite | En PR (14 novembre) |

## 1. Objectif

Demande du propriétaire du 14 novembre : « en entraînement ERG et FTP il faudrait un demi-tour automatique ». Sur un parcours en ligne (Col du lacet, démos des biomes, traces GPX), l'arrivée terminait la séance et coupait l'entraînement en plein bloc, sans prévenir ; une rampe de FTP pouvait s'arrêter avant la fin.

## 2. Travail fait

- **Core** (`session.py`, `_u_turn_at_end`) : au bout d'un parcours en ligne (arrivée, ou départ à rebours), si un entraînement de la bibliothèque ou un test de FTP est en cours (`ErgController`) et que le demi-tour est permis (règles de N17 : pas en Dernier survivant ni en Grand Prix), demi-tour sans arrêt comme Y maintenu : vitesse gardée, `dir` inversé, événement `u_turn` au journal, passage de segment en cours annulé. Position bornée au bout de la route. Autant de fois qu'il le faut.
- Entraînement fini (retour au SIM, invite `workout_done`), SIM, ERG libre ou cadence verrouillée (O18) : le bout du parcours termine la séance comme avant.
- **Engine** (`hud_view_model.gd`, `main.gd`) : bandeau « Bout du parcours : demi-tour, l'entraînement continue » quand le sens change en roulant à un bout du parcours avec un entraînement en cours.
- **Guide** : paragraphe de Y maintenu.

## 3. Contrat

Aucun changement : champ `dir` (révision 1.9) et événement `u_turn` du journal existants.

## 4. Critères d'acceptation

1. `core/tests/test_u_turn_auto.py` : demi-tour aux deux bouts sans arrêt, distance croissante, arrivée ordinaire après l'entraînement ; rampe de FTP ; SIM et ERG libre terminent toujours à l'arrivée ; `u_turn` au journal.
2. `engine/tests/unit/test_hud_view_model.gd` : bandeau seulement au bout du parcours, en roulant, avec un entraînement.
3. Essai PC sans vélo : `openride --trainer mock --input keyboard --autostart --route demo --workout <entraînement de 30 min>` : demi-tour au sommet, bandeau, l'entraînement continue.

## Livraison

Branche `claude/project-thread-1b3i67` (14 novembre).
