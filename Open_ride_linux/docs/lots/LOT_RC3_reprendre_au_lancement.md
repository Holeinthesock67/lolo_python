# Lot RC3 – « Reprendre la course » au lancement suivant

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Séance ou course interrompue par un arrêt brutal du jeu reprise depuis l'accueil, moins de 2 h après, en mots (mode, tour, place) ; contrat IPC (révision à la fusion) | Python, GDScript | RC1, O34 | Petite | En PR le 23 novembre 2026 (avec RC1) ; captures à valider |

Suite de RC1 (`LOT_RC1_reprise_course.md`) : RC1 reprend une course quand le core plante et que le lanceur le relance ;
RC3 couvre l'arrêt du jeu entier (PC éteint, coupure de courant, jeu fermé).

## 1. La règle

- **Accueil** : la ligne de la séance interrompue (lot O34) devient « Course interrompue à reprendre » (ou « Séance
  interrompue à reprendre ») quand la reprise est possible, avec en mots le mode, le tour et la place
  (« Course de la ligue · tour 3 sur 6 · tu étais 4e sur 12 » ; Dernier survivant : coureurs encore en course).
- **Écran** : « Reprendre la course » en premier (focus), puis « Enregistrer sans finir » et « Ne pas l'enregistrer »
  (confirmé). Reprise impossible : l'écran d'O34 tel quel.
- **Possible** moins de 2 h après la dernière ligne du journal (`resume.RESUME_WINDOW_S`) et, pour une course, avec un
  instantané de ce format et de cette version du jeu ; jamais pour une course coupée avant son premier instantané.
- **Reprise** : la séance repart en pause, raison `core_restarted`, comme après un plantage du core ; la ligne d'état
  de la pause dit « OpenRide a redémarré : course retrouvée, tout le monde repart arrêté ». La pause est celle d'une
  course (pas de lignes de bots modifiables).
- **Contrat** (révision à la fusion) : `resumable` et `race` des éléments de `hello_ack.config.interrupted`,
  `recover_session` avec `resume`, `resumed` du message `interrupted`.

## 2. Vérification

- `core/tests/test_race_resume.py` : course proposée avec place, tour et ligue, reprise depuis le menu puis menée à
  l'arrivée ; trop ancienne ou d'une autre version : non reprenable, `resume` refusé ; coupée avant le premier
  instantané : non reprenable.
- `engine/tests/unit/test_interrupted_menu.gd` : accueil et écran en mots, commande `recover_session` avec `resume`,
  ligne d'état de la pause, pause d'une course sans lignes de bots, séance trop ancienne.
- Banc des menus, scénario `reprise_course` (en-tête `course_interrompue` : course roulée par le vrai core juste
  avant le lancement, `openride_core.tools.course_interrompue`) : captures `accueil_course_interrompue`,
  `course_interrompue`, `pause_course_reprise`.

## Recette PC
Catégorie : menus
- Cloud : tests du core et de l'engine ; banc des menus `reprise_course` et `seance_interrompue` en low, medium et high.
- PC : banc des menus medium (`reprise_course`, `seance_interrompue`) ; captures low/medium/high à valider.
- Versions : contrat IPC (révision à la fusion), WORLDGEN_VERSION et SCHEMA_VERSION inchangés.

## Livraison

- 23 novembre 2026 : `resume._resume_offer`, `CoreSession._resume_interrupted`, place et tour dans `race_snapshot`,
  `menu_flow.gd` (`interrupted_race_detail`, ligne d'état de la pause), `main.gd`, scénario `reprise_course`,
  outil `tools/course_interrompue.py`.
