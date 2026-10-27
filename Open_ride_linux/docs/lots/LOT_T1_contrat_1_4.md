# Lot T1 – Contrat IPC 1.4 commun aux séries R, T et V : segments, bonus, bots à profil, Cyber-Rogue, progression

## 1. Objectif

Fixer en **un seul lot et une seule PR**, avant tout code des séries R, T et V qui en dépend, la révision 1.4 du contrat IPC et la couche `segments` du format `.world`. Décision du propriétaire du 27 octobre (décision D4 de l'audit de cohérence) : les anciens lots de contrat R1 et V1 sont réunis ici, pour qu'il n'y ait qu'un journal, une revue et une numérotation. Le core reste le maître : il calcule les règles du jeu (invariant A2) ; l'engine affiche et demande.

**Lot interne (décision du propriétaire) :** il change le contrat et se valide avant R8, R9, R10 à R13, R17, T3, T5, T7 à T15, V5, V6, V8, V9 et V11.

## 2. À lire

1. `docs/SPECIFICATION_GENERALE.md` §6.1 (révisions), §6.2 (format `.world`), §7.1 (boutons, seule référence) et §7.2 (vues de caméra).
2. `docs/contracts/ipc_v1.md` (tout, en particulier §2, §3, §5 et §8), schémas de `docs/contracts/ipc/`, `docs/contracts/world_format_v1.md` §10.
3. Plans `docs/2.0/PLAN_SERIE_T.md` (§3 et décisions du 27 octobre au §6), `docs/2.0/PLAN_SERIE_R.md` (§2, §4, §7), `docs/2.0/GDD_CYBER_ROGUE.md`, `docs/2.0/PLAN_SERIE_V.md` (§2 et questions V-Q4 à V-Q13).
4. Modules déjà livrés dont les noms de champs font foi : `core/src/openride_core/segments.py` (T2), `segment_timing.py` (T4), `powerups.py` (T6), `gaps.py` (T16), `progression.py` (V2 à V4) ; cahiers `LOT_R6_run_deck_boss.md`, `LOT_R13_menu_cyber_rogue.md`, `LOT_V3_catalogue_equipement.md`, `LOT_V3b_pieces.md`, `LOT_V4_profil_local.md`.
5. Code : `core/src/openride_core/ipc_server.py`, `engine/scripts/ipc_client.gd`, `engine/scripts/menu_model.gd`, `core/src/openride_core/ipc_budget.py` (pire trame par révision, lot X25).

## 3. Prérequis

- P1 livré (révision 1.3).
- La PR #287 fusionnée : elle ajoute à la 1.3, une seule fois, les événements de tous les boutons du Click (`A_SHORT`, `A_LONG`, `Z_SHORT`, `Z_LONG`, `Y_SHORT`, `LEFT_SHORT`, `RIGHT_SHORT`, `UP_SHORT`, `DOWN_SHORT`). Ce lot les utilise sans les redéfinir.
- Réponses du propriétaire aux questions R-Q1 à R-Q10, T-Q1 à T-Q6 et V-Q1 à V-Q13 (toutes tranchées).

## 4. Travail demandé

Rédiger les ajouts suivants dans `ipc_v1.md`, ses schémas et `world_format_v1.md`, avec **une seule ligne** « révision 1.4 » au journal des changements (§8 du contrat).

### 4.1 Commun aux trois séries

- **Boutons :** aucun nouvel événement. Le sens de chaque bouton dans chaque mode est celui du tableau de la spécification générale §7.1 ; le contrat ne le recopie pas.
- **Modes :** `hello_ack.config.modes` (révision 1.3) gagne la valeur `"rogue"` ; `mode` de `state` gagne `"ROGUE"`.
- **Taille :** chaque trame `state` reste sous la limite de 4 096 octets de la révision 1.3 dans le pire cas de chaque mode (classique avec segment, bonus et 5 bots à profil ; ERG ; `ROGUE` complet avec 4 fenêtres et 4 événements ; avec `devices` ou `wind`). Le lot ajoute la révision 1.4 à l'outil `ipc_budget` (X25) et note les tailles dans le contrat. Les messages courts (`segment_result`, `xp_result`, `progression`, `loot`) visent 1 400 octets.
- **Bilan :** `summary` gagne les objets facultatifs `segments` (T), `rogue` (R) ; le bilan de progression est le message `xp_result` (V).

### 4.2 Partie T : segments, bonus et bots à profil

#### Couche `segments` du format `.world`

Couche facultative `segments.json` (mineur suivant du format, règle des couches facultatives) : la liste rendue par `Segment.to_dict()` de `segments.py` (identifiant, nom, type `sprint` ou `climb`, `s_start`, `s_end`, longueur, pente moyenne, gain, catégorie `4` à `HC`, source `auto` ou `manual`). L'engine la lit lui-même, comme les autres couches ; le compilateur l'écrit (lot T3, segments manuels dans `<parcours>.segments.toml`).

#### Champs de `state`

| Champ | Type | Sens |
| --- | --- | --- |
| `segment` | objet ou absent | Segment en cours ou prochain : `id`, `kind`, `category`, `d_to_start_m` (0 dans le segment), `elapsed_s` (ou `null` avant le départ), `gap_to_pr_s` (écart au record, négatif si en avance, ou `null`) |
| `powerup` | objet ou absent | `held` (bonus en réserve : `light`, `aero`, `power` ou `null`), `active` (bonus actif ou `null`), `remaining_s` ; absent en ERG (T-Q2) |
| `jerseys` | objet ou absent | Détenteurs des maillots pendant la séance : `sprint` et `kom`, chacun `"me"`, un `id` de bot ou `null` (T14) |
| `bot_ahead`, `bot_behind` | chaîne ou `null` | Identifiants des voisins immédiats (T16) |

Chaque élément de `bots` gagne, facultatifs : `profile` (`climber`, `rouleur`, `sprinter`, `diesel` ou `null` pour un bot à puissance constante), `cp_w`, `mass_kg`, `wbal_pct`, `jersey` (`sprint`, `kom` ou `null`) et `gap_s` (écart en temps de passage, positif si le bot est devant).

#### Message `segment_result` (core vers engine, à la fin de chaque passage)

`v`, `segment_id`, `name`, `kind`, `time_s`, `with_powerup` (booléen : record « avec » ou « sans » bonus, T-Q1), `pr` (booléen), `pr_time_s` (ancien record ou `null`), `rank`, `rank_total` (classement local avec bots et fantôme, T5), `points` (points de maillot gagnés, T14), `equipment_gain_s` (temps gagné ou perdu par l'équipement sur le passage, négatif si gagné, ou `null`, série V). Répété 3 fois à une seconde d'intervalle avec le même `segment_id`, l'engine ignorant les doublons.

Le journal de séance gagne l'événement `powerup` (type, début, durée) sans changement des champs existants ; il n'est pas dans le contrat IPC (lot T5).

### 4.3 Partie R : mode Cyber-Rogue

- `hello_ack.config.rogue`, facultatif, présent si `"rogue"` est dans `modes` : `{ "w_prime_j", "w_prime_estimate_j", "cp_w", "objectives", "durations_min" }`. `w_prime_estimate_j` vient de R16 (`null` sans estimation fiable) ; `objectives` = `["endurance", "threshold", "vo2max"]` ; `durations_min` = `[30, 45, 60, 90]`.
- Boutons du mode : tableau de la spécification générale §7.1 (Z court : attaque, parade, purge ou relance en couloir ; Z long : carte ou relique active ; A court : carte ou porte suivante ; A long : valider ; ± : vitesse du frein). Le core consomme ces événements et les relaie à l'engine pour l'effet visuel et sonore.

#### Commandes de run

| `name` | `args` | Effet |
| --- | --- | --- |
| `start_run` | `{ "objective": chaîne, "duration_min": entier, "seed": entier ou null, "w_prime_j": nombre ou null }` | Depuis `IDLE`, `READY` ou `FINISHED` : compose la run (R15), `session_state` passe à `LOADING` puis `READY`, `mode` = `"ROGUE"`. `start` lance ensuite la run, comme une séance. `seed` nul : tirée par le core ; `w_prime_j` nul : valeur de `config.toml` |
| `rogue_resync` | `{}` | Demande au core de renvoyer le message `room` de la salle en cours et, en couloir, le message `loot` |

Fin de run : `end_session` (`save` vrai) suffit ; le résultat (`abandoned` si la run n'est pas finie) est dans `summary.rogue`. La commande `abandon_run` du plan n'est pas ajoutée (décision R-Q3 du 26 octobre).

Nouveau code d'erreur : `run_invalid` (objectif ou durée hors liste).

#### Champs de `state`

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
| `windows` | tableau | Fenêtres actives, au plus 4 : `{kind, s_start, s_end}`, `kind` parmi `arch`, `strike_target`, `parry_zone`, `pad`, `purge`, `tunnel` |
| `hack` | objet ou null | Piratage du Saboteur : `{locked: booléen, forced_gear: entier ou null, until_s}` |
| `overheat` | booléen | Surchauffe (objectif endurance, décision Q3) |
| `loot_focus` | entier ou null | En couloir : carte ou porte sélectionnée (0 à 4) |
| `events` | tableau | Événements de jeu de la dernière trame, au plus 4 : `perfect_shift`, `hit`, `crit`, `parry`, `parry_miss`, `firewall_contact`, `room_won`, `room_fled`, `room_skipped`, `defeat`, `card_taken` |


#### Messages `room` et `loot` (core vers engine, sur événement)

- `room` : `v`, `room_id`, `part`, `parts`, `archetype`, `variant`, `length_m`, `nominal_s`, `profile` (pente tous les 10 m : liste de `[s_m, grade_pct]`, au plus 1 500 points), `markers` (liste de `{kind, s_m, len_m, param}` : `arch`, `strike_target`, `parry_zone`, `pad`, `purge`, `tunnel`, `rock`, `shockwave`), `next` (`room_id` et archétype de la salle suivante si elle est déjà connue, sinon `null`). Même découpage en parties de 60 000 octets que `routes`. Envoyé au début de chaque salle et, pendant le couloir, pour chacune des deux portes.
- `loot` : `v`, `corridor_id`, `cards` (3 cartes : `{id, name, kind, text, replaces_gear}`), `doors` (2 portes : `{side: "left" | "right", room_id, archetype}`), `reroll_cost`, `gold`. Renvoyé après chaque relance.
- L'engine qui voit un `room_id` ou un `corridor_id` inconnu dans `state.rogue` envoie `rogue_resync`, au plus une fois par seconde.

#### Bilan

`summary` gagne l'objet facultatif `rogue` : `{ result: "victory" | "defeat" | "abandoned", objective, duration_min, seed, rooms_won, rooms_fled, rooms_skipped, rooms_total, defeats, boss: "won" | "fled" | "not_reached", gold, cards: [ids], perfect_shifts, unlocks: [ids] }`.


### 4.4 Partie V : progression, Garage et avatar

#### `hello_ack.config.progression` (facultatif)

Objet présent dès que le core connaît la progression (absent sinon : l'engine n'affiche rien de la série V) :

| Champ | Type | Sens |
| --- | --- | --- |
| `level` | entier 1 à 50 | Niveau actuel |
| `xp` | entier | Expérience totale |
| `xp_level_start`, `xp_next_level` | entier, entier ou `null` | Seuils du niveau actuel et du suivant (`null` au niveau 50) |
| `coins` | entier ≥ 0 | Solde de pièces |
| `equipped` | objet | Identifiant choisi par emplacement : `frame`, `wheels`, `helmet`, `kit`, `socks`, `glasses` |
| `avatar` | objet | Réglages de l'avatar (§4.4) |
| `lives` | entier ≥ 0 | Vies du mode Cyber-Rogue en réserve (série R) |

#### Message `xp_result` (core vers engine, en fin de séance)

Message dédié (décision D7 de l'audit IPC, validée par le propriétaire ; nommé `xp_result` pour ne pas le confondre avec l'entier `progression.xp`). Envoyé quand `session_state` passe à `FINISHED`, après le `summary`, puis répété une fois par seconde tant que la séance reste `FINISHED` (au plus 10 fois), comme `hello` se répète : une perte UDP ne fait pas disparaître le bilan.

Champs : `eligible` (booléen), `reason` (`too_short`, `replay`, `simulated`, `imported` ou `null`), `gains` (liste de `{source, points}` dans l'ordre du plan §2.1 : `distance`, `climb`, `erg`, `erg_bonus`, `segment`, `segment_pr`, `jersey`, `rogue`, `rogue_boss`), `total`, `level_before`, `level_after`, `xp_total`, `xp_next_level`, `coins_gained`, `coins_total`, `unlocked` (identifiants d'équipement devenus achetables), `challenges` (défis réussis dans la séance : `{id, name, reward_item}`), `equipment_gain_s` (temps gagné ou perdu par l'équipement sur la séance, négatif si gagné, ou `null`).

Taille : 1 400 octets au plus, cible commune des messages courts (au plus 8 déblocages et 4 défis listés, `more` vrai au-delà).

#### Commandes et catalogue du Garage

| `name` | `args` | Effet |
| --- | --- | --- |
| `list_garage` | `{}` | Demande le catalogue ; réponse `garage` en parties, comme `routes` |
| `equip` | `{ "slot": chaîne, "item_id": chaîne }` | Choisit une pièce possédée ; `error` `item_locked` sinon |
| `buy` | `{ "item_id": chaîne }` | Achète une pièce débloquée ; `error` `not_enough_coins` ou `item_locked` |
| `set_avatar` | `{ "avatar": objet }` | Remplace les réglages de l'avatar (§4.4) ; valeurs hors bornes : `error` `avatar_invalid` |

- Hors séance seulement (`IDLE`, `READY`) : sinon `error` `busy` (code existant).
- Après `equip`, `buy` ou `set_avatar` réussi, le core envoie un message dédié `progression` (`v`, `request_cmd_id` et les champs de l'objet du §4.1) : l'engine n'a pas à recalculer. Pas de nouveau `hello_ack`, que l'engine traite comme la fin de la poignée de main (décision D7 de l'audit IPC).
- Message `garage` : `v`, `request_cmd_id`, `part`, `parts`, `items`. Élément : `id`, `slot`, `name`, `state` (`locked`, `buyable`, `owned`, `equipped`), `level_required`, `price`, `challenge` (texte du défi qui l'offre, ou `null`), `mass_delta_kg`, `cda_delta_pct`, `terrain` (`flat`, `rolling`, `climb`, `all`), `look` (identifiant de rendu pour V7).
- Nouveaux codes d'erreur : `item_locked`, `not_enough_coins`, `avatar_invalid`.
- Élément de `routes` : champ facultatif `terrain` (`flat`, `rolling`, `climb` ou `null`, calculé par le core, lot V3 §4.3) pour le conseil d'équipement de l'écran « Prêt » (V8).

#### Avatar

Objet `avatar` : `height` (`S`, `M`, `L`, `XL`), `build` (`slim`, `medium`, `strong`), `skin` (indice 0 à 7 d'une palette fixe), `hair` (style 0 à 5), `hair_color` (0 à 7), `kit_primary`, `kit_secondary` (indices 0 à 15 d'une palette fixe), `number` (entier 0 à 999), et deux seuils de la position en danseuse lus dans `[avatar]` de `config.toml` (lot V6) : `standing_grade_pct` (pente, 8 par défaut) et `standing_power_pct` (% de la FTP, 150 par défaut), transmis dans `hello_ack` mais non modifiables par `set_avatar`. Choix par listes et palettes : tout se règle au Click. Aucune mesure réelle (taille, masse) du cycliste n'y figure.


## 5. Fichiers concernés

- **Modifiés :** `docs/contracts/ipc_v1.md`, `docs/contracts/world_format_v1.md`, `docs/contracts/ipc/state.schema.json`, `cmd.schema.json`, `hello_ack.schema.json`, `error.schema.json`, `routes.schema.json`, `docs/contracts/world/manifest.schema.json`, `core/src/openride_core/ipc_budget.py` (révision 1.4), `core/tests/test_contract_ipc.py`, `docs/SPECIFICATION_GENERALE.md` (§6.1, §6.2), `docs/SRS_v1.1.md` (§11 : sections `[rogue]`, `[avatar]`), `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Créés :** schémas `segment_result`, `room`, `loot`, `garage`, `progression`, `xp_result` dans `docs/contracts/ipc/` ; `segments.schema.json` dans `docs/contracts/world/`.
- **Interdits :** le code du core et de l'engine hors tests de contrat et outil `ipc_budget` (les lots R8, T5 à T15, V11 et suivants branchent).

## 6. Modifications de contrat autorisées

Les ajouts du §4, tous compatibles (`v` reste 1), sous une seule révision 1.4.

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe, dont `test_docs_coherence.py` (schémas valides) et `test_contract_ipc.py`.
2. Trames d'exemple valides pour chaque ajout : `state` classique avec `segment`, `powerup`, `jerseys` et 5 bots à profil ; `state` en mode `ROGUE` ; `segment_result`, `room`, `loot`, `garage`, `progression`, `xp_result`, `start_run`, `rogue_resync`, `list_garage`, `equip`, `buy`, `set_avatar` ; `hello_ack` avec et sans `rogue` et `progression` ; une trame de la 1.0 reste valide.
3. `ipc_budget` donne la pire trame 1.4 de chaque mode sous 4 096 octets et les messages courts sous 1 400.
4. Une couche `segments.json` d'exemple est valide ; un `.world` sans cette couche reste lisible.
5. Le propriétaire valide le contrat.

## 8. Hors périmètre

- Monde ouvert (W1, révision 1.5) et biomes (U1, révision suivante).
- Vues de caméra (décision D5 en attente) : l'engine change de vue lui-même sur `A_SHORT`, sans ajout au contrat.
- Le calcul et le branchement (R2 à R9, T3 à T16, V2 à V11) et l'affichage.

## 9. Livraison (27 octobre 2026, PR #392)

- Contrat : `docs/contracts/ipc_v1.md` révision 1.4 (mode `ROGUE`, objets `segment`, `powerup`, `jerseys`, bots à profil, messages `segment_result`, `room`, `loot`, `garage`, `progression`, `xp_result`, commandes de run et du Garage) ; format `.world` 1.3 avec la couche `segments` (`docs/contracts/world_format_v1.md`).
- Schémas : six nouveaux messages (`garage`, `loot`, `progression`, `room`, `segment_result`, `xp_result`), `state`, `cmd`, `error`, `hello_ack` et `routes` complétés ; `world/segments.schema.json` et manifeste.
- `ipc_budget.py` mesure les pires trames 1.4 : 2 456 octets en classique, 1 543 en run, sous 4 096 ; messages courts sous 1 400.
- Tests : `core/tests/test_contract_ipc.py` (trames d'exemple de chaque ajout) et `core/tests/test_ipc_budget.py`.
- Contrat validé par le propriétaire le 27 octobre (critère 5). Le core annonce encore `rev` « 1.3 » jusqu'au branchement (R8, T7, V11).
