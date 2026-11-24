# Lot CH4 – Ligue d'hiver : écrans

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CH : ligne de l'accueil, écran de la ligue avec le classement, écran Prêt d'une manche, encart du bilan (CH4a) | GDScript | CH3 (contrat 1.30) | Moyenne | En PR le 22 novembre 2026 ; podium, trophée et saison suivante au lot CH4b |

Plan : `docs/6.0/PLAN_SERIE_CH.md` §3.5. Maquettes CH0 validées le 21 novembre 2026 :
`/mnt/project-files/menus/ch0-ligue-hiver/` (01 accueil, 02 écran de la ligue, 03 bilan).

## 1. La règle

- **Accueil** : ligne « Ligue d'hiver » après « Séance conseillée », montrée dès que le core a répondu à
  `league_status` (demandé à chaque liste de l'accueil, au lancement et après une séance). Détail : `home_line` du
  core (« 9e · manche 1/8 : Course en tours, à courir cette semaine ») ; sans saison : « 8 semaines contre 11 rivaux ».
- **Écran de la ligue** (`league_view_model.gd`) : titre « Ligue d'hiver · saison N · semaine S sur 8 » ; à gauche
  « Courir la manche N : … » (grisée avec la raison écrite : faite, pas encore jouable, saison en pause) ou
  « Commencer la saison N » (`league_new`) ; à droite la fiche du classement général : tableau des 12 (place,
  pastille du maillot, nom, caractère et équipe écrits, points, manches courues), ligne du cycliste écrite « Toi »
  avec sa FTP et encadrée. Mots écrits avant la couleur.
- **Écran Prêt d'une manche** (`mode` « league » de `menu_model.gd`) : « Démarrer » avec le rappel de la manche,
  « Changer de parcours ». La manche prend une boucle : la dernière choisie si c'en est une, sinon la première boucle
  libre, sinon le premier circuit du Grand Prix (les parcours libres de départ sont en ligne) ; sur un parcours en
  ligne, « Démarrer » est grisé et dit de choisir une boucle. `start` : `{"mode": "race", "league": true}`, sans
  bots ni ERG (le core compose le plateau).
- **Bilan** : lignes « Ligue d'hiver », « Manche » (place et points), « Général » (place et mouvement écrit),
  « Intensité » (facile), puis cinq lignes du classement autour du cycliste (`summary.league`).
- `detail_card.gd` gagne la clé `table` (lignes du classement) pour toute fiche.

## 2. Vérification

- `engine/tests/unit/test_league_menu.gd` : modèle (sans saison, manche à courir, faite, pas jouable, saison finie),
  accueil, écran de la ligue et sa fiche, écran Prêt sur une boucle libre puis sur un circuit du Grand Prix, refus
  d'un parcours en ligne, `start`, `league_new` et refus du core, carte du tableau, lignes du bilan.
- Banc des menus : `engine/tests/menu_scenarios/ligue_hiver.json` (vrai core, profil neuf, FTP fictive 250 W) :
  accueil, saison commencée, classement, écran Prêt, course jusqu'à l'arrivée, bilan, manche faite. Captures
  `ch4_*` en low, medium et high pour la validation du propriétaire.

## 3. Limites connues (lots suivants)

- Podium, trophée et « Commencer la saison suivante » à la fin d'une saison : CH4b. Classique : CH5.
- Manches des autres modes (Dernier survivant, Grand Prix, élimination) : CH3b, avant leur semaine.
