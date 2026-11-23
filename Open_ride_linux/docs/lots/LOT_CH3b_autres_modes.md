# Lot CH3b : les autres modes du calendrier de la ligue d'hiver

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Ligue d'hiver : Dernier survivant, Grand Prix et élimination en manche | Python | CH3a, CH3c | Moyenne | En revue |

Série CH (ligue d'hiver). Fait suite à CH3a (manche 1, Course en tours) et à CH3c (correctifs de la revue F1).
Échéance : avant le dimanche 6 décembre au soir (fin de la semaine 2, Dernier survivant). Sinon la semaine est
neutralisée, et personne n'y marque de points.

## 1. Ce que le lot fait (core seul)

- `league.PLAYABLE_MODES` passe aux quatre modes : `race`, `survivor`, `grandprix` et `track`. Une semaine
  manquée est donc simulée pour les rivaux, comme prévu au plan.
- **Dernier survivant** (semaines 2 et 6) :
  - Il se court sur une boucle, avec une arche par rival (11).
  - L'écart entre arches (1, 2 ou 3 km) est choisi pour une course d'environ 27 min à l'allure du cycliste.
  - Les réglages `survivor.opponents` et `survivor.spread` sont ignorés.
  - Comme partout depuis RT1/RT2, on continue à rouler après l'élimination ou la victoire, et la manche compte au
    bilan (`end_session`). Si le bilan est demandé avant la fin de la course, les rivaux encore en course sont
    rangés par distance parcourue. Il n'y a donc pas d'égalité à la 1re place, qui donnerait 25 points à chacun.
- **Grand Prix** (semaines 3 et 7) :
  - Les objets suivent le réglage du cycliste (chaos, écart des boîtes).
  - Sur une boucle, la manche suit les tours de la ligue. Sur un parcours en ligne, elle suit la distance du
    Grand Prix.
- **Élimination au vélodrome** (semaine 4) :
  - Elle se court sur le vélodrome seulement, sans argument `track`, contre les 11 rivaux.
  - Les autres réglages sont ceux par défaut de l'épreuve.
  - La manche compte au bilan, même demandé après l'élimination du cycliste avant la fin de l'épreuve : les
    rivaux encore en piste sont alors classés devant lui, dans l'ordre de la course.
  - Une manche de route reste permise sur une piste : la boucle d'essai du Grand Prix du banc des menus est une
    copie du vélodrome.
- Le journal `league_start` porte le mode de la manche, quel que soit ce mode.

## 2. Contrat

Le contrat reste en révision 1.30, sans nouveau champ. `start` avec `league` accepte maintenant les quatre
modes. Le message `league` portait déjà `round.mode` et `round.terrain`.

## 3. Reste à faire

- **Engine** (lot suivant, banc de nuit). Aujourd'hui, l'écran de la ligue envoie toujours `mode` = `race`. Il
  doit :
  - envoyer le mode de la manche ;
  - choisir le parcours selon `round.terrain` : le vélodrome pour `piste`, un parcours en ligne pour
    `arrivee_cote`, une boucle sinon ;
  - griser « Démarrer » avec une raison écrite.
- La classique (CH5), ainsi que le podium et le trophée (CH4b).
