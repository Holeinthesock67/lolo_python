# Lot RT2 – Fin de séance commune à tous les modes

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Même fin dans tous les modes : l'arrivée ne coupe plus la séance, même résultat écrit en séance et en tête du bilan, objectif sur l'écran de départ | Python, GDScript | RT1, EL1, CR1 | Moyenne | En revue (captures à valider) |

## 1. Objectif

Audit des retours du 21 novembre (dossier du projet `plans/AUDIT_RETOURS_JEU_2026-11-21.md`, §3 point 3 et §5) et
choix du propriétaire du 21 novembre à 10 h 37 : « après la fin, on continue à rouler, A maintenu = bilan », dans
**tous** les modes. RT1 l'a fait pour les épreuves de piste, le Dernier survivant et l'entraînement ERG. Restaient le
Grand Prix, la Course et l'arrivée d'un parcours en ligne, où la séance s'arrêtait d'un coup et le bilan s'ouvrait
seul, et un bilan qui ne disait le résultat qu'en Cyber-Rogue. Lancé par le propriétaire le 22 novembre.

## 2. Spécification

| # | Règle |
| --- | --- |
| 1 | Core (révision IPC 1.27) : `state.arrival` `{kind, place, of}` dit l'issue dès qu'elle est connue, une seule fois par séance : `route` (bout d'un parcours en ligne), `workout` (entraînement fini), `grandprix` ou `race` (ligne passée par le cycliste, avec sa place). La séance continue ; « Terminer et enregistrer » la termine. Le bilan en garde une copie (`summary.arrival`) ; `summary.gp.finished` dit si la ligne a été passée. |
| 2 | Bout d'un parcours en ligne hors entraînement : demi-tour automatique (règle du lot N26, sans s'arrêter), autant de fois qu'il le faut. Après l'arrivée du Grand Prix ou de la Course, le demi-tour est permis. Le monde ouvert et le Cyber-Rogue gardent leur propre fin ; le Dernier survivant réglé « terminer la séance » après l'élimination aussi (choix du joueur). |
| 3 | Engine : `state.arrival` donne le même moment RÉSULTAT que RT1 (« VICTOIRE ! », « ARRIVÉE · 3e sur 8 », « ARRIVÉE ») puis la consigne de fin « COURSE FINIE · 3e sur 8 / Roule au calme… / Y puis A maintenu = bilan » (« PARCOURS FINI » au bout d'un parcours) ; rien de plus quand un mode a déjà donné son résultat. La pause s'ouvre sur « Terminer et enregistrer » (« Arrivée passée : A maintenu pour terminer et enregistrer »). Une seule fanfare par séance : `jingle_finish` à FINISHED seulement si aucun résultat n'a été annoncé. |
| 4 | Bilan : bandeau « ★ RÉSULTAT » en tête, le même pour tous les modes, avec les mots de la séance (`summary_view_model.gd` `result_card`) : VICTOIRE, ARRIVÉE · place, ÉLIMINÉ · place, ÉPREUVE TERMINÉE ou NON FINIE, COURSE NON FINIE, ENTRAÎNEMENT TERMINÉ ou ARRÊTÉ, SÉANCE TERMINÉE ; fond de la couleur du ton, jamais seule. Mêmes boutons qu'avant (Rejouer, Menu principal, Voir le bilan détaillé, Quitter). |
| 5 | Encart extensible : `result_card(summary, extra)` et `summary_view.gd` `result_lines` ajoutent des lignes sous le titre ; la ligue d'hiver (lot CH4) y mettra ses points de manche sans toucher au reste. |
| 6 | Écran de départ : « Objectif : … » sous la carte du parcours (objectif du mode, comme le bandeau « ▶ DÉPART » de RT1 ; d'après le mode choisi quand la trame ne le porte pas encore). |

## 3. Livraison

- Core : `session.py` (`_set_arrival`, `_u_turn_at_end` pour toutes les séances, Grand Prix et Course sans `_finish` à l'arrivée, `summary.arrival`), `ipc_server.py` (`arrival`, révision 1.27), `grandprix/mode.py` (`summary.gp.finished`).
- Engine : `feedback_model.gd` (`arrival_result`, moment de l'arrivée), `event_sounds_model.gd` (`issue_known`), `summary_view_model.gd` (`result_card`), `summary_view.gd` (bandeau du résultat, `result_lines`), `menu_flow.gd` (pause après l'arrivée), `start_screen.gd` (`set_goal`), `main.gd` (`_start_goal`).
- Contrat : `ipc_v1.md` (champ `arrival`, `summary.gp.finished`, journal 1.27), `state.schema.json`.
- Tests : `test_rt2_fin_commune.py` (nouveau), `test_u_turn_auto.py`, `test_u_turn.py`, `test_race_mode.py`, `test_contract_ipc.py` ; engine `test_feedback.gd`, `test_summary_view_model.gd`, `test_event_sounds_model.gd`.
- Base : branche de RT1 (#959, empilée sur #958), `main` fusionnée dedans pour la Course (CR1, #939).

## Recette PC
Catégorie : logique
- Cloud : suites du core et de l'engine, captures low, medium et high du bandeau d'arrivée, de la consigne de fin, du bilan et de l'écran de départ (dossier du projet `captures/rt2-fin-commune/`)
- Fumée (≈ 5 min) : `python3 engine/tests/menu_bench.py --native --scenario course --scenario elimination --qualite medium --voies clavier --out {sortie}`
- Matrice medium (≈ 30 min) : `python3 engine/tests/sim_bench.py --native --probe --scenario grand_prix --scenario course_onze --scenario erg_village --quality medium --out {sortie}` (fin par `end_session` comme avant : la séance ne finit plus seule à l'arrivée)
- Essai vélo : arrivée d'une Course ou d'un Grand Prix, on continue à rouler, Y puis A maintenu ouvre le bilan qui commence par le résultat
- Versions : révision IPC 1.27 (libérée par l'abandon de RT3) ; WORLDGEN_VERSION et SCHEMA_VERSION inchangés
