# Lot VD6 – Épreuves de piste

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : épreuves de piste en modules purs (toutes : poursuite, kilomètre, 200 m, scratch, points, tempo, élimination, keirin, omnium, heure) | Python | VD3, DS1, AS6 | Grande | En PR (version 4.0) |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Plan validé par le propriétaire le 6 novembre (lot VD0).

## 1. Objectif

Écrire les règles de toutes les épreuves du §5 (décision du propriétaire du 6 novembre : toutes dès la première livraison) dans un paquet `track/` du core, un fichier par épreuve, et les brancher dans la séance.

## 2. À lire

§5 du plan ; `core/src/openride_core/survivor.py` (élimination), `wtf/mode.py` (forme d'un mode), `replay.py` (fantôme), `records.py`, `jerseys.py` (barème) ; cahier AS6 (véhicule et abri, pour le derny du keirin).

## 3. Travail demandé

- Paquet `track/` : `pursuit.py`, `time_trial.py` (kilomètre, 500 m, 200 m lancé), `scratch.py`, `points.py`, `tempo.py`, `elimination.py` (règles de DS, sans copie de code), `keirin.py` (derny d'AS6 qui s'écarte à 3 tours de l'arrivée), `omnium.py` (enchaîne les épreuves et additionne les points), `hour.py`, et les épreuves par équipes (ajout du propriétaire du 6 novembre) : `team_sprint.py` (vitesse par équipes), `team_pursuit.py` (poursuite par équipes, relais et coureur qui s'écarte), `madison.py` (américaine, relais du joueur et de son coéquipier) ; notion d'équipe commune (coéquipiers bots, classement par équipe) ; interface commune (`start`, `step`, `frame`, `summary`).
- Départ arrêté et départ lancé ; tours, cloche du dernier tour ; tours pris ; arrivée.
- Records par piste et par épreuve ; tours dans le journal et dans le FIT (`lap`).
- Pause et coupure du trainer figent l'épreuve.

## 4. Critères d'acceptation

1. Chaque épreuve a ses tests positifs et négatifs (course simulée de bout en bout, même graine, même résultat).
2. Trame `track` sous le budget de VD1.
3. Aucune épreuve ne renvoie de pente (test).

## 5. Fichiers touchés

- `core/src/openride_core/track/` (nouveau), `session.py`, `records.py`, `fit_export.py`, leurs tests.

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 6, 12 et 14 ms) et ses captures sont validées par le propriétaire avant la fusion.

## 6. Livraison (7 novembre, demande du propriétaire : « lance VD6 »)

- Paquet `core/src/openride_core/track/` : `base.py` (interface commune `start`, `step`, `frame`, `summary`, `take_journal` ; tours du cycliste sur la ligne, premier passage d'une grille derrière la ligne non compté ; journal `track`), `time_trial.py` (kilomètre, 500 m, 200 m lancé : 425 m d'élan, 200 m chronométrés), `hour.py`, `free.py` (séance libre, seule épreuve qui accepte l'ERG), `pursuit.py` (deux équipes ou deux coureurs de part et d'autre, chrono sur le `count`-ième coureur, rejoint à un demi-tour), `team_sprint.py` (chacun mène un tour puis s'écarte, chrono sur le dernier), `team_pursuit.py` (relais tous les demi-tours ou tours, coureur lâché à plus de 30 m du 3e, chrono sur le 3e), `mass.py` (socle des courses en peloton : origine sur la ligne, tours pris et perdus sur la médiane des autres, distance ajustée, cloche, arrivées, une minute de grâce), `scratch.py`, `points.py` (5, 3, 2, 1 tous les 10 tours, double au dernier, ±20 par tour), `tempo.py` (1 point par tour dès le 5e), `elimination.py` (habillage de `survivor.SurvivorRace`, une arche sur la ligne tous les 2 tours), `keirin.py` (derny de 30 à 50 km/h, s'écarte à 3 tours, déclassement si on le passe), `madison.py` (équipes de 2, la distance de l'équipe n'avance qu'avec le coureur en course, relais tous les 375 m avec la vitesse du relayé), `omnium.py` (scratch, tempo, élimination, points ; points de place 40, 38… ; un tour neutralisé entre deux épreuves) ; `__init__.py` : registre `EVENTS` (réglages permis et défauts, plateau), `check`, `field_size`, `make`, `teams`.
- Séance (`session.py`) : `start` avec `mode` = `track` et `track` = `{event, réglages}`, sur un vélodrome seulement ; plateau de bots à profil composé par le core (grille, ou équipe adverse sur l'autre ligne de poursuite) ; objet `track` de `state` ; lignes `track_start`, `track`, `track_summary` au journal ; `summary.track` ; record de la piste à la fin de la séance gardée ; pas de circulation ni de cyclistes du décor dans la salle.
- Records (`records.py`) : `RecordBook.add_track`, une table par épreuve (`track:kilo`, `track:hour`…) ; `distance_m` facultatif d'un record, à temps égal la plus grande distance d'abord (record de l'heure).
- FIT (`fit_export.py`) : chaque passage du cycliste sur la ligne est un tour (`lap`), à l'enregistrement comme au rattrapage d'un journal.
- Contrat : révision 1.7 de l'IPC (`ipc_v1.md`, `state.schema.json`), `hello_ack.config.modes` avec `track`, pire trame 3 690 octets (`ipc_budget.worst_track`, `_extras_1_7`) ; l'engine annonce 1.7 et ignore l'objet jusqu'au HUD de piste (VD9).
- Tests : `core/tests/test_track_events.py` (chaque épreuve de bout en bout, cas refusés, même graine même résultat, pause qui fige, aucune pente, taille de l'objet), `core/tests/test_track_session.py` (kilomètre jusqu'au record et au FIT, plateaux, refus, ERG, salle sans circulation).
- Reste aux lots suivants : réglages persistés et menu (`list_mode_options`, `set_mode_option`, lot VD10), bots qui courent l'épreuve (suivre le derny, relais de l'américaine et des poursuites par équipes, lot VD7), HUD, tableau d'affichage et cloche (VD9).
