# Lot N26 – Demi-tour automatique au bout du parcours pendant un entraînement

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 1.x série N : demi-tour automatique au bout d'un parcours en ligne pendant un entraînement ERG ou un test de FTP ; boucle de retournement au bout des impasses du monde ouvert | Python + GDScript | N17, W8 | Petite | En PR (14 novembre) |

## 1. Objectif

Demande du propriétaire du 14 novembre : « en entraînement ERG et FTP il faudrait un demi-tour automatique ». Sur un parcours en ligne (Col du lacet, démos des biomes, traces GPX), l'arrivée terminait la séance et coupait l'entraînement en plein bloc, sans prévenir ; une rampe de FTP pouvait s'arrêter avant la fin.

## 2. Travail fait

- **Core** (`session.py`, `_u_turn_at_end`) : au bout d'un parcours en ligne (arrivée, ou départ à rebours), si un entraînement de la bibliothèque ou un test de FTP est en cours (`ErgController`) et que le demi-tour est permis (règles de N17 : pas en Dernier survivant ni en Grand Prix), demi-tour sans arrêt comme Y maintenu : vitesse gardée, `dir` inversé, événement `u_turn` au journal, passage de segment en cours annulé. Position bornée au bout de la route. Autant de fois qu'il le faut.
- Entraînement fini (retour au SIM, invite `workout_done`), SIM, ERG libre ou cadence verrouillée (O18) : le bout du parcours termine la séance comme avant.
- **Engine** (`hud_view_model.gd`, `main.gd`) : bandeau « Bout du parcours : demi-tour, l'entraînement continue » quand le sens change en roulant à un bout du parcours avec un entraînement en cours.
- **Guide** : paragraphe de Y maintenu.

### Impasse du monde ouvert

Demande du propriétaire du 14 novembre : « il faudra tester impasse en monde ouvert ». Essai fait (test du générateur et captures du banc, `engine/tests/make_impasse_world.py`) : au bout d'une impasse, la route engagée revenait sur elle-même sur place (cap de 89° à 269° en 10 m), la route s'arrêtait net à l'écran et la caméra pivotait d'un coup. Choix du propriétaire (carte du 14 novembre) : **boucle de retournement**.

- **Générateur** (`worldgen/edge_profile.py`, `turnaround_points`, `with_turnaround` ; `process.py`, `_append_leg`) : quand le navigateur fait demi-tour au bout d'une impasse, l'arête reprise en sens inverse est précédée d'une boucle : arc d'entrée à droite de 15 m de rayon, boucle à gauche de 18 m de rayon centrée sur l'axe de la route, arc de sortie à droite (cos α = r / (r + R) ferme la boucle sur l'axe), environ 130 m, au plus 47 m au-delà du bout de l'impasse. Le cap reste continu. L'altitude suit le relief, lissée et raccordée à celle du bout de l'impasse.
- Hors ligne, au bord du relief présent sur le PC (point le plus éloigné de la boucle sans relief), le demi-tour reste sur place comme avant.
- Aucun changement de contrat (`worldgen_v1.md`, format `.world`) : la boucle fait partie du profil de l'étape.

## 3. Contrat

Aucun changement : champ `dir` (révision 1.9) et événement `u_turn` du journal existants.

## 4. Critères d'acceptation

1. `core/tests/test_u_turn_auto.py` : demi-tour aux deux bouts sans arrêt, distance croissante, arrivée ordinaire après l'entraînement ; rampe de FTP ; SIM et ERG libre terminent toujours à l'arrivée ; `u_turn` au journal.
2. `engine/tests/unit/test_hud_view_model.gd` : bandeau seulement au bout du parcours, en roulant, avec un entraînement.
3. Essai PC sans vélo : `openride --trainer mock --input keyboard --autostart --route demo --workout <entraînement de 30 min>` : demi-tour au sommet, bandeau, l'entraînement continue.

5. `compiler/tests/test_worldgen_process.py` : impasse en balade, boucle au bout (au plus 50 m au-delà, 15 à 22 m de part et d'autre), cap sans saut de plus de 45° entre deux points, retour sur la même voie, sans trou ni pause ; tracé de la boucle fermé à moins d'un millimètre.
6. Captures low, medium et high de la boucle (`sim_bench.py --world` sur `make_impasse_world.py`) validées par le propriétaire.

## Livraison

Branche `claude/project-thread-1b3i67` (14 novembre).
