# EC3 : Cyber-Rogue aligné sur les vraies trames du core

- PR : à venir ; revue de code vague 3, lot E10 (E10-01 à E10-09) ; engine du mode et core (`rogue/`, `session.py`) ; pas de nouvelle révision IPC (aucun champ ni message nouveau)
- CHANGELOG (section « Corrigé ») :
  - Cyber-Rogue : dans les couloirs et pendant la récupération, la scène ne revient plus au début de la salle finie, figée, avec le mur du Firewall posé sur le vélo : le vélo roule sur la bande plate, comme à l'échauffement.
  - Cyber-Rogue : pendant la récupération après une défaite, plus de bords rouges ni de panneau « TE TOUCHE ! · or perdu » : le panneau dit « Firewall arrêté · Récupération · Rien ne se perd », sans alarme.
  - Cyber-Rogue : « N m restants » et l'avertissement « Fin de salle dans … m » s'affichent enfin (longueur prise dans la salle reçue).
  - Cyber-Rogue : le jingle de fin dit la défaite quand la run est perdue (il jouait toujours la victoire).
  - Cyber-Rogue : plus de ronflement du Firewall ni d'alarme de contact pendant l'échauffement, les couloirs, la récupération et le retour au calme.
  - Cyber-Rogue : l'ennemi s'éteint ou s'enfuit à la fin de la salle au lieu de disparaître d'un coup.
  - Cyber-Rogue : Y pendant un couloir cache aussi les cartes et les portes sous le menu de pause.
  - Cyber-Rogue : après un plantage du core en pleine run, la salle en cours, l'offre de cartes ou de relique et les portes reviennent à la reprise.
  - Fin de séance : vies et pièces à jour tout de suite (message `progression` après le bilan) ; une vie consommée en run peut être rachetée sans relancer le jeu.
- SUIVI :
  - [ ] EC3 : Cyber-Rogue sur les vraies trames du core (E10-01 à E10-09), trames `engine/tests/data/rogue_trames_core.json` (`python -m openride_core.tools.rogue_trames`, `--check`), tests `engine/tests/unit/test_rogue_trames_core.gd`, `core/tests/test_rogue_trames.py`, `core/tests/test_revue_code_ec3.py`.
