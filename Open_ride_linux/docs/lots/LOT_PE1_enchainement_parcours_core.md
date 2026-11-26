# Lot PE1 : enchaîner plusieurs parcours en session libre, côté core

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Enchaînement de parcours en session libre : qui peut enchaîner, parcours suivant, phases « choix » et « en route », un seul journal et un seul FIT avec un tour par parcours | Python | RT2, AC5 | Moyenne | En cours (module pur et tours FIT codés le 23 novembre ; branchement dans la séance après RT2 et AC5) |

Demande du propriétaire du 22 novembre 2026 : à l'arrivée d'un parcours en ligne en session libre, enchaîner sur un
autre parcours sans s'arrêter ni repasser par l'accueil, avec une courte animation « hyperespace » pendant le
changement de monde (lot PE2, engine) et un seul enregistrement pour toute la séance. Réponses du 22/11 : animation
de 3 s, saut sur la carte Garmin entre deux parcours accepté, et rien ne se décide sans le joueur (pas de fin
automatique : il roule au calme tant qu'il ne choisit pas).

## Règles
- Seulement en session libre (`start.mode` = `ride`), parcours en ligne, hors entraînement en cours (le demi-tour du
  lot N26 reste), hors monde ouvert, Cyber-Rogue, ligue, Course, Grand Prix, Dernier survivant, vélodrome et WTF.
  Réglage « Proposer d'enchaîner à l'arrivée : oui / non ».
- Parcours proposés : prêts, libres (pas réservés à un mode, lot GP13), autres que celui qu'on vient de finir ; ceux
  pas encore roulés dans la séance d'abord.
- La séance reste `RUNNING` du début à la fin : arrivée (fin de séance commune RT2, demi-tour « Roule au calme »),
  choix, hyperespace, nouveau départ à s = 0 avec la distance cumulée gardée. Trainer : SIM, pente du parcours puis
  0 % pendant l'hyperespace, limitation de variation habituelle ; ERG libre : cible gardée.
- Un seul journal, un seul FIT : ligne `{"kind": "chain", "event": "route_start", "route_id", "leg", "distance"}` à
  chaque nouveau parcours, tour du FIT (`fit_export.LAP_LINES`). Parcours d'un instant relu par `chain.legs_of` et
  `chain.route_at` (records de segments et reprise rangés sous le bon parcours).

## Livraison
- 23/11 : `core/src/openride_core/chain.py` (module pur : `refusal`, `candidates`, `ChainSession`, `journal_line`,
  `legs_of`, `route_at`), tour du FIT par parcours enchaîné (`LAP_LINES`), tests `core/tests/test_chain.py` (FIT relu
  par le SDK de Garmin).
- Reste (après la fusion de RT2 et d'AC5) : branchement dans `session.py` (`_set_arrival("route")` de RT2 : le choix
  « Enchaîner » remplace le demi-tour ; `.world` suivant lu dans un fil ; attente du `scene_ready` du nouveau
  parcours), objet `chain` de `state` et commandes `chain_open`, `chain_cancel`, `chain_route` (ajout compatible du
  contrat IPC, révision prise à la fusion), records de segments et reprise (`resume.py`) par parcours, test de
  séance « deux parcours enchaînés, un seul FIT ».
