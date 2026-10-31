# Lot R8 – Intégration dans la session du core : mode ROGUE, formule centrée, boutons Z et A, pause Y, journal, pause et reprise

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Intégration dans la session du core : mode ROGUE, formule centrée, boutons Z et A, pause Y, journal, pause et reprise | Python | T1, R6, R15, Q4 | Grande | **Livré le 27 octobre**, **version 2.0** |

## 1. Objectif

Brancher le moteur de run (R6) et le scénariste (R15) dans la session du core : commande `start_run`, mode `ROGUE`, pente envoyée selon la formule centrée de la décision Q2, lecture des boutons Z et A du Click (Y reste la pause, comme dans les autres modes), champ `rogue` de `state`, messages `room` et `loot`, journal, FIT et reprise après un plantage. Lot interne : il touche `session.py`, cœur de la boucle à 50 Hz.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/contracts/ipc_v1.md` (révision 1.4, lot T1), `docs/SRS_v1.1.md` §4 et §5.
2. `docs/2.0/PLAN_SERIE_R.md` §2 et §7, `docs/lots/LOT_T1_contrat_1_4.md` (§4.1 et §4.3), `LOT_R6_run_deck_boss.md`, `LOT_R15_scenariste_run.md`, `LOT_N8_reprise_plantage_core.md`.
3. Code : `core/src/openride_core/session.py`, `gearing.py`, `zwift_click.py`, `input_providers.py`, `ipc_server.py`, `ipc_lists.py` (découpage en parties), `recorder.py`, `resume.py`, `fit_export.py`.

## 3. Prérequis

T1 (contrat 1.4), R6 et R15 livrés ; R0 (valeurs de la rampe) ou ses défauts ; Q4 livré.

## 4. Travail demandé

### 4.1 Lancement et états

- `start_run` (T1 §4.3) depuis `IDLE`, `READY` ou `FINISHED` : vérifie les arguments (`run_invalid` sinon), compose le scénario (R15), `LOADING` puis `READY`, `mode` = `"ROGUE"`. `start` passe en `RUNNING` ; `end_session` termine (résultat `abandoned` si la run n'est pas en `RESULTS`).
- `hello_ack.config` : `modes` contient `"rogue"` ; objet `rogue` (W' de la configuration, estimation de R16 si elle existe, CP, objectifs, durées).
- `select_route` ou `select_workout` pendant `READY` en mode `ROGUE` : la run préparée est abandonnée, retour au mode classique.

### 4.2 Pente envoyée et braquets

- Mode `ROGUE` : cassette de 12 vitesses propre au mode (la configuration `n_gears` du mode classique n'est pas touchée), départ en 6.
- `grade_sent = clamp(pente_ennemi + (vitesse − 6) × 1, grade_min_pct, grade_max_pct)` (décision Q2), puis la rampe propre au mode : `[rogue] grade_rate_up_pct_per_s` et `grade_rate_down_pct_per_s` (défauts 8 et 12 en attendant R0, bornes 0,1 à 100). Changement de braquet : immédiat, comme en mode classique.
- `difficulty_pct` (Q1) : **non appliqué** en mode `ROGUE` (décision R-Q1 du 26 octobre) ; le HUD de la run ne l'affiche pas.
- Vitesse virtuelle : physique existante sur la pente de l'ennemi (sans le décalage du braquet), comme le Firewall (R4).

### 4.3 Boutons

- `zwift_click.py` : A et Z sont décodés depuis la révision 1.3 (événements `Z_SHORT`, `Z_LONG`, `A_SHORT`, `A_LONG`) ; R8 les branche sur le mode `ROGUE`.
- Mode classique : inchangé (Y = pause interne, N6 ; A et Z sans effet jusqu'à la série T).
- Mode `ROGUE` (plan de boutons commun, spécification générale, §7.1) : + et B courts et longs vers le braquet (±1, ±3) ; `Z_SHORT` et `Z_LONG` vers `RunEngine` ; `A_SHORT` et `A_LONG` vers la sélection en couloir, sinon seulement relayés à l'engine (vue de caméra) ; Y = pause ou reprise, comme en mode classique.
- `input_event` de l'engine (clavier) accepte les mêmes noms.

### 4.4 Pause, pannes et reprise

- Pause (Y, Échap, perte de l'engine, panne du journal) : le moteur de run est figé (Firewall, minuterie des fenêtres et W'bal compris), pente envoyée à 0 %.
- Click perdu : la run continue mais le Firewall s'arrête (R4) ; le clavier reste actif.
- Reprise après un plantage du core (N8) : `RunEngine.snapshot()` écrit dans le journal toutes les 5 s ; au redémarrage, la run reprend au **début de la salle en cours**, bouclier, or, deck et adrénaline de ce début de salle.

### 4.5 Journal et FIT

- Journal JSONL : une ligne `rogue` par événement de jeu (`room_start`, `room_won`, `room_fled`, `room_skipped`, `defeat`, `card_taken`, `perfect_shift`, `boss_phase`, `run_end`), avec l'empreinte de la table d'équilibrage (R7).
- FIT : séance sans position GPS, distance virtuelle ; sport « cyclisme », sous-sport « virtuel » ; tours au début de chaque salle et de chaque phase du boss.
- `summary` : objet `rogue` (T1 §4.3).

### 4.6 Messages

- `room` au début de chaque salle et pour les deux portes d'un couloir ; `loot` à l'entrée en couloir et après chaque relance ; renvoi sur `rogue_resync`. Découpage en parties comme `routes`, hors de la boucle à 50 Hz.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/session.py`, `zwift_click.py`, `input_providers.py`, `ipc_server.py`, `config.py` (section `[rogue]` : rampe), `recorder.py`, `resume.py`, `fit_export.py` ; `docs/SRS_v1.1.md` §11, `README.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Créés :** `core/tests/test_rogue_session.py`.

## 6. Modifications de contrat autorisées

Aucune au-delà de la révision 1.4 (lot T1).

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe.
2. Session simulée (trainer et Click simulés) : `start_run` puis `start`, une run de 30 min en temps accéléré jusqu'à `RESULTS`, trames `state` valides pour le schéma 1.4, `summary.rogue` valide.
3. `grade_sent` suit la formule centrée et ses bornes ; `difficulty_pct` n'a pas d'effet en mode `ROGUE` (décision R-Q1).
4. Mode classique : mêmes trames et même comportement des boutons qu'avant le lot (tests existants inchangés).
5. Y met en pause et reprend en mode `ROGUE` comme en mode classique ; B long fait −3 vitesses ; A ne change rien au jeu hors couloir.
6. Plantage simulé du core au milieu d'une salle : reprise au début de cette salle avec l'état noté.
7. FIT de la run validé par le SDK officiel (lot H5).
8. La trame `state` la plus chargée en mode `ROGUE` fait moins de 1 400 octets.

## 8. Hors périmètre

- Affichage (R10 à R13), déblocages permanents (R9).

## 9. Livraison (27 octobre 2026)

- `rogue/mode.py` : `RogueMode` (une run en cours, pure, pilotée par la session), `parse_start_run` (refus `run_invalid` / `item_locked`), `hello_block`, `journal_line`. La session (`session.py`) gagne `start_run`, `rogue_resync`, le mode `ROGUE` (`ipc_server.CORE_MODES`), la trame `state.rogue`, et lâche la run à `select_route` / `select_workout`.
- **Pente :** `grade_sent = pente de l'ennemi + (vitesse − 6)`, bornée −10..16, avec la rampe R8 (`[rogue] grade_rate_up_pct_per_s` = 8, `grade_rate_down_pct_per_s` = 12, bornes 0,1 à 100 ; SRS §11 à jour) ; immédiate à un changement de vitesse. `difficulty_pct` et la formule classique sont ignorés (R-Q1). Le trainer est relâché à la fin et en pause.
- **Boutons :** Z et A passent à la run (`press`), les vitesses par `shift`, Y garde la pause ; aucun nouvel événement.
- **Journal :** lignes `rogue`, `rogue_run` (celle de R9, avant `rec.finish`) et `rogue_snapshot`. **FIT :** un tour par salle (début = ligne `rogue room_start`), `num_laps` en conséquence.
- **Reprise :** instantané (pickle zlib+base64, ~8,6 ko) écrit au début de chaque phase ou salle ; la reprise repart au début de la salle en cours. **Écart au cahier :** pas d'instantané toutes les 5 s.
- **Écarts :** vies et châssis arrivent par `session.rogue_provider` (défaut : 0 vie, châssis standard) jusqu'à V11 ; l'estimation de W' n'est pas encore branchée (`estimate_cp.estimate_w_prime`, à lancer au démarrage dans un thread, hors de la boucle 50 Hz).
- Tests : `core/tests/test_rogue_session.py` (20), `test_contract_ipc.py` (modes).
