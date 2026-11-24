# Lot CH4c – Ligue d'hiver : départ de chaque manche dans son mode

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CH : l'écran de la ligue lance chaque manche dans son mode, sur un parcours qui va à son terrain | GDScript | CH4a (#993), CH3b (core) | Petite | En revue |

Échéance : avant le dimanche 6 décembre au soir, c'est-à-dire la fin de la semaine 2 (Dernier survivant).

## 1. Ce que le lot fait

- « Démarrer » envoie `start` avec `mode` = `round.mode` du message `league` : `race`, `survivor`, `grandprix`
  ou `track`, et toujours `league` = `true`. CH4a envoyait toujours `race`.
- « Courir la manche » choisit le parcours selon `round.terrain` (`LeagueViewModel.pick_route`). Le parcours en
  cours est gardé s'il convient. Sinon, l'écran prend le premier qui convient : les parcours libres, puis ceux du
  Grand Prix, puis les vélodromes.

  | Terrain | Parcours choisi |
  | --- | --- |
  | `boucle` (Course en tours, Dernier survivant, Finale) | une boucle, jamais le vélodrome |
  | `grandprix` | une boucle d'abord (tours de la ligue, environ 27 min), sinon un parcours en ligne |
  | `piste` (élimination) | le vélodrome |
  | `arrivee_cote` | un parcours en ligne |

- Sur un parcours qui ne convient pas, « Démarrer » est grisé, et la raison est écrite :
  - « choisis le vélodrome » ;
  - « choisis un parcours en ligne » ;
  - « choisis une boucle » ;
  - « choisis un parcours sur route ».

- Comment la manche s'enregistre, écrit sur la fiche de la ligue et sur la ligne « Démarrer » : « La manche compte
  au bilan : après l'arrivée, Y puis A maintenu. » Cela suit la fin de séance commune RT2 (#1000) : après
  l'arrivée, on continue à rouler, et la manche ne s'écrit qu'au bilan.

## 2. Recette

- Test unitaire `engine/tests/unit/test_league_menu.gd` (`_test_other_modes`) : quatre manches (survivant, Grand
  Prix, élimination, arrivée en côte), avec le parcours et le `start` attendus pour chacune, plus les refus écrits.
- Menus seuls : banc medium et captures de l'écran Prêt d'une manche au vélodrome, de nuit avant le 28/11 ou après.
- Le core doit avoir CH3b. Sans lui, il refuse ces manches avec un message écrit (« n'est pas encore jouable »).
