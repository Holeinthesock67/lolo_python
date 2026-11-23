# Lot RC1 – Reprendre une course après un plantage du core

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Reprise d'une course après un plantage du core : instantané `race_snapshot` au journal, Course, Grand Prix et Dernier survivant repris, ligue comptée à l'arrivée | Python | N8, CR1 (#939), CH3 (#989) | Moyenne | En PR le 23 novembre 2026 ; core seul, bouton au lancement suivant au lot RC3 |

Audit du 22 novembre 2026, constats L10 et M2. Cadrage validé le 22 novembre (`plans/CADRAGE_REPRISE_COURSE_2026-11-22.md`
du dossier du projet) : RC1 (Course et Dernier survivant), RC2 (Grand Prix), RC3 (lancement suivant). RC2 tient dans
ce lot : le Grand Prix et la Course sont la même course (`GrandPrixMode`).

## 1. La règle

- **Instantané** : pendant une Course, un Grand Prix ou un Dernier survivant, la séance écrit au journal une ligne
  `race_snapshot` toutes les 5 s (au même instant qu'un relevé) et à chaque pause. Pas de `pickle` : du JSON
  (`race_resume.py`), un numéro de format (`FORMAT`) et la version du jeu. Quelques Ko par ligne.
- **Contenu** : mode, graine de la séance, départ de la course, objectif des bots, manche de la ligue ; pour chaque
  bot sa position, sa distance, sa vitesse, son temps, sa réserve W'bal, son échelle de calibrage, ses attaques déjà
  faites, sa place sur la chaussée ; la course (longueur, tours, arrivées, objets en main, tirage en cours, compteurs
  du bilan, boîtes prises et rangées) ; les arches, passages et éliminations du Dernier survivant ; les points des
  maillots de la Course.
- **Reprise** (plantage du core, relance par le lanceur, lot N8) : le core recompose le même plateau avec les mêmes
  réglages (rivaux, cote Elo, manche de la ligue), à la place du départ, puis pose l'instantané dessus. Le cycliste
  repart de sa dernière ligne du journal, comme avant ; les bots avancent à leur vitesse pendant l'écart (5 s au
  plus) ; tout le monde repart arrêté, en pause `core_restarted`, avec les 3 s de grâce du Grand Prix.
- **Ne reviennent pas**, pour tout le monde : les attaques et relais en cours des bots, les projectiles en vol, les
  effets en cours et les coups en attente du Grand Prix, les passages de segments en cours de la Course.
- **Refus** (format ou version du jeu différents, plateau qui ne colle plus, manche de la ligue qui n'est plus celle
  de la semaine, course coupée avant le premier instantané) : la séance reprend sans la course, avec une ligne
  `WARNING` « Course non reprise » au journal du lanceur.
- **Ligue** : une manche reprise et menée à l'arrivée compte normalement (même course, même plateau). Une manche non
  reprise ne compte pas et se recourt dans la semaine (règle de CH3 gardée).

## 2. Vérification

- `core/tests/test_race_resume.py` : instantanés à 5 s et à la pause, taille ; Course reprise (positions, réserves,
  forme du jour, longueur, place) puis menée à l'arrivée ; Grand Prix (objets en main, boîtes prises, compteurs,
  arrivées, rien en vol) ; Dernier survivant (arches, éliminés, bots retirés) ; autre version refusée ; course coupée
  avant le premier instantané ; manche de la ligue reprise et comptée une fois ; manche non reprise non comptée.

## 3. Limites connues (lots suivants)

- RC3 : jeu entier arrêté (PC, coupure de courant) : au lancement suivant, bouton « Reprendre la course » dans la
  fenêtre de la séance interrompue (lot O34), moins de 2 h après l'arrêt ; ajout à l'IPC et captures.
- Hors lot : épreuves de piste, mode WTF, monde ouvert, Cyber-Rogue (toujours par `pickle`, constat R5).
- L'écran de pause ne dit pas encore en mots que la course a été reprise (RC3).

## Recette PC
Catégorie : logique
- Cloud : tests du core (`test_race_resume.py`, `test_league_session.py`, `test_grandprix_session.py`).
- PC : fumée + medium (une Course simulée, core tué puis relancé par le lanceur) ; pas de capture (aucun écran ajouté).
- Versions : contrat IPC inchangé (ligne de journal seulement), WORLDGEN_VERSION et SCHEMA_VERSION inchangés.

## Livraison

- 23 novembre 2026 : `race_resume.py`, branchements dans `session.py` (`_journal_race_snapshot`, `_resume_race`,
  `_start_grandprix` et `_start_survivor` avec `restore`), ligne `race_snapshot` dans `journal.GAME_KINDS`,
  `ResumeState.race`.
