# Lot R1 – Contrat IPC v1.4 : boutons Z et A, liste des modes, champ `rogue`, messages `room` et `loot`, commandes de run

## 1. Objectif

Fixer, **avant tout code**, les ajouts compatibles au contrat IPC dont le mode Cyber-Rogue a besoin. Le core reste le maître : il compose la run, calcule les règles et pilote le trainer ; l'engine affiche ce qu'il reçoit et envoie les commandes du menu. C'est une décision du propriétaire, comme N1 et P1.

Numérotation (confirmée le 26 octobre) : la révision 1.2 est prise par Q1, N13 et O4, la 1.3 par P1 ; les séries R, T et V ajoutent la **1.4**. Les ajouts communs avec la série T (événements Z et A) et la série V sont rédigés une seule fois, par le premier des lots R1, T1 ou V1.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/contracts/ipc_v1.md` (tout, en particulier §3, §4, §5 et §8), schémas de `docs/contracts/ipc/`.
2. `docs/2.0/PLAN_SERIE_R.md` (§2 décisions, §4, §7 questions), `docs/2.0/GDD_CYBER_ROGUE.md`.
3. `docs/lots/LOT_R6_run_deck_boss.md` (phases), `docs/lots/LOT_R13_menu_cyber_rogue.md` (parcours de lancement), `docs/2.0/PLAN_SERIE_T.md` (contrat de la série T).
4. Code : `core/src/openride_core/zwift_click.py` (`KEYPAD_BITS`, `InputEvent`, détection court et long), `core/src/openride_core/ipc_server.py`, `engine/scripts/ipc_client.gd`, `engine/scripts/menu_model.gd`.

## 3. Prérequis

P1 livré (révision 1.3). Les réponses du propriétaire aux questions R-Q1 à R-Q10 du plan (§7).

## 4. Travail demandé

Rédiger les ajouts suivants dans `ipc_v1.md` et les schémas, chacun avec sa ligne au journal des changements (§8). Propositions de départ, à confirmer par le propriétaire :

### 4.1 Boutons Z et A

- Nouveaux événements `input` et valeurs de `input_event` : `Z_SHORT`, `A_SHORT`, `A_LONG`. Mêmes seuils que + et − (court sous 0,5 s, long à partir de 0,9 s, décision au relâchement, entre les deux : ignoré).
- B reste lu comme « − » (contournement du boîtier gauche) ; aucun nouvel événement pour B.
- **Y reste la pause du core dans tous les modes** (lot N6 ; décision R-Q6 du 26 octobre), interne, sans événement.
- **Mode Cyber-Rogue :** `Z_SHORT`, `A_SHORT` et `A_LONG` sont consommés par le core (A court : attaque, purge, valider en couloir ; A long : Disjoncteur ou carte de module A, deck en couloir ; Z : parade, relance) et relayés à l'engine pour l'effet visuel et sonore.
- Clavier de l'engine (`input_event`) : Z et A pour les appuis courts, A maintenu 0,9 s pour l'appui long ; Échap et Y restent la pause.

### 4.2 Liste des modes dans `hello_ack.config`

- Tableau facultatif `modes` : modes de jeu que ce core sait lancer, parmi `"ride"` (parcours libre), `"erg"` (entraînement), `"rogue"` (Cyber-Rogue) ; d'autres valeurs pourront s'ajouter (série W : `"open_world"`). Absent : l'engine suppose `["ride", "erg"]`, comportement de la 1.0.
- L'accueil du menu de l'engine se construit à partir de cette liste (lot R13 ; la 1.0 prépare déjà cette construction, voir le plan §6). Une valeur inconnue de l'engine est ignorée.
- Objet facultatif `rogue` dans `hello_ack.config`, présent si `"rogue"` est dans `modes` : `{ "w_prime_j", "w_prime_estimate_j", "cp_w", "objectives", "durations_min" }`. `w_prime_estimate_j` vient de R16 (`null` sans estimation fiable) ; `objectives` = `["endurance", "threshold", "vo2max"]` ; `durations_min` = `[30, 45, 60, 90]`.

### 4.3 Commandes

| `name` | `args` | Effet |
| --- | --- | --- |
| `start_run` | `{ "objective": chaîne, "duration_min": entier, "seed": entier ou null, "w_prime_j": nombre ou null }` | Depuis `IDLE`, `READY` ou `FINISHED` : compose la run (R15), `session_state` passe à `LOADING` puis `READY`, `mode` = `"ROGUE"`. `start` lance ensuite la run, comme une séance. `seed` nul : tirée par le core ; `w_prime_j` nul : valeur de `config.toml` |
| `rogue_resync` | `{}` | Demande au core de renvoyer le message `room` de la salle en cours et, en couloir, le message `loot` |

Fin de run : `end_session` (`save` vrai) suffit ; le résultat (`abandoned` si la run n'est pas finie) est dans `summary.rogue`. La commande `abandon_run` du plan n'est pas ajoutée (décision R-Q3 du 26 octobre).

Nouveau code d'erreur : `run_invalid` (objectif ou durée hors liste).

### 4.4 Message `state`

- `mode` gagne la valeur `"ROGUE"`. En run : `route_id`, `lat`, `lon`, `alt` à `null` ; `route_length_m` = longueur de la salle en cours ; `s` = distance depuis le début de la run ; `grade` = pente de l'ennemi après cartes ; `grade_sent` = pente envoyée (formule centrée Q2) ; `gear` de 1 à 12, `gears_total` = 12.
- Objet facultatif `rogue`, présent seulement en mode `ROGUE`, dans chaque trame :

| Champ | Type | Sens |
| --- | --- | --- |
| `phase` | chaîne | `WARMUP`, `ROOM`, `CORRIDOR`, `BOSS`, `RECOVERY`, `COOLDOWN`, `RESULTS` |
| `room_id` | entier | Numéro de la salle (le même que dans `room`) ; change à chaque salle |
| `room_index`, `rooms_total` | entiers | Salle en cours (à partir de 1) et nombre prévu |
| `archetype` | chaîne ou null | `diesel`, `puncheur`, `grimpeur`, `sprinteur`, `saboteur`, `boss` |
| `boss_phase` | entier ou null | 1 à 3 |
| `s_room` | nombre | Distance dans la salle (m) |
| `enemy_hp`, `enemy_hp_max` | nombres | Points de vie de l'ennemi |
| `shield`, `adrenaline` | nombres | 0 à `shield_max` et 0 à 100 |
| `shield_max` | nombre | 100 sans bonus |
| `w_bal_j`, `w_prime_j` | nombres | Réserve anaérobie et sa capacité |
| `posture` | chaîne | `ROC`, `FLUIDE`, `VELOCE`, `ARRET` |
| `firewall_gap_m` | nombre | Avance sur le Firewall (négatif : rattrapé) |
| `gold` | entier | Or de la run |
| `windows` | tableau | Fenêtres actives, au plus 4 : `{kind, s_start, s_end}`, `kind` parmi `arch`, `strike_target`, `z_zone`, `pad`, `purge`, `tunnel` |
| `hack` | objet ou null | Piratage du Saboteur : `{locked: booléen, forced_gear: entier ou null, until_s}` |
| `overheat` | booléen | Surchauffe (objectif endurance, décision Q3) |
| `loot_focus` | entier ou null | En couloir : carte ou porte sélectionnée (0 à 4) |
| `events` | tableau | Événements de jeu de la dernière trame, au plus 4 : `perfect_shift`, `hit`, `crit`, `parry`, `parry_miss`, `firewall_contact`, `room_won`, `room_fled`, `room_skipped`, `defeat`, `card_taken` |

- Taille : la trame la plus chargée (mode `ROGUE`, `devices`, `rogue` complet avec 4 fenêtres et 4 événements) tient dans 1 400 octets (outil X25 s'il existe, sinon test du lot).

### 4.5 Messages `room` et `loot` (core vers engine, sur événement)

- `room` : `v`, `room_id`, `part`, `parts`, `archetype`, `variant`, `length_m`, `nominal_s`, `profile` (pente tous les 10 m : liste de `[s_m, grade_pct]`, au plus 1 500 points), `markers` (liste de `{kind, s_m, len_m, param}` : `arch`, `strike_target`, `z_zone`, `pad`, `purge`, `tunnel`, `rock`, `shockwave`), `next` (`room_id` et archétype de la salle suivante si elle est déjà connue, sinon `null`). Même découpage en parties de 60 000 octets que `routes`. Envoyé au début de chaque salle et, pendant le couloir, pour chacune des deux portes.
- `loot` : `v`, `corridor_id`, `cards` (3 cartes : `{id, name, kind, text, replaces_gear}`), `doors` (2 portes : `{side: "left" | "right", room_id, archetype}`), `reroll_cost`, `gold`. Renvoyé après chaque relance.
- L'engine qui voit un `room_id` ou un `corridor_id` inconnu dans `state.rogue` envoie `rogue_resync`, au plus une fois par seconde.

### 4.6 Bilan

`summary` gagne l'objet facultatif `rogue` : `{ result: "victory" | "defeat" | "abandoned", objective, duration_min, seed, rooms_won, rooms_fled, rooms_skipped, rooms_total, defeats, boss: "won" | "fled" | "not_reached", gold, cards: [ids], perfect_shifts, unlocks: [ids] }`.

## 5. Fichiers concernés

- **Modifiés :** `docs/contracts/ipc_v1.md`, `docs/contracts/ipc/state.schema.json`, `cmd.schema.json`, `input.schema.json`, `hello_ack.schema.json`, `error.schema.json`, `docs/SRS_v1.1.md` (§4.2 boutons, §11 section `[rogue]`), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Créés :** `docs/contracts/ipc/room.schema.json`, `docs/contracts/ipc/loot.schema.json`.
- **Interdits :** tout code.

## 6. Modifications de contrat autorisées

Ajouts compatibles décrits au §4, et seulement eux. `v` reste 1.

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe, dont `core/tests/test_docs_coherence.py` (schémas valides).
2. Une trame `state` d'exemple en mode `ROGUE` est valide ; une trame de la 1.0 sans `rogue` aussi.
3. Exemples valides de `room`, `loot`, `start_run`, `rogue_resync` et d'un `hello_ack` avec et sans `modes`.
4. La trame d'exemple la plus chargée fait moins de 1 400 octets (calcul noté dans le contrat).
5. Le propriétaire a validé les choix du §4 (notés en tête du lot à la livraison).

## 8. Hors périmètre

- Contrat de la série T (couche `segments`, `segment_result`) et de la série V (`xp`, `equip`) : seuls les événements de boutons sont communs.
- Multijoueur, classement en ligne.
