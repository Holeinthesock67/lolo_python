# OpenRide Linux – Contrat IPC v1

21 octobre 2026, révision 1.1 du 24 octobre 2026, révision 1.2 du 25 octobre 2026, révision 1.3 du 26 octobre 2026, révision 1.4 du 27 octobre 2026, révision 1.5 du monde ouvert (lot W1) du 27 octobre 2026 (ajouts compatibles, `v` reste 1)

## 1. Objet, principes et conventions

Ce contrat fixe les messages échangés en direct entre openride-core (Python) et openride-engine (Godot) pendant une séance. Il est la référence commune : aucun des deux programmes ne doit faire d'hypothèse qui n'y figure pas.

**Principes**

- Le core est le maître : il détient l'état de la séance ; l'engine affiche et envoie des demandes.
- Un message = un objet JSON UTF-8 dans un datagramme UDP.
- Les champs inconnus sont ignorés ; un champ absent vaut `null`.
- Les noms de champs sont en anglais, en `snake_case`.

**Unités (obligatoires)**

| Grandeur | Unité | Type |
| --- | --- | --- |
| Distance, altitude, position | mètre | nombre |
| Vitesse | mètre par seconde | nombre |
| Pente | pour cent, positif en montée | nombre |
| Puissance | watt | nombre |
| Cadence | tours par minute | nombre |
| Fréquence cardiaque | battements par minute | entier ou `null` |
| Temps, durée | seconde | nombre |
| Latitude, longitude | degrés décimaux WGS84 | nombre |
| Cap | degrés dans le sens horaire depuis le nord | nombre |

**Champs communs à tout message :** `type` (chaîne), `v` (version majeure du contrat, ici 1) et, pour les messages périodiques, `seq` (entier croissant propre à chaque émetteur, remis à 0 au démarrage).

**Exception connue :** dans le message `state`, le champ `v` est la vitesse virtuelle (§3), pas la version : les deux noms se recouvrent et la vitesse l'emporte. La version est vérifiée par `hello` et `hello_ack` (§5), ce qui suffit. Le renommage de la vitesse en `speed` est prévu pour la version 2 du contrat.

## 2. Transport : UDP localhost, ports, fréquences

Deux sockets UDP non bloquantes sur `127.0.0.1`, sans connexion : chaque programme écoute sur son port et envoie vers l'autre.

| Sens | Port par défaut | Contenu | Fréquence |
| --- | --- | --- | --- |
| core vers engine | 5005 | `state`, `input`, `hello_ack`, `error`, `shutdown`, `routes`, `workouts`, `settings`, `imports`, `workout_saved`, `plans` ; depuis la révision 1.4 : `segment_result`, `room`, `loot`, `garage`, `progression`, `xp_result` ; depuis la révision 1.5 (monde ouvert) : `world_status`, `places`, `world_map`, `world_regions` ; `wtf_rules`, `profiles`, `contents` (lot O25) | `state` à 30 Hz ; le reste sur événement |
| engine vers core | 5006 | `hello`, `heartbeat`, `cmd`, `bye` | `heartbeat` à 2 Hz ; `cmd` sur événement |

- Les ports sont modifiables dans `config.toml` (section `ipc`) ; si un port est occupé, le programme s'arrête avec un message explicite.
- Encodage : JSON compact en UTF-8, caractères accentués écrits tels quels (sans échappement `\u`) ; un lecteur JSON standard lit les deux formes.
- Taille maximale d'un datagramme : 4 096 octets pour tout message, dans les deux sens, depuis la révision 1.5 (décision du propriétaire du 27 octobre : une seule limite ; jusqu'à la révision 1.4, 1 400 octets, et 4 096 pour `state` depuis la 1.3, décision D1 de l'audit IPC du 26 octobre). Seuls les messages en parties (`part` et `parts`) vont au-delà : `routes`, `workouts` et, depuis la révision 1.3, `imports` (§4), `plans` (révision 1.3, lot O12, un seul datagramme), depuis la révision 1.4, `garage` et `room` (§4) et, depuis la révision 1.5 en monde ouvert, `places`, `world_map` et `world_regions` (§4), puis `settings` (30 octobre, révision 1.5, un seul datagramme : la liste des réglages et des thèmes installés passait les 4 096 octets) et `contents` (31 octobre, révision 1.5, lot O25, un seul datagramme : les thèmes et les packs du lot O29 s'y ajoutent), 60 000 octets par partie. Ces messages restent sur `127.0.0.1`, où un datagramme de cette taille passe sans fragmentation ; l'engine lit sa socket avec un tampon d'au moins 65 536 octets. Un engine antérieur lit donc déjà ces messages : le changement est compatible. Le core allège une trame `state` qui dépasse la limite (§3, liste `bots`, lot X25) ; il jette, avec un avertissement, tout autre message trop grand. Les cibles de 1 400 octets citées plus bas (§3, messages courts) gardent de la place pour les ajouts ; ce ne sont pas des limites.
- Un datagramme illisible (JSON invalide) est ignoré et compté dans les journaux.
- Le trainer notifie à environ 1 Hz (mode puissance) à 8 Hz (mode pente), mesuré ; la fréquence de 30 Hz du message `state` est indépendante et vient de la physique du core (50 Hz).

## 3. Message core vers engine : état de séance

`type: "state"`, envoyé à 30 Hz en continu, y compris hors séance. L'engine ne garde que le message au `seq` le plus élevé reçu.

| Champ | Type | Description |
| --- | --- | --- |
| `seq` | entier | Numéro croissant des trames d'état |
| `t` | nombre | Temps de séance en secondes (horloge du core, arrêtée en pause) |
| `session_state` | chaîne | `IDLE`, `LOADING`, `READY`, `RUNNING`, `PAUSED`, `FINISHED`, `ERROR` |
| `pause_reason` | chaîne ou `null` | `user`, `trainer_lost`, `engine_lost`, `recording_failed`, `core_restarted`, `world_data` (§6) quand `session_state` vaut `PAUSED` |
| `trainer_status` | chaîne | `CONNECTED`, `RECONNECTING`, `LOST`, `MOCK` |
| `input_status` | chaîne | `CONNECTED`, `LOST`, `KEYBOARD` |
| `mode` | chaîne | `SIM` ou `ERG` ; `ROGUE` depuis la révision 1.4 (série R, voir l'objet `rogue`) |
| `route_id` | chaîne ou `null` | Nom du `.world` chargé ; l'engine en déduit le dossier |
| `route_length_m` | nombre ou `null` | Longueur de la route |
| `s` | nombre | Position le long de la route, en mètres |
| `v` | nombre | Vitesse virtuelle |
| `grade` | nombre | Pente réelle du terrain à `s` |
| `grade_sent` | nombre | Pente effective envoyée au trainer |
| `difficulty_pct` | entier | Difficulté du trainer appliquée (0 à 100 %, défaut 50) |
| `power` | nombre | Puissance mesurée, lissage court |
| `power_3s` | nombre | Puissance moyennée sur 3 s |
| `cadence` | nombre | Cadence |
| `hr` | entier ou `null` | Fréquence cardiaque |
| `gear` | entier | Vitesse virtuelle `k` (1 à 24) |
| `gears_total` | entier | Nombre de vitesses |
| `lat`, `lon`, `alt` | nombres | Position géographique correspondant à `s` ; `null` en mode `ROGUE` (révision 1.4) |
| `erg` | objet ou `null` | Présent en mode ERG, voir ci-dessous |
| `summary` | objet ou `null` | Présent quand `session_state` vaut `FINISHED` (ou `ERROR` après une séance) : `duration_s` (temps chronométré), `distance_m`, `avg_power_w`, `fit_path` (`null` si aucun FIT n'a été produit) ; champs facultatifs du bilan enrichi ci-dessous |
| `devices` | objet, facultatif | État détaillé des appareils, voir ci-dessous ; envoyé une trame sur 30 (une fois par seconde) et dans la trame qui suit un changement, absent des autres trames |
| `bots` | liste, facultatif | Concurrents virtuels, voir ci-dessous |
| `wind` | objet, facultatif | Révision 1.3 : vent ressenti au point `s`, voir ci-dessous ; envoyé 2 fois par seconde (une trame sur quinze, jamais avec `devices`) et absent quand le vent est coupé |
| `draft` | nombre, facultatif | Révision 1.3 : coefficient d'aspiration appliqué au cycliste, de 0 à 0,45 (SRS §5) ; absent sans bot |
| `draft_bot` | chaîne, facultatif | Révision 1.3 : `id` du bot qui abrite le cycliste ; absent quand `draft` vaut 0 ou manque |
| `open_world` | objet, facultatif | Monde ouvert seulement : révision du monde, prochain carrefour, état des données (§4, « Monde ouvert ») |
| `last_cmd_id` | entier | Dernier `cmd_id` traité par le core (§4) |

**Objet `erg`**

| Champ | Type | Description |
| --- | --- | --- |
| `workout_name` | chaîne | Nom de l'entraînement |
| `block_index`, `block_count` | entiers | Bloc en cours et nombre total, en comptant à partir de 1 |
| `block_type` | chaîne | `warmup`, `steady`, `interval_on`, `interval_off`, `ramp`, `cooldown` ; plus de `freeride` depuis le lot O19 (29 octobre) : un entraînement ERG n'a jamais de roue libre, un bloc FreeRide d'un `.zwo` arrive en `steady` à 50 W |
| `block_remaining_s`, `block_total_s` | nombres | Temps restant et durée du bloc |
| `target_w` | nombre | Cible de puissance en cours, biais inclus, jamais sous 50 W (lot O19) |
| `next_target_w` | nombre ou `null` | Cible du bloc suivant |
| `bias_pct` | nombre | Biais d'intensité (80 à 120) |
| `paused` | booléen | ERG en pause : séance en pause (Y), seule pause depuis le lot O17 |
| `kind` | chaîne, facultatif | Révision 1.5 (lot O18) : `workout` (entraînement), `free` (ERG libre d'une session libre) ou `cadence` (ERG à cadence verrouillée) ; absent : `workout` |
| `cadence_target_rpm` | entier, facultatif | `cadence` seulement : cadence cible, biais compris (`bias_pct` s'applique à la cadence, pas à la puissance) |
| `cadence_low_rpm`, `cadence_high_rpm` | nombres, facultatifs | `cadence` seulement : bornes de la plage (cible ± 15 %) |
| `cadence_zone` | chaîne, facultatif | `cadence` seulement : `low` (sous la plage, la puissance baisse), `in`, `high` (au-dessus, la puissance monte) |

ERG d'une session libre (`free`, `cadence`, lot O18) : un seul bloc `steady` sans durée (`block_index` = `block_count` = 1, `block_remaining_s` = `block_total_s` = 0, `next_target_w` = `null`) ; `mode` vaut `ERG`.

**Bilan enrichi (champs facultatifs de `summary`)**

Mêmes définitions que `openride-core summary` (lot K7). Chaque champ vaut `null` quand la donnée manque (pas de cardio, pas de cadence, séance trop courte).

| Champ | Type | Description |
| --- | --- | --- |
| `np_w` | nombre ou `null` | Puissance normalisée |
| `intensity_factor` | nombre ou `null` | NP divisée par la FTP (par exemple 0,85) |
| `tss` | nombre ou `null` | Training Stress Score |
| `elevation_gain_m` | nombre ou `null` | Dénivelé positif |
| `avg_cadence_rpm` | nombre ou `null` | Cadence moyenne en roulant |
| `avg_hr_bpm` | nombre ou `null` | Fréquence cardiaque moyenne |
| `max_power_w` | nombre ou `null` | Puissance maximale |
| `blocks` | liste ou `null` | En ERG seulement : au plus 24 triplets `[index, puissance moyenne, cible moyenne ou null]`, index compté à partir de 1 ; au-delà, les premiers 24 et `blocks_truncated` vrai |
| `blocks_truncated` | booléen | Vrai si `blocks` a été coupé |

**Objet `devices`**

| Clé | Contenu |
| --- | --- |
| `trainer` | `{status, name, address, busy}` : `status` reprend `trainer_status` ; `name` (nom annoncé) et `address` sont des chaînes ou `null` ; `busy` (booléen, facultatif, révision 1.5) est vrai quand le Control Point refuse les consignes parce qu'il est occupé (ATT 0x80 ou 0xFE, autre appareil sur le trainer, une montre par exemple) : liaison gardée, consigne réessayée, l'engine affiche « Trainer piloté par un autre appareil » |
| `click` | Liste de `{side, status, battery_pct}` : `side` vaut `plus`, `minus` ou `single` ; `status` vaut `CONNECTED`, `SEARCHING` ou `LOST` ; `battery_pct` est un entier de 0 à 100 ou `null`. Liste vide sans Click configuré |
| `hr` | `{status, source, battery_pct}` : `status` vaut `CONNECTED`, `SEARCHING`, `LOST` ou `NONE` ; `source` vaut `strap`, `trainer` ou `null` |

`trainer_status` et `input_status` restent présents dans toutes les trames et gardent leur sens : un lecteur qui ignore `devices` fonctionne comme en v1. L'engine garde le dernier objet `devices` reçu jusqu'au suivant.

**Liste `bots`**

Au plus 5 éléments `{id, name, s, v, kind}` (4 bots à puissance constante et un fantôme), pour que la trame la plus chargée (ERG, `devices` et bots) reste petite (1 400 octets jusqu'à la révision 1.2, 4 096 octets depuis la 1.3, §2) : `id` (au plus 8 caractères) et `name` (au plus 16 caractères) sont des chaînes, `s` et `v` des nombres (mêmes unités que la trame), `kind` vaut `constant` (puissance fixe) ou `ghost` (rejeu d'une séance passée, lot N9). Champ absent quand il n'y a pas de bot. Si une trame `state` dépasse malgré tout sa limite (mesure du 26 octobre, lot X25, `python -m openride_core.ipc_budget` : avec les longueurs maximales, la trame qui porte `devices` peut dépasser 1 400 octets), le core l'allège au lieu de la jeter, dans cet ordre : textes raccourcis, noms des bots raccourcis, `bots` retiré de cette trame-là seulement (ils reviennent dans la trame suivante, 33 ms plus tard), puis `devices`, `summary`, `bots`, `erg`. Position, vitesse, puissance et état de séance restent toujours. Un avertissement au plus toutes les 10 s au journal du core.

**Objet `wind` (révision 1.3, lot P1)**

| Champ | Type | Description |
| --- | --- | --- |
| `speed_mps` | nombre ≥ 0 | Vitesse du vent au sol, rafale comprise |
| `from_deg` | nombre, 0 à 360 | Direction d'où vient le vent, en degrés dans le sens horaire depuis le nord (même convention que le cap, `world_format_v1.md` §3) |
| `head_mps` | nombre | Composante de face le long du cap de la route à `s` : positive de face, négative de dos. C'est celle qu'utilise la physique |
| `gust` | nombre, 0 à 1 | Force de la rafale en cours, pour l'animation (arbres, drapeaux, son) |

- Arrondis à l'envoi : `speed_mps` et `head_mps` au centième, `from_deg` au dixième, `gust` au centième, `draft` au millième (comme `s` et `v` des bots, au centième et au millième).
- La physique du core utilise le vent exact à 50 Hz ; l'engine lisse les valeurs reçues 2 fois par seconde. Entre deux envois, l'engine garde le dernier objet `wind` reçu ; s'il n'en reçoit plus pendant 2 s, le vent est considéré comme coupé.
- L'indicateur du vent du HUD (favorable, défavorable ou neutre, et son intensité) se déduit de ces champs : le verdict du signe de `head_mps` (seuil ± 1 m/s), l'intensité de `speed_mps`. Aucun champ de plus.
- Le vent est coupé par défaut dans les versions 1.x (`[wind] mode = "off"`, SRS §11) : l'objet `wind` est alors absent et les trames restent celles de la révision 1.2.
- En ERG, le vent et l'aspiration ne changent que la vitesse virtuelle, jamais la puissance demandée. Le fantôme (`kind` = `ghost`) n'abrite pas : `draft_bot` désigne toujours un bot `constant`.
- `wind` n'est jamais dans la même trame que `devices` : quand les deux tombent ensemble, le core envoie `wind` dans la trame suivante. Les deux trames les plus chargées (ERG, 5 bots, `draft` et `draft_bot`, avec soit `devices`, soit `wind`) restent ainsi sous 1 400 octets, bien en dessous de la limite de 4 096 octets de la révision 1.3 (§2), ce qui laisse la place aux ajouts de la 2.0 ; un test du core le vérifie.

**Segments, bonus, maillots et voisins (révision 1.4, série T, lot T1)**

Champs facultatifs de `state`, absents quand le parcours n'a pas de segment, qu'il n'y a pas de bot, ou qu'un engine plus ancien les ignorerait sans gêne :

| Champ | Type | Sens |
| --- | --- | --- |
| `segment` | objet, facultatif | Segment en cours ou prochain : `id`, `kind` (`sprint` ou `climb`), `category` (`4` à `HC`, `null` pour un sprint), `d_to_start_m` (0 dans le segment), `elapsed_s` (`null` avant le départ), `gap_to_pr_s` (écart au record, négatif si en avance, ou `null`). Le nom et les bornes sont dans la couche `segments` du `.world` (format §2), que l'engine lit lui-même |
| `powerup` | objet, facultatif | Bonus : `held` (en réserve : `light`, `aero`, `power` ou `null`), `active` (bonus actif ou `null`), `remaining_s` ; absent en ERG (décision T-Q2) |
| `jerseys` | objet, facultatif | Détenteurs des maillots pendant la séance : `sprint` (vert) et `kom` (à pois), chacun `"me"`, un `id` de bot ou `null` (T14) |
| `bot_ahead`, `bot_behind` | chaîne ou `null`, facultatifs | `id` des voisins immédiats, devant et derrière (T16) ; `null` : la ligne disparaît du HUD |

Chaque élément de `bots` gagne, facultatifs : `profile` (`climber`, `rouleur`, `sprinter`, `diesel`, ou `null` pour un bot à puissance constante), `cp_w`, `mass_kg`, `wbal_pct` (réserve W′ restante, 0 à 100), `jersey` (`sprint`, `kom` ou `null`) et `gap_s` (écart en temps de passage, positif si le bot est devant). Le sens de chaque bouton dans chaque mode est celui du tableau de la spécification générale §7.1 ; la révision 1.4 n'ajoute aucun événement de bouton.

**Objet `rogue` (révision 1.4, série R, lot T1)**

En mode `ROGUE` : `route_id`, `lat`, `lon` et `alt` valent `null` ; `route_length_m` est la longueur de la salle en cours ; `s` la distance depuis le début de la run ; `grade` la pente de l'ennemi après cartes ; `grade_sent` la pente envoyée (formule centrée du lot Q2) ; `gear` va de 1 à 12 et `gears_total` vaut 12. L'objet `rogue` est présent dans chaque trame de ce mode, et seulement dans ce mode :

| Champ | Type | Sens |
| --- | --- | --- |
| `phase` | chaîne | `WARMUP`, `ROOM`, `CORRIDOR`, `BOSS`, `RECOVERY`, `COOLDOWN`, `RESULTS` |
| `room_id` | entier | Numéro de la salle, le même que dans le message `room` ; change à chaque salle |
| `room_index`, `rooms_total` | entiers | Salle en cours (à partir de 1) et nombre prévu |
| `archetype` | chaîne ou `null` | `diesel`, `puncheur`, `grimpeur`, `sprinteur`, `saboteur`, `boss` |
| `boss_phase` | entier ou `null` | 1 à 3 |
| `s_room` | nombre | Distance dans la salle (m) |
| `enemy_hp`, `enemy_hp_max` | nombres | Points de vie de l'ennemi |
| `shield`, `shield_max`, `adrenaline` | nombres | Bouclier (0 à `shield_max`, 100 sans bonus) et adrénaline (0 à 100) |
| `w_bal_j`, `w_prime_j` | nombres | Réserve anaérobie et sa capacité (J) |
| `posture` | chaîne | `ROC`, `FLUIDE`, `VELOCE`, `ARRET` |
| `firewall_gap_m` | nombre | Avance sur le Firewall (négatif : rattrapé) |
| `gold` | entier | Or de la run |
| `windows` | liste | Fenêtres actives, au plus 4 : `{kind, s_start, s_end}`, `kind` parmi `arch`, `strike_target`, `parry_zone`, `pad`, `purge`, `tunnel` |
| `hack` | objet ou `null` | Piratage du Saboteur : `{locked, forced_gear, until_s}` |
| `overheat` | booléen | Surchauffe (objectif endurance, décision Q3) |
| `loot_focus` | entier ou `null` | En couloir : carte ou porte sélectionnée (0 à 4) |
| `events` | liste | Événements de jeu de la dernière trame, au plus 4 : `perfect_shift`, `hit`, `crit`, `parry`, `parry_miss`, `firewall_contact`, `room_won`, `room_fled`, `room_skipped`, `defeat`, `card_taken` |

L'engine qui voit dans `state.rogue` un `room_id` ou un couloir dont il n'a pas reçu le message envoie `rogue_resync` (§4), au plus une fois par seconde.

**Bilan d'un test de FTP (révision 1.3, lot O12).** `summary` gagne l'objet facultatif `ftp_test` après une séance de test de FTP : voir « Plans d'entraînement et test de FTP depuis le menu » au §4.

**Objet `wtf` (révision 1.5, lot WTF2, mode « What the fuck »)**

Présent dans chaque trame d'une séance lancée par `start` avec `mode` = `wtf`, et seulement là ; `mode` reste `SIM` (le mode WTF refuse l'ERG). `grade` est la pente **transformée** par la règle en cours (Lune, Jupiter, monde à l'envers, spaghetti) ; le journal garde la pente du parcours. Champs (plan `docs/2.0/PLAN_SERIE_WTF.md` §5) : `points` (entier) ; `event` (`null` ou `{id, left_s, …}`, `id` parmi `gravity`, `upside_down`, `collapse`, `cheese`, `micro`, `eggs`, `tiny`, `storm`, `camera`, `chef`, avec les champs propres à l'événement : `planet` et `hop_m` ; `gap_m` ; `squashed` ; `kind`, `target`, `round`, `round_left_s`, `results`, `progress` ; `eggs` et `left_m` ; `scale` et `set` ; `pushback_m` et `cows` ; `view` ; `phase`, `dish`, `phase_left_s`, `tempo_rpm`, `souffle`, `burning`) ; `next_s` (secondes avant le prochain événement, quand il n'y en a pas) ; et, selon les règles actives, `kata` (`size`, `count`, `last`, `next` : liste de `[distance_m, objet]`), `skins` (bot → `grandma`, `tractor`, `bathtub` ou `whale`) et `attack` (bot qui attaque ou `null`), `clock_h` et `fish`. Les clés d'une règle coupée sont absentes. `summary.wtf` : `points`, `events` (nombre de fois par règle), `kata_size`, `kata_count`.

**Bilan 1.4.** `summary` gagne deux objets facultatifs. `segments` (série T) : `passes` (les 10 derniers passages de la séance : `segment_id`, `kind`, `time_s`, `with_powerup`, `pr`, `rank`, `rank_total`, `points`), `more` (vrai s'il y en a eu davantage) et `jerseys` (détenteurs à la fin, même forme que dans `state`). `rogue` (série R) : `result` (`victory`, `defeat` ou `abandoned`), `objective`, `duration_min`, `seed`, `rooms_won`, `rooms_fled`, `rooms_skipped`, `rooms_total`, `defeats`, `boss` (`won`, `fled` ou `not_reached`), `gold`, `cards` (identifiants), `perfect_shifts`, `unlocks` (identifiants). Le bilan de progression de la série V est le message `xp_result` ci-dessous.

**Messages de jeu (révision 1.4, core vers engine, sur événement)**

| Message | Contenu | Envoi |
| --- | --- | --- |
| `segment_result` | `v`, `segment_id`, `name`, `kind`, `time_s`, `with_powerup` (table des records « avec » ou « sans » bonus, T-Q1), `pr`, `pr_time_s` (ancien record ou `null`), `rank`, `rank_total` (classement local avec bots et fantôme, T5), `points` (points de maillot gagnés, T14), `equipment_gain_s` (temps gagné, négatif, ou perdu par l'équipement sur le passage, ou `null`, série V) | À la fin de chaque passage, répété 3 fois à une seconde d'intervalle avec le même `segment_id` ; l'engine ignore les doublons |
| `room` | `v`, `room_id`, `part`, `parts`, `archetype`, `variant`, `length_m`, `nominal_s`, `profile` (pente tous les 10 m : liste de `[s_m, grade_pct]`, au plus 1 500 points), `markers` (liste de `{kind, s_m, len_m, param}`, `kind` parmi `arch`, `strike_target`, `parry_zone`, `pad`, `purge`, `tunnel`, `rock`, `shockwave`), `next` (`room_id` et `archetype` de la salle suivante si elle est connue, sinon `null`) | Au début de chaque salle et, en couloir, pour chacune des deux portes ; parties de 60 000 octets comme `routes` |
| `loot` | `v`, `corridor_id`, `cards` (3 cartes `{id, name, kind, text, replaces_gear}`), `doors` (2 portes `{side, room_id, archetype}`, `side` = `left` ou `right`), `reroll_cost`, `gold` | À l'entrée du couloir et après chaque relance |
| `xp_result` | `v`, `eligible`, `reason` (`too_short`, `replay`, `simulated`, `imported` ou `null`), `gains` (liste de `{source, points}` dans l'ordre `distance`, `climb`, `erg`, `erg_bonus`, `segment`, `segment_pr`, `jersey`, `rogue`, `rogue_boss`), `total`, `level_before`, `level_after`, `xp_total`, `xp_next_level`, `coins_gained`, `coins_total`, `unlocked` (au plus 8 identifiants d'équipement devenus achetables), `challenges` (au plus 4 défis réussis `{id, name, reward_item}`), `equipment_gain_s`, `more` (vrai au-delà de 8 déblocages ou 4 défis) | Quand `session_state` passe à `FINISHED`, après le `summary`, puis une fois par seconde tant que la séance reste `FINISHED` (au plus 10 fois) : une perte UDP ne fait pas disparaître le bilan (décision D7 de l'audit IPC) |
| `wtf_rules` | `v`, `rules` (13 éléments `{id, label, family, pitch, on}`, `family` = `event` ou `ambient`) | Révision 1.5 (lot WTF2) : réponse à `list_wtf_rules` et à `set_wtf_rule` |

Tailles mesurées par `python -m openride_core.ipc_budget` avec les longueurs maximales (27 octobre) : pire trame `state` classique ou ERG de la révision 1.4 (5 bots à profil, `segment`, `powerup`, `jerseys`, `devices`) 2 456 octets ; pire trame `ROGUE` (4 fenêtres, 4 événements, `devices`) 1 543 octets ; toutes deux sous la limite de 4 096 octets, sans allègement. Messages courts, cible 1 400 octets : `segment_result` 297, `xp_result` 1 357, `progression` 572, `loot` 1 168.

## 4. Message engine vers core : commandes

`type: "cmd"`, envoyé sur événement. L'UDP peut perdre ou dupliquer un datagramme, donc chaque commande porte un `cmd_id` entier croissant propre à l'engine.

**Fiabilité.** L'engine renvoie la commande toutes les 200 ms jusqu'à voir son `cmd_id` dans le champ `last_cmd_id` du message `state` (abandon après 3 s avec un message d'erreur à l'écran). Le core ignore un `cmd_id` déjà traité : toutes les commandes sont donc idempotentes. Le compteur `cmd_id` est propre à une instance de l'engine : le core remet `last_cmd_id` à 0 à chaque `hello`, si bien qu'un engine relancé peut renuméroter ses commandes à partir de 1.

| `name` | `args` | Effet |
| --- | --- | --- |
| `select_route` | `{ "route_id": chaîne }` | Charge le parcours ; `session_state` passe à `LOADING` puis `READY` |
| `select_workout` | `{ "workout_id": chaîne ou null }` | Choisit un entraînement (mode ERG) ; `null` revient au mode SIM |
| `start` | `{}` ; révision 1.3 (lot O12) : `{ "ftp_test": "ramp" }` (le test `20min` est retiré au lot O19) ou `{ "plan_day": true }` ; lot O7 : `bots`, facultatif, avec l'un ou l'autre | Démarre la séance (`READY` vers `RUNNING`). Avec `ftp_test`, choisit d'abord l'entraînement `ftp_test:<test>` (test de FTP, lot O10) ; avec `plan_day`, la séance du jour du plan actif (`plans.active.plan_day`), `error` `plan_invalid` s'il n'y en a pas. Entraînement refusé : `error` `workout_invalid` et rien ne démarre ; `ftp_test` inconnu : `bad_args`. Avec `bots` (lot O7, révision 1.3) : liste qui remplace les bots de la séance (sans `bots`, la séance a ceux de la ligne de commande `--bot` et `--ghost` ; une liste vide les retire), au plus 4 `{ "kind": "constant", "power_w": nombre }` ou `{ "kind": "constant", "ftp_pct": nombre }` (puissance en % de la FTP du core) et un `{ "kind": "ghost" }` (fantôme de la dernière séance enregistrée sur ce parcours) ; révision 1.5, lot T12 : `{ "kind": "profile", "profile": "climber" }` (`climber`, `rouleur`, `sprinter` ou `diesel`), compté dans les 4 bots avec les bots constants ; lot T13 : `level_pct` facultatif (50 à 150, % de la FTP du core ; sans lui, le réglage `bots.level_pct`), le core calibrant la CP du bot au départ pour qu'il finisse le parcours dans le temps d'un cycliste roulant à ce niveau ; `kind` = `constant` et champs de profil dans la trame ; bots recréés au départ, à la position du cycliste ; liste refusée ou aucune séance pour le fantôme : `error` `bot_invalid` et rien ne démarre. Révision 1.5 (lot WTF2) : `mode` facultatif, `ride` (défaut) ou `wtf` (mode « What the fuck », objet `wtf` de `state`, sans segments, records ni bonus) ; `wtf` avec un entraînement ERG choisi, ou `mode` inconnu : `bad_args` |
| `pause` | `{}` | Met en pause (`pause_reason` = `user`) |
| `resume` | `{}` | Reprend après une pause, quelle qu'en soit la raison |
| `end_session` | `{ "save": booléen }` | Termine ; avec `save` vrai, produit le FIT puis passe à `FINISHED` |
| `input_event` | `{ "event": chaîne }` | Touches lues par l'engine, même effet qu'un appui sur le Click (`PLUS_SHORT`, `MINUS_SHORT`, …) |
| `skip_block` | `{}` | Bloc suivant en ERG, comme Z court au Click (spécification générale §7.1) ; pour le menu ou un outil |
| `list_routes` | `{}` | Demande la liste des parcours ; réponse `routes` |
| `list_workouts` | `{}` | Demande la liste des entraînements ; réponse `workouts` |
| `set_difficulty` | `{ "pct": nombre }` | Change la difficulté du trainer (0 à 100) pour la séance en cours ; la valeur est aussi écrite dans `config.toml` (`trainer.difficulty_pct`) et sert de départ à la séance suivante |
| `scan_devices` | `{ "timeout_s": nombre }` (8 par défaut, 1 à 30) | Révision 1.2 : recherche des appareils Bluetooth ; réponses `scan_results` |
| `identify_click_plus` | `{}` | Révision 1.2 : attend un appui « + » du Click pendant 15 s ; réponse `scan_results` avec `plus_address` |
| `pair_devices` | `{ "trainer", "click_plus", "click_minus", "hr" }` : adresse ou `null` | Révision 1.2 : écrit les appareils choisis dans `config.toml` ; `error` `pairing_failed` en cas d'échec |
| `list_settings` | `{}` | Révision 1.3 : demande les réglages du menu ; réponse `settings` |
| `set_setting` | `{ "key": texte, "value": nombre ou texte }` | Révision 1.3 : écrit un réglage dans `config.toml` ; réponse `settings`, ou `error` `busy` / `setting_invalid` |
| `list_imports` | `{}` | Révision 1.3 : fichiers d'entraînement importables ; réponse `imports` |
| `list_plans` | `{}` | Révision 1.3 (lot O12) : plans d'entraînement et suivi du plan actif ; réponse `plans` |
| `start_plan` | `{ "id": chaîne, "start_date": "AAAA-MM-JJ" ou null }` | Révision 1.3 (lot O12) : rend le plan actif (début : aujourd'hui si `null`) ; réponse `plans` ; plan inconnu, invalide ou date mal écrite : `error` `plan_invalid` |
| `stop_plan` | `{}` | Révision 1.3 (lot O12) : arrête le plan actif ; réponse `plans` |
| `accept_ftp` | `{ "force": booléen }` (facultatif) | Révision 1.3 (lot O12) : écrit la FTP du dernier test (`summary.ftp_test`) dans `config.toml` comme `set_setting` `rider.ftp_w` ; réponse `settings` |
| `create_workout` | `{ "warmup_min", "reps", "on_s", "on_pct", "off_s", "off_pct", "cooldown_min" }` : entiers | Révision 1.3 : le core écrit un entraînement par intervalles ; réponse `workout_saved` |
| `import_workout` | `{ "path": chaîne }` | Révision 1.3 : le core copie un fichier proposé par `imports` ; réponse `workout_saved` |
| `start_run` | `{ "objective": chaîne, "duration_min": entier, "seed": entier ou null, "w_prime_j": nombre ou null, "chassis": chaîne (facultatif) }` | Révision 1.4 (série R) : depuis `IDLE`, `READY` ou `FINISHED`, compose la run (R15) ; `session_state` passe à `LOADING` puis `READY`, `mode` = `ROGUE` ; `start` lance ensuite la run comme une séance. `seed` nul : tirée par le core ; `w_prime_j` nul : valeur de `config.toml`. `chassis` (lot R9) : identifiant parmi `hello_ack.config.rogue.chassis.unlocked`, `standard` si absent ; inconnu : `error` `run_invalid`, non débloqué : `item_locked`. Objectif ou durée hors des listes de `hello_ack.config.rogue` : `error` `run_invalid` |
| `rogue_resync` | `{}` | Révision 1.4 (série R) : le core renvoie le message `room` de la salle en cours et, en couloir, le message `loot` |
| `list_garage` | `{}` | Révision 1.4 (série V) : demande le catalogue du Garage ; réponse `garage` en parties, comme `routes` |
| `equip` | `{ "slot": chaîne, "item_id": chaîne }` | Révision 1.4 (série V) : choisit une pièce possédée ; `error` `item_locked` sinon ; réponse `progression` |
| `buy` | `{ "item_id": chaîne }` | Révision 1.4 (série V) : achète une pièce débloquée ; `error` `not_enough_coins` ou `item_locked` ; réponse `progression` |
| `set_avatar` | `{ "avatar": objet }` | Révision 1.4 (série V) : remplace les réglages de l'avatar (§5) ; valeur hors bornes : `error` `avatar_invalid` ; réponse `progression` |
| `start_open_world` | `{ "lat", "lon", "heading_deg", "nav", "target", "loop_km", "seed" }` | Monde ouvert : prépare le départ ; `LOADING`, messages `world_status`, puis `READY` avec `route_id` = `ow:<id>` |
| `choose_branch` | `{ "junction_id": chaîne, "branch": entier }` | Monde ouvert : choisit la branche d'un carrefour avant son verrouillage |
| `world_search` | `{ "query": chaîne }` | Monde ouvert, menu : recherche de lieu ; réponse `places` |
| `world_map` | `{ "lat", "lon", "radius_m" }` | Monde ouvert, menu : routes autour d'un point ; réponse `world_map` |
| `world_regions` | `{}` | Monde ouvert, menu : régions du cache local ; réponse `world_regions` |
| `set_ride_mode` | `{ "mode": "sim" ou "erg" ou "cadence", "target_w": nombre (facultatif), "cadence_rpm": nombre (facultatif) }` | Révision 1.5 (lot O18) : pendant une session libre (`RUNNING` ou `PAUSED`, sans entraînement ni run), passe en SIM, en ERG libre (cible `target_w`, 50 à 1 000 W) ou en ERG à cadence verrouillée (cadence cible `cadence_rpm`, 50 à 120 tr/min, plage ± 15 %, puissance adaptée entre 50 W et 150 % de la FTP). Sans `target_w` : la cible en cours, sinon la puissance des 3 dernières secondes arrondie à 5 W (60 % de la FTP si elle manque) ; sans `cadence_rpm` : la cadence cible en cours, sinon la cadence mesurée arrondie à 5 (85 tr/min si elle manque) ; valeurs hors bornes ramenées aux bornes ; le biais repart à 100 %. Hors séance : `error` `busy` ; pendant un entraînement ou une run : `busy` ; vers l'ERG pendant une séance WTF : `busy` ; `mode` inconnu ou nombre mal typé : `bad_args` |
| `list_wtf_rules` | `{}` | Révision 1.5 (lot WTF2) : demande les treize règles du mode WTF ; réponse `wtf_rules` |
| `set_wtf_rule` | `{ "id": chaîne, "on": booléen }` | Révision 1.5 (lot WTF2) : allume ou coupe une règle (écrit `~/OpenRide/wtf.toml`), à tout moment, prise en compte tout de suite pendant une séance WTF ; réponse `wtf_rules` ; règle inconnue : `error` `wtf_rule_invalid` ; arguments mal typés : `bad_args` |
| `world_pin` | `{ "region_id": chaîne, "pinned": booléen }` | Monde ouvert, menu : épingle ou libère une région du cache ; réponse `world_regions` |
| `list_profiles` | `{}` | Révision 1.5 (lot MJ6) : profils de joueurs ; réponse `profiles` |
| `select_profile` | `{ "id": chaîne }` | Révision 1.5 (lot MJ6) : change de profil sans relancer, hors séance seulement ; réponse : `hello_ack` complet, puis `settings` et `progression` ; `busy` pendant une séance, `profile_invalid` pour un profil inconnu, illisible ou déjà utilisé |
| `create_profile` | `{ "name": chaîne }` | Révision 1.5 (lot MJ6) : crée un profil de joueur et le rend actif ; réponse : `hello_ack` complet, puis `profiles` ; `name_invalid`, ou `profile_invalid` au-delà de huit profils |
| `rename_profile` | `{ "id": chaîne, "name": chaîne }` | Révision 1.5 (lot MJ6) : change le nom affiché (l'identifiant ne change pas) ; réponse `profiles` ; `name_invalid` ou `profile_invalid` |
| `delete_profile` | `{ "id": chaîne }` | Révision 1.5 (lot MJ6) : met le profil à la corbeille ; refusé (`profile_invalid`) pour le profil en cours, le profil d'essai et le dernier profil joueur ; réponse `profiles` |
| `list_contents` | `{}` | Révision 1.5 (lot O25) : contenus installables depuis « Réglages › Contenus » ; réponse `contents` |
| `install_content` | `{ "id": chaîne }` | Révision 1.5 (lot O25) : installe un contenu de `contents` sans rien écraser, hors séance ; réponse `contents` au départ (`installing`), une fois par seconde au plus pendant l'installation, puis à la fin ; `busy` pendant une séance, `content_invalid` pour un contenu inconnu ou si une installation tourne déjà, `content_failed` si elle échoue |


**Cyber-Rogue et Garage (révision 1.4, lot T1).** Fin de run : `end_session` avec `save` vrai suffit, le résultat (`abandoned` si la run n'est pas finie) est dans `summary.rogue` ; il n'y a pas de commande d'abandon (décision R-Q3 du 26 octobre). Les commandes du Garage (`list_garage`, `equip`, `buy`, `set_avatar`) ne sont acceptées que hors séance (`IDLE`, `READY`) ; sinon `error` `busy`. Quand `[progression] enabled` est faux, le core ne met pas `progression` dans `hello_ack` et répond `bad_args` à ces commandes ; si le profil ne peut pas être écrit, `recording_failed` et rien ne change. Après `equip`, `buy` ou `set_avatar` réussi, le core envoie le message `progression` (`v`, `request_cmd_id` et les champs de `hello_ack.config.progression`, §5) : l'engine n'a rien à recalculer, et aucun nouveau `hello_ack` n'est envoyé (l'engine le traite comme la fin de la poignée de main). Le message `garage` porte `v`, `request_cmd_id`, `part`, `parts` et `items` ; chaque élément : `id`, `slot` (`frame`, `wheels`, `helmet`, `kit`, `socks`, `glasses`), `name`, `state` (`locked`, `buyable`, `owned`, `equipped`), `level_required`, `price`, `challenge` (texte du défi qui offre la pièce, ou `null`), `mass_delta_kg`, `cda_delta_pct`, `terrain` (`flat`, `rolling`, `climb`, `all`), `look` (identifiant de rendu, lot V7). Chaque élément de `routes` gagne le champ facultatif `terrain` (`flat`, `rolling`, `climb` ou `null`, calculé par le core, lot V3 §4.3), pour le conseil d'équipement de l'écran « Prêt » (V8).

**Listes des parcours et des entraînements.** Le core est la seule source de vérité : l'engine ne lit ni le dossier des parcours ni les fichiers `.zwo`. Le core lit le disque à la demande, hors de la boucle physique à 50 Hz, et répond dans les 500 ms pour 200 parcours.

| Message | Sens | Champs |
| --- | --- | --- |
| `routes` | core vers engine | `v`, `request_cmd_id`, `part`, `parts`, `items`, `truncated` |
| `workouts` | core vers engine | `v`, `request_cmd_id`, `part`, `parts`, `items`, `truncated` |

- `request_cmd_id` reprend le `cmd_id` de la demande. Le core répond à chaque demande reçue, y compris quand ce `cmd_id` est déjà traité, puisque la réponse a pu se perdre.
- Une réponse tient en un ou plusieurs datagrammes de 60 000 octets au plus : `part` va de 1 à `parts`, et chaque élément est dans une seule partie. L'engine assemble les parties d'une même réponse. S'il lui en manque une seconde après la première reçue, il renvoie la commande avec un nouveau `cmd_id`, au plus 3 fois.
- Au plus 200 éléments au total, triés par nom ; `truncated` est vrai s'il y en a davantage.
- Élément de `routes` : `id` (nom du `.world`, sert à `select_route`), `name`, `status` (`ready`, `to_compile`, `outdated`, `invalid`, comme `catalog.py`), `length_m` (nombre ou `null`), `route_type` (`open`, `loop`, `out_and_back` ou `null`), `has_terrain` (booléen), `error` (chaîne ou `null`). Seul un parcours `ready` ou `outdated` peut être choisi.
- Élément de `workouts` : `id` (sert à `select_workout`), `name`, `duration_s`, `block_count`, `selectable` (booléen), `error` (chaîne ou `null`), `profile` : au plus 30 triplets `[durée_s, fraction de FTP au début, fraction à la fin]` pour l'aperçu (jamais `null` depuis le lot O19 : un FreeRide arrive à 50 W) ; au-delà, les premiers 30 et `profile_truncated` vrai.
- Révision 1.3 (lot O12), champs facultatifs. Élément de `routes` : `stats` (fiche calculée du lot O15, absente sans fiche à jour) = `{distance_m, gain_m, max_grade_pct, duration_s, difficulty, main_climb}`, où `duration_s` est la durée estimée à la FTP de `config.toml` (comme `route-list --ftp`), `difficulty` va de 1 à 5 et `main_climb` vaut `{length_m, gain_m, avg_grade_pct, category}` ou `null` ; `library` (fiche saisie `<trace>.toml`) = `{description, region, tags}`. Le tri et les filtres de la bibliothèque se font dans l'engine sur ces champs. Élément de `workouts` : `unit` = `watts` quand les cibles du fichier sont en watts absolus (`.erg`, lot O9) ; `profile` reste en fraction de la FTP du core et l'engine affiche alors des watts (fraction × FTP) ; absent ou `ftp` : pourcentages de la FTP.
- La compilation d'une trace GPX depuis le menu n'est pas prévue en v1.1 : le lanceur compile les traces nouvelles au démarrage (lot N11). Un parcours `to_compile` est affiché mais pas sélectionnable.

**Entraînements créés ou importés depuis le menu (révision 1.3, lot N16, décision D4 de l'audit IPC du 26 octobre).** Le core reste seul à lire et à écrire le dossier des entraînements ; l'engine affiche, règle les paramètres et choisit.

| Message | Sens | Champs |
| --- | --- | --- |
| `imports` | core vers engine | `v`, `request_cmd_id`, `part`, `parts`, `truncated`, `items` : liste de `{path, file, source, imported}` |
| `workout_saved` | core vers engine | `v`, `request_cmd_id`, `workout_id` (identifiant final, pour `select_workout`), `name`, `created` (faux si un fichier identique était déjà là) |

- Hors séance seulement (pas pendant `RUNNING` ni `PAUSED`) : sinon `error` `busy`.
- `create_workout` : bornes `warmup_min` et `cooldown_min` 0 à 30, `reps` 1 à 20, `on_s` et `off_s` 15 à 1 200 s, `on_pct` 50 à 200 et `off_pct` 30 à 100 (% de la FTP) ; hors bornes ou non entier : `error` `bad_args`. Le core écrit `intervalles_<reps>x<on_s>s_<on_pct>.zwo` (`Warmup`, `IntervalsT`, `Cooldown` en % de la FTP), nommé « Intervalles 5 × 4 min à 105 % » ; les mêmes paramètres réécrivent le même fichier.
- `list_imports` : fichiers `.zwo`, `.erg` et `.mrc` de `~/Téléchargements`, `~/Downloads`, `~/Bureau`, `~/Desktop`, `~/OpenRide/Import` et du dossier personnel, sans sous-dossiers, les plus récents d'abord, 30 au plus ; `source` est le dossier affiché, `imported` est vrai si un entraînement du même nom existe déjà.
- `import_workout` : `path` doit être l'un des chemins de la dernière réponse `imports` (sinon `error` `workout_invalid`). Le core relit le fichier (illisible ou invalide : `workout_invalid`, rien n'est écrit) ; un fichier identique déjà importé n'est pas recopié ; un entraînement différent du même nom n'est jamais écrasé : la copie prend le suffixe `_2`, `_3`… Échec d'écriture : `workout_write_failed`.
- Ces trois commandes sont idempotentes : le core répond à chaque copie reçue, comme pour les listes. L'engine redemande ensuite `list_workouts` et place le focus sur `workout_id`.

**Plans d'entraînement et test de FTP depuis le menu (révision 1.3, lot O12).** Le core lit et écrit les plans (lot O11) et la configuration ; l'engine affiche et choisit.

| Message | Sens | Champs |
| --- | --- | --- |
| `plans` | core vers engine | `v`, `request_cmd_id`, `items` (au plus 50 : `{id, name, weeks, sessions, active, error}`, un plan invalide est listé avec son erreur et ne peut pas être démarré), `truncated`, `active` (plan actif ou `null`) |

- `active` : `id`, `name`, `start` (date de début), `week` (semaine en cours, ou `null` hors des semaines du plan), `weeks`, `finished`, `done`, `total`, `done_pct`, `today` (séances du jour), `late` (séances en retard encore rattrapables, 7 au plus), `next` (prochaine séance ou `null`) et `plan_day` (entraînement que lance `start` avec `plan_day`, ou `null`). Chaque séance : `{week, day, date, workout, name, duration_s, tss, done}`, où `workout` est l'identifiant à choisir (ou `ftp_test:ramp`, `ftp_test:20min`) et `tss` l'estimation à la FTP du core (`null` si l'entraînement manque).
- Une séance compte comme faite d'après l'historique (lot O11) : après une séance du plan, l'engine redemande `list_plans` pour la voir comptée.
- `start_plan`, `stop_plan` et `accept_ftp` : hors séance seulement (sinon `error` `busy`).
- `summary.ftp_test` (§3) : résultat d'une séance de test de FTP, `{test, ftp_w, previous_ftp_w, warnings, reliable}` ; `warnings` parmi `too_short`, `erratic_cadence`, `trainer_dropout`, `paused` ; `reliable` faux si l'effort est trop court, coupé ou mis en pause. `accept_ftp` écrit `ftp_w` ; sans test de FTP depuis le lancement du core : `error` `ftp_result_missing` ; résultat douteux sans `force` vrai : `error` `ftp_result_doubtful` (l'engine demande alors une confirmation) ; FTP hors des bornes de `config.toml` : `setting_invalid`. Le résultat reste écrit dans le journal de la séance : `openride-core ftp-test --accept` permet de l'accepter plus tard.

**Appairage depuis le menu (révision 1.2, lot N13).** Le core recherche et écrit ; l'engine affiche et choisit.

| Message | Sens | Champs |
| --- | --- | --- |
| `scan_results` | core vers engine | `v`, `request_cmd_id`, `done` (booléen), `items` : liste de `{role, name, address, rssi, configured}`, `plus_address` (adresse ou `null`) |

- Hors séance seulement (`IDLE` ou `READY`) : sinon le core répond `error` avec le code `busy`.
- `scan_devices` : un premier `scan_results` avec `done` faux part aussitôt (résultat précédent), le dernier avec `done` vrai à la fin de la recherche. `role` vaut `trainer`, `click`, `hr_strap` ou `hr_watch` ; `configured` est vrai si l'adresse est déjà dans `config.toml`. Les appareils déjà reliés à la séance (muets en recherche) sont listés grâce à BlueZ. Au plus 12 appareils, noms coupés à 24 caractères, 1 400 octets au plus.
- `identify_click_plus` : le core attend un appui « + » pendant 15 s sur le Click relié à la séance (ou, s'il n'y en a pas, en se connectant aux boîtiers trouvés). Cet appui ne pilote pas le menu (pas d'`input`). Réponse : `scan_results` avec `done` vrai, `request_cmd_id` de la commande et `plus_address` (`null` sans appui).
- `pair_devices` : une adresse `null` garde la valeur actuelle ; le nom du trainer et de la ceinture vient de la dernière recherche. L'écriture garde le reste du fichier (copie `config.toml.bak`) et la nouvelle configuration sert au prochain lancement. Adresse mal formée ou même boîtier en « + » et « − » : `error` `pairing_failed`, rien n'est écrit.

**Monde ouvert (révision 1.5, lot W1).** Le monde ouvert (`docs/2.0/PLAN_SERIE_W.md`) est généré pendant la séance par le processus `openride-worldgen`, que le core pilote selon `docs/contracts/worldgen_v1.md`. Le core lit la route engagée et publie le prochain carrefour ; l'engine lit le monde vivant (`world_format_v1.md` §13) et ne parle qu'au core. Révision 1.5, après la 1.4 des séries R, T et V.

- `start_open_world` : `nav` vaut `ride` (balade), `destination` (`target` = `{lat, lon}`) ou `loop` (`loop_km`) ; `seed` entier. Hors séance seulement (`IDLE` ou `READY`), sinon `error` `busy`. Pendant la préparation, `world_status` (au plus 4 par seconde) ; départ hors cache sans réseau ou sans route à moins de 200 m : `error` `world_unavailable`, retour à `IDLE`. `hello_ack.config.open_world_dir` donne le dossier des séances : `ow:<id>` désigne `<open_world_dir>/<id>.world`.
- `choose_branch` : accepté tant que `s` est avant le point de verrouillage du carrefour (30 m avant) ; ensuite `error` `branch_locked` ; identifiant inconnu : `error` `unknown_junction`. Le Click fait le même choix (décision W-Q1) : pendant un monde ouvert, quand un carrefour est proposé (à moins de 300 m) et non verrouillé, la flèche gauche ou droite du boîtier gauche (événements `LEFT_SHORT`, `RIGHT_SHORT`) prend la branche voisine dans ce sens, `A_SHORT` du boîtier droit passe à la branche suivante, en boucle, et `A_LONG` valide tout de suite la branche affichée (plan des boutons, spécification générale §7.1) ; ces événements existent depuis la révision 1.3 et sont relayés à l'engine comme les autres. Sans appui, la branche par défaut du navigateur est prise. Tant que le boîtier gauche du Click peut se taire après 35 à 60 s (lot Q6), `A_SHORT` et le clavier (`choose_branch`) sont les moyens principaux de choisir ; les flèches du boîtier gauche ne sont qu'un complément (décision D8 de l'audit IPC du 26 octobre).
- Champ `open_world` de `state`, dans les trames d'une séance en monde ouvert, sauf celles qui portent `devices` (une sur 30 : l'engine garde le dernier `open_world` reçu) : `rev` (révision du monde vivant : l'engine relit `live.json`, les parties de route et `junctions.json` quand elle change), `next` (prochain carrefour devant, ou `null`) et `data` (`cached`, `downloading`, `offline`, `missing`). `next` : `id`, `d_m` (distance le long de la route engagée), `default`, `chosen`, `locked`, `b` = au plus 4 triplets `[angle, classe, pente]` : angle relatif au cap d'arrivée en degrés entiers, positif à droite ; classe `p` (grande route), `s`, `t`, `m` (petite route), `c` (piste cyclable), `k` (chemin revêtu) ; pente moyenne des 500 premiers mètres à 0,1 % près. La trame la plus chargée (ERG, 5 bots, carrefour à 4 branches) reste sous 1 400 octets.
- `hello_ack.config.modes` : le core y ajoute `"open_world"` quand il sait lancer le monde ouvert (§5, « Modes de jeu »).
- `pause_reason` = `world_data` : moins de 200 m de route connue devant, que le générateur soit sans données ou en retard sur le cycliste ; reprise automatique quand 500 m sont de nouveau connus.
- En ERG, le monde ouvert est permis (décision W-Q5) : la pente ne change pas la résistance.

| Message | Sens | Champs |
| --- | --- | --- |
| `world_status` | core vers engine | `v`, `phase` (`dem`, `osm`, `tiles`, `generate`, `ready`, `error`), `done_bytes`, `total_bytes` (ou `null`), `squares_ready`, `squares_needed`, `message` |
| `places` | core vers engine | `v`, `request_cmd_id`, `part`, `parts`, `truncated`, `items` : au plus 50 `{name, kind, lat, lon, cached, source}` |
| `world_map` | core vers engine | `v`, `request_cmd_id`, `part`, `parts`, `lat`, `lon`, `radius_m`, `truncated`, `roads` : `{c, xz}`, classe et suite plate de coordonnées en mètres entiers depuis le point demandé, simplifiée à 20 m |
| `world_regions` | core vers engine | `v`, `request_cmd_id`, `part`, `parts`, `cache_bytes`, `cache_max_bytes`, `items` : `{id, name, bytes, pinned, last_used, bbox}` |

`places`, `world_map` et `world_regions` suivent les règles de `routes` (parties de 60 000 octets, `request_cmd_id`, nouvelle demande si une partie manque). `world_search` lit d'abord la liste embarquée et les bases locales ; il n'interroge Nominatim que si le réseau est permis, à la demande du cycliste, une requête par seconde au plus.

**Profils de joueurs (révision 1.5, lot MJ6, plan `docs/2.0/PLAN_SERIE_MJ.md` §6).** Un profil est un joueur : ses réglages (FTP, poids, FC max, séance, vent, caméra, courbes, ceinture cardio), sa progression, ses records, son plan et ses séances. Le core lit et écrit les profils ; l'engine affiche « Qui roule ? », la saisie du nom et la gestion.

| Message | Sens | Champs |
| --- | --- | --- |
| `profiles` | core vers engine | `v`, `request_cmd_id`, `active` (identifiant du profil en cours), `items` : au plus 8 `{id, name, type, level, last_ride, kit_primary}`, un seul datagramme (moins de 1 000 octets) |

- `type` vaut `joueur` ou `essai` ; `level` est le niveau de progression (1 à 50) ; `last_ride` la date de la dernière séance (`AAAA-MM-JJ`) ou `null` ; `kit_primary` la couleur principale du maillot de l'avatar (0 à 15, comme `progression.avatar`). Les profils de type `joueur` sont triés par nom ; le profil d'essai `_essai` n'y figure que s'il est le profil en cours.
- `select_profile`, `create_profile`, `rename_profile` et `delete_profile` : hors séance seulement (`IDLE`, `READY`, `FINISHED`, `ERROR`), sinon `error` `busy`. `list_profiles` est accepté à tout moment.
- Nom (`create_profile`, `rename_profile`) : 1 à 16 caractères, lettres (accents compris), chiffres, espace et tiret, différent des noms des autres profils ; sinon `error` `name_invalid`. L'identifiant du dossier est tiré du nom à la création et ne change plus.
- Après `select_profile` ou `create_profile`, le core envoie un nouveau `hello_ack` complet (§5) : l'engine le traite comme une nouvelle poignée de main et redemande ses listes. La liaison Bluetooth du trainer et du Click n'est pas coupée.
- Les commandes de profil sont idempotentes : le core répond à chaque copie reçue, comme pour les listes ; une copie de `create_profile` déjà traitée ne crée pas un second profil.

**Contenus installables (révision 1.5, lot O25).** Le joueur remplit sa bibliothèque depuis « Réglages › Contenus », sans terminal. Le core lit et écrit les dossiers ; l'engine n'affiche que la liste.

| Message | Sens | Champs |
| --- | --- | --- |
| `contents` | core vers engine | `v`, `request_cmd_id`, `busy` (identifiant du contenu en cours d'installation ou `null`), `message` (compte rendu de la dernière installation, `""` sinon), `items` : au plus 32 `{id, kind, label, detail, state, network, size_mb, progress_pct}` ; champs facultatifs (lot O29) `disk_free_mb` (place libre sur le disque des contenus, Mo, ou `null`), `themes_mb` et `themes_max_mb` (place des thèmes installés et plafond `[render] theme_library_gb`, Mo) ; rangé avec `plans` parmi les messages de 60 000 octets au plus (§2) |

- `kind` vaut `starter` (contenus de départ : entraînements livrés, plans de départ, parcours de démonstration des biomes), `route_pack` (pack de parcours : `routes:cols_celebres`, construit depuis OpenStreetMap, ou archive `.zip` trouvée dans Téléchargements, sur le Bureau ou dans `~/OpenRide/Import`, lot O29) ou `theme` (archive d'un thème ou d'un pack de biomes, ou thème déjà installé, lot O29) ; l'engine affiche tout élément quel que soit son `kind`. Identifiants : `starter`, `routes:<pack>`, `archive:<n>` (rang dans la dernière liste envoyée, figée pendant une installation), `theme:<nom>` (installé, information seulement).
- Un pack de parcours installé est compilé tout de suite (`build-all`) : ses parcours arrivent dans la liste sans relancer.
- `state` vaut `missing` (rien d'installé), `partial`, `installed` ou `installing` (avec `progress_pct`, 0 à 100 ; `null` dans les autres états). `network` est vrai si l'installation télécharge ; `size_mb` est la place prise sur le disque, ou `null` si elle n'est pas connue.
- `list_contents` est une requête : le core répond à chaque copie reçue, comme pour les listes ; une copie de `install_content` déjà traitée est ignorée (accusé par `last_cmd_id`). Une installation ne remplace jamais un fichier du joueur ; une seule tourne à la fois. Au premier lancement (`openride-core run --first-run`, passé par le lanceur), le core installe `starter` de lui-même : rien n'est téléchargé.
- Après une installation, l'engine redemande les listes des parcours, des entraînements et des plans.

**Événements du Click (révision 1.3).** `type: "input"`, `event` parmi : `PLUS_SHORT`, `MINUS_SHORT`, `PLUS_LONG`, `MINUS_LONG` (+ et −, B valant −) ; `PLUS_UNCLEAR`, `MINUS_UNCLEAR` (appui de + ou − entre 0,5 et 0,9 s : sans effet, l'engine explique comment refaire l'appui) ; `A_SHORT`, `A_LONG`, `Z_SHORT`, `Z_LONG` (entre court et long : aucun événement) ; `Y_SHORT`, `LEFT_SHORT`, `RIGHT_SHORT`, `UP_SHORT`, `DOWN_SHORT` (un seul événement, quelle que soit la durée). Le rôle de chaque bouton dans les menus et dans chaque mode est fixé par la spécification générale §7.1, seule référence. Le core relaie tous les événements à l'engine, hors séance (menus) comme pendant `RUNNING` (retour sonore et explications ; l'engine ignore alors leur sens de menu), sauf `Y_SHORT` pendant `RUNNING`, que le core consomme (pause). Pendant `RUNNING`, le core agit lui-même sur + et − (braquet, biais, saut de bloc, pause ERG). Un événement `input` perdu n'est pas rejoué : sur localhost la perte est négligeable et un appui de menu manqué se refait. Mesure de latence (lot X7) : quand le core est lancé avec `--latence` (`[log] latence = true`), l'événement d'un appui du Click porte en plus `latence_id` (entier, identifiant de l'appui) et `latence_t` (heure murale de l'envoi, en secondes) ; l'engine écrit alors dans son journal `[latence] id=N etage=recu` à la réception et `etage=affiche` à la première image dessinée après le changement du HUD (braquet, cible ou biais ERG). Champs de diagnostic, absents en usage normal : ils ne changent pas la révision du contrat (§8, champs inconnus ignorés).

## 5. Messages de session : hello, heartbeat, fin

| Message | Sens | Champs | Rôle |
| --- | --- | --- | --- |
| `hello` | engine vers core | `v`, `engine_version`, `rev` (facultatif, révision 1.3) | Premier message de l'engine, répété chaque seconde jusqu'au `hello_ack` |
| `hello_ack` | core vers engine | `v`, `core_version`, `rev` (facultatif, révision 1.3), `config` (pour l'affichage : `ftp_w`, `hr_max_bpm` (facultatif, révision 1.5 : zones de FC du HUD), `profile` (facultatif, révision 1.5, lot MJ6 : profil en cours, `{id, name, type, count}`, `count` étant le nombre de profils de type `joueur`), `gears_total`, `theme`, `chart` (facultatif, révision 1.3, lot O14 : taille des courbes de la séance), `difficulty_pct` ; `modes`, facultatif, révision 1.3 ; `open_world_dir`, facultatif, révision 1.5) | Confirme la version du contrat et donne la configuration utile |
| `heartbeat` | engine vers core | `seq`, `fps` (nombre, facultatif) | À 2 Hz ; prouve que l'engine est vivant |
| `error` | core vers engine | `code`, `message` | Erreur à afficher (voir codes ci-dessous) |
| `bye` | engine vers core | — | L'engine se ferme volontairement |
| `shutdown` | core vers engine | — | Le core se ferme : l'engine quitte ou revient à l'écran d'attente |

**Réglages depuis le menu (révision 1.3, lots O3 et O4).** Le core lit, valide et écrit ; l'engine affiche et change les valeurs au Click.

| Message | Sens | Champs |
| --- | --- | --- |
| `settings` | core vers engine | `v`, `request_cmd_id`, `items` : liste de `{key, label, group, type, value, applies}` ; `group` range le réglage dans un sous-écran de « Réglages » (`rider` cycliste, `ride` séance, `graphics` graphisme, `sound` son, `wind` vent) ; `type` vaut `int` (avec `min`, `max`, `step`, `unit`) ou `choice` (avec `choices`) ; `applies` vaut `next_session` (séance suivante, sans relancer) ou `now` (qualité, thème, courbes, compteur d'images/s `render.fps`, jauge d'abri `render.draft_gauge` et volumes `audio.*` : l'engine les applique tout de suite) ; 32 éléments au plus (révision 1.5, 24 avant le 30 octobre), un seul datagramme de 60 000 octets au plus (§2, depuis le 30 octobre) |

- Réglages proposés : `rider.ftp_w`, `rider.mass_kg`, `rider.hr_max_bpm`, `trainer.difficulty_pct`, `gearing.start_gear`, `render.quality`, `render.theme` (`default` et les thèmes de `~/OpenRide/Themes/`), `render.chart` (courbes de la séance, lot O14 : `hidden`, `reduced`, `full` ; appliqué tout de suite). Bornes et choix : ceux de la validation de `config.toml`.
- `set_setting` : hors séance (`IDLE`, `READY`, `FINISHED`, `ERROR`), tout réglage. Pendant `RUNNING` ou `PAUSED`, seuls les réglages que l'engine applique tout de suite (`applies` = `now` : qualité, thème, courbes, mode d'affichage, images/s, vue de caméra, volumes) sont écrits ; les autres reçoivent `error` `busy` et rien n'est écrit (pendant la séance, la difficulté se change par `set_difficulty`). Précision du 28 octobre (outil X42) : la vue de caméra choisie en roulant, écrite par l'engine (lot V12), recevait `busy`. Valeur hors bornes ou choix inconnu : `error` `setting_invalid`, rien n'est écrit. Sinon le fichier est modifié comme pour `pair_devices` (copie `.bak`), la valeur sert dès la séance suivante (`hello_ack.config` aussi) et le core renvoie `settings` avec `request_cmd_id` de la commande.

**Codes d'erreur :** `version_mismatch` (versions majeures différentes), `route_not_found`, `route_invalid`, `workout_invalid`, `trainer_control_refused`, `recording_failed` ; révision 1.2 : `busy` (recherche ou appairage demandé pendant une séance ; aussi un réglage en révision 1.3), `scan_failed` (Bluetooth indisponible), `pairing_failed` (écriture refusée) ; révision 1.3 : `setting_invalid` (réglage inconnu ou valeur refusée), `bad_args` (arguments d'une commande absents ou mal typés, par exemple `set_difficulty` sans `pct` numérique ; rien n'est appliqué), `workout_write_failed` (entraînement impossible à écrire, lot N16), `plan_invalid` (plan inconnu ou invalide, date mal écrite, aucune séance du jour : lot O12), `ftp_result_missing` et `ftp_result_doubtful` (`accept_ftp`, lot O12), `bot_invalid` (argument `bots` de `start` refusé, lot O7) ; révision 1.4 : `run_invalid` (objectif ou durée de run hors liste), `item_locked` (pièce non débloquée ou non possédée), `not_enough_coins`, `avatar_invalid` (réglage d'avatar hors bornes) ; révision 1.5 (monde ouvert) : `branch_locked` (choix après le verrouillage), `unknown_junction`, `world_unavailable` (départ impossible : hors cache sans réseau, ou aucune route proche) ; `wtf_rule_invalid` (règle du mode WTF inconnue ou fichier non écrit, lot WTF2) ; `profile_invalid` (profil inconnu, illisible ou déjà utilisé, plus de huit profils, suppression refusée : lot MJ6), `name_invalid` (nom de profil vide, trop long, caractère refusé ou déjà pris : lot MJ6) ; `content_invalid` (contenu inconnu, ou installation déjà en cours : lot O25), `content_failed` (installation d'un contenu impossible : lot O25).

**`hello_ack` en cours de route (révision 1.5, lot MJ6).** Après un changement de profil (`select_profile`, `create_profile`), le core envoie un `hello_ack` complet sans `hello` préalable. L'engine repart alors de zéro sur ce qu'il tient du core : configuration, réglages, Garage, listes des parcours, des entraînements et des plans ; il les redemande. Un engine d'avant la 1.5 ne change jamais de profil et ne reçoit donc jamais ce `hello_ack`.

**Version.** Le core refuse un `hello` dont `v` diffère du sien, répond par une erreur `version_mismatch` et n'ouvre pas la séance. La règle d'évolution est au §8.

**Révision (1.3, décision D3 de l'audit IPC).** `hello` et `hello_ack` portent le champ facultatif `rev`, la révision du contrat que suit l'émetteur, en texte (« 1.3 »). Absent : émetteur antérieur à la 1.3. Une révision différente n'est pas une erreur, puisque les révisions d'une même version sont compatibles : chaque programme l'écrit dans son journal et continue, en ignorant les champs qu'il ne connaît pas.

**Modes de jeu (1.3).** `hello_ack.config.modes` est la liste des modes que ce core sait lancer : `"ride"` (parcours libre) et `"erg"` (entraînement) en 1.3 ; `"rogue"` (mode Cyber-Rogue) s'y ajoute depuis la révision 1.4 et `"open_world"` s'ajoutera avec la série W. Absent : l'engine suppose `["ride", "erg"]`. L'accueil de l'engine n'affiche que les modes annoncés, sans entrée grisée, et ignore une valeur qu'il ne connaît pas.

**Configuration des séries R et V (révision 1.4, lot T1).** `hello_ack.config` gagne deux objets facultatifs ; l'engine qui ne les trouve pas n'affiche rien de la série correspondante.

- `rogue`, présent si `"rogue"` est dans `modes` : `w_prime_j`, `w_prime_estimate_j` (lot R16, `null` sans estimation fiable), `cp_w`, `objectives` (`["endurance", "threshold", "vo2max"]`) et `durations_min` (`[30, 45, 60, 90]`), puis (lot R9, facultatifs) `chassis` (`unlocked` : identifiants des châssis débloqués, `selected` : celui de la dernière run s'il est toujours débloqué, sinon `standard`) et `lives` (vies en réserve, 0 à 3), et (révision 1.5, facultatif) `last` : `{objective, duration_min}` de la dernière run, relus dans le journal, ou `null` avant la première run ; l'engine en remplit le menu de départ et ne montre l'avertissement du premier lancement que si `last` est nul.
- `progression`, présent dès que le core connaît la progression : `level` (1 à 50), `xp` (total), `xp_level_start` et `xp_next_level` (seuils du niveau actuel et du suivant, `null` au niveau 50), `coins`, `equipped` (identifiant choisi par emplacement : `frame`, `wheels`, `helmet`, `kit`, `socks`, `glasses`), `avatar` et `lives` (vies du mode Cyber-Rogue en réserve).
- Objet `avatar` : `height` (`S`, `M`, `L`, `XL`), `build` (`slim`, `medium`, `strong`), `skin` (0 à 7), `hair` (0 à 5), `hair_color` (0 à 7), `kit_primary` et `kit_secondary` (0 à 15, indices de palettes fixes), `number` (0 à 999), et les deux seuils de la position en danseuse lus dans `[avatar]` de `config.toml` (lot V6) : `standing_grade_pct` (8 par défaut) et `standing_power_pct` (% de la FTP, 150 par défaut), transmis mais non modifiables par `set_avatar`. Tout se choisit dans des listes et des palettes, au Click ; aucune mesure réelle du cycliste n'y figure.

## 6. Gestion des pannes

Règle générale : la séance ne se perd jamais ; en cas de doute, le core met en pause et lâche la résistance.

| Situation | Détection | Réaction du core | Réaction de l'engine |
| --- | --- | --- | --- |
| Engine disparu | Pas de `heartbeat` depuis 2 s | Pause (`engine_lost`), pente 0 % envoyée au trainer, chronomètre arrêté, journal conservé | À son retour : `hello`, puis l'utilisateur décide de reprendre |
| Core injoignable | Pas de `state` depuis 1 s | — | Bandeau « core non joignable », caméra figée après 1 s d'extrapolation, `hello` toutes les secondes |
| Trainer perdu | Pas de données depuis 3 s | Pause (`trainer_lost`), reconnexion avec délai croissant | Bandeau d'alerte à partir de `trainer_status` |
| Trainer revenu | Notifications reprises | Reste en pause jusqu'à `resume` | Affiche le choix de reprise |
| Click perdu | Déconnexion BLE | `input_status` = `LOST`, la séance continue, le clavier reste actif | Affiche l'état du Click |
| Plus de route connue (monde ouvert) | Moins de 200 m de route engagée devant (générateur sans données ou en retard) | Pause (`world_data`), pente 0 % ; reprise automatique à 500 m connus | Message d'attente à partir de `pause_reason` et de `open_world.data` |
| Trame perdue ou en désordre | `seq` plus ancien que le dernier reçu | — | Ignore la trame ; un saut de `seq` est compté, pas signalé |
| Datagramme illisible | JSON invalide | Ignoré, compteur incrémenté | Idem |
| Refus du contrôle FTMS | Réponse du Control Point | Erreur `trainer_control_refused`, `session_state` = `ERROR` | Affiche le message |
| Core planté pendant une séance | Sortie du core en erreur, vue par le lanceur | Relancé par le lanceur (au plus 3 fois en 10 min) : reprend la séance de son journal en pause (`pause_reason` = `core_restarted`), `t` et `s` restaurés ; au-delà, séance sauvée par `recover` (lot N8) | Ne quitte pas ; bandeau « core non joignable », puis à la reprise « Séance reprise après un incident » et attente de `resume` |
| Échec d'écriture du journal | Exception d'écriture | Erreur `recording_failed`, pause (`pause_reason` = `recording_failed`), séance gardée en mémoire ; à la reprise, nouveau journal contenant toute la séance | Affiche le message |

Le core ne démarre jamais une séance (`RUNNING`) sans avoir reçu un `hello` valide. Une fois la séance démarrée, la perte de l'engine ne l'arrête pas : elle la suspend.

## 7. Exemples de trames et séquence d'une séance

**État en mode SIM**

```json
{"type":"state","v":1,"seq":48213,"t":1604.35,"session_state":"RUNNING","pause_reason":null,"trainer_status":"CONNECTED","input_status":"CONNECTED","mode":"SIM","route_id":"col-du-galibier","route_length_m":28450.0,"s":12873.4,"v":4.62,"grade":7.8,"grade_sent":8.1,"power":248,"power_3s":245.3,"cadence":79,"hr":151,"gear":9,"gears_total":24,"lat":45.0731,"lon":6.4027,"alt":1834.2,"erg":null,"summary":null,"last_cmd_id":6}
```

**Objet `erg` en mode ERG** (le reste de la trame est identique)

```json
{"workout_name":"Seuil 2x20","block_index":3,"block_count":7,"block_type":"steady","block_remaining_s":512.0,"block_total_s":1200.0,"target_w":238,"next_target_w":125,"bias_pct":102,"paused":false}
```

**Commande**

```json
{"type":"cmd","v":1,"cmd_id":7,"name":"select_route","args":{"route_id":"col-du-galibier"}}
```

**Objet `devices`** (ajouté à la trame d'état une fois par seconde)

```json
{"trainer":{"status":"CONNECTED","name":"HomeTrainer 0000","address":"C1:1C:00:00:00:03"},"click":[{"side":"plus","status":"CONNECTED","battery_pct":80},{"side":"minus","status":"SEARCHING","battery_pct":null}],"hr":{"status":"CONNECTED","source":"strap","battery_pct":null}}
```

**Liste des parcours** (réponse à `cmd list_routes` portant `cmd_id` 3)

```json
{"type":"routes","v":1,"request_cmd_id":3,"part":1,"parts":1,"truncated":false,"items":[{"id":"col-du-galibier","name":"Col du Galibier","status":"ready","length_m":28450.0,"route_type":"open","has_terrain":true,"error":null},{"id":"tour-du-lac","name":"Tour du lac","status":"to_compile","length_m":null,"route_type":null,"has_terrain":false,"error":null}]}
```

**Liste des entraînements**

```json
{"type":"workouts","v":1,"request_cmd_id":4,"part":1,"parts":1,"truncated":false,"items":[{"id":"seuil-2x20","name":"Seuil 2x20","duration_s":4200.0,"block_count":5,"selectable":true,"error":null,"profile":[[600,0.5,0.75],[1200,0.95,0.95],[600,0.55,0.55],[1200,0.95,0.95],[600,0.6,0.4]],"profile_truncated":false},{"id":"casse","name":"casse.zwo","duration_s":0,"block_count":0,"selectable":false,"error":"XML invalide ligne 3","profile":[]}]}
```

**Trame d'état classique de la révision 1.4** (champs ajoutés à la trame en mode SIM ci-dessus)

```json
{"segment":{"id":"climb-1","kind":"climb","category":"2","d_to_start_m":0.0,"elapsed_s":412.5,"gap_to_pr_s":-3.2},"powerup":{"held":"aero","active":null,"remaining_s":0.0},"jerseys":{"sprint":"me","kom":"b2"},"bot_ahead":"b2","bot_behind":null,"bots":[{"id":"b2","name":"Grimpeur","s":12650.4,"v":4.12,"kind":"constant","profile":"climber","cp_w":248.0,"mass_kg":62.0,"wbal_pct":71.5,"jersey":"kom","gap_s":8.4}]}
```

**Objet `rogue`** (trame d'état en mode `ROGUE`, avec `route_id`, `lat`, `lon` et `alt` à `null`)

```json
{"phase":"ROOM","room_id":7,"room_index":3,"rooms_total":9,"archetype":"puncheur","boss_phase":null,"s_room":812.5,"enemy_hp":640.0,"enemy_hp_max":1000.0,"shield":40.0,"shield_max":100.0,"adrenaline":65.0,"w_bal_j":14200.0,"w_prime_j":20000.0,"posture":"FLUIDE","firewall_gap_m":120.5,"gold":85,"windows":[{"kind":"strike_target","s_start":900.0,"s_end":960.0}],"hack":null,"overheat":false,"loot_focus":null,"events":["perfect_shift"]}
```

**Résultat d'un segment**

```json
{"type":"segment_result","v":1,"segment_id":"climb-1","name":"Côte du village","kind":"climb","time_s":312.4,"with_powerup":false,"pr":true,"pr_time_s":318.9,"rank":2,"rank_total":5,"points":3,"equipment_gain_s":-4.1}
```

**Couloir du mode Cyber-Rogue**

```json
{"type":"loot","v":1,"corridor_id":3,"cards":[{"id":"c-overclock","name":"Overclock","kind":"attack","text":"Coups critiques +20 %","replaces_gear":null},{"id":"c-ice","name":"Pare-feu glacé","kind":"defense","text":"Bouclier +15","replaces_gear":null},{"id":"c-gear11","name":"Braquet 11 renforcé","kind":"gear","text":"Remplace le braquet 11","replaces_gear":11}],"doors":[{"side":"left","room_id":8,"archetype":"grimpeur"},{"side":"right","room_id":9,"archetype":"saboteur"}],"reroll_cost":20,"gold":85}
```

**Bilan de progression**

```json
{"type":"xp_result","v":1,"eligible":true,"reason":null,"gains":[{"source":"distance","points":120},{"source":"climb","points":45},{"source":"segment_pr","points":30}],"total":195,"level_before":7,"level_after":8,"xp_total":4310,"xp_next_level":5000,"coins_gained":39,"coins_total":210,"unlocked":["wheels-carbon-40"],"challenges":[],"equipment_gain_s":-12.5,"more":false}
```

**Configuration de la progression dans `hello_ack`**

```json
{"type":"hello_ack","v":1,"core_version":"0.9.0","rev":"1.4","config":{"ftp_w":250,"gears_total":24,"theme":"default","modes":["ride","erg","rogue"],"rogue":{"w_prime_j":20000,"w_prime_estimate_j":null,"cp_w":240,"objectives":["endurance","threshold","vo2max"],"durations_min":[30,45,60,90],"chassis":{"unlocked":["standard","blinde"],"selected":"standard"},"lives":2},"progression":{"level":8,"xp":4310,"xp_level_start":3800,"xp_next_level":5000,"coins":210,"equipped":{"frame":"frame-alu","wheels":"wheels-carbon-40","helmet":"helmet-basic","kit":"kit-blue","socks":"socks-white","glasses":"glasses-none"},"avatar":{"height":"M","build":"medium","skin":3,"hair":2,"hair_color":1,"kit_primary":4,"kit_secondary":11,"number":27,"standing_grade_pct":8,"standing_power_pct":150},"lives":2}}}
```

**Objet `erg` d'une session libre en ERG à cadence verrouillée** (révision 1.5, lot O18 ; le cycliste tourne au-dessus de la plage, la puissance monte)

```json
{"kind":"cadence","workout_name":"ERG cadence","block_index":1,"block_count":1,"block_type":"steady","block_remaining_s":0.0,"block_total_s":0.0,"target_w":207,"next_target_w":null,"bias_pct":100,"paused":false,"cadence_target_rpm":90,"cadence_low_rpm":76.5,"cadence_high_rpm":103.5,"cadence_zone":"high"}
```

**Bascule de mode d'une session libre** (révision 1.5, lot O18)

```json
{"type":"cmd","v":1,"cmd_id":21,"name":"set_ride_mode","args":{"mode":"cadence","cadence_rpm":90}}
```

**Liste des profils** (révision 1.5, lot MJ6 ; deux profils de joueur)

```json
{"type":"profiles","v":1,"request_cmd_id":30,"active":"cycliste-a","items":[{"id":"cycliste-a","name":"Cycliste A","type":"joueur","level":7,"last_ride":"2026-10-29","kit_primary":3},{"id":"cycliste-b","name":"Cycliste B","type":"joueur","level":1,"last_ride":null,"kit_primary":11}]}
```

**Changement de profil** (révision 1.5, lot MJ6)

```json
{"type":"cmd","v":1,"cmd_id":31,"name":"select_profile","args":{"id":"cycliste-b"}}
```

**Profil en cours dans `hello_ack`** (révision 1.5, lot MJ6)

```json
{"type":"hello_ack","v":1,"core_version":"0.9.0","rev":"1.5","config":{"ftp_w":250,"gears_total":24,"theme":"default","profile":{"id":"cycliste-b","name":"Cycliste B","type":"joueur","count":2}}}
```

**Contenus de départ en cours d'installation** (révision 1.5, lot O25)

```json
{"type":"contents","v":1,"request_cmd_id":40,"busy":"starter","message":"","items":[{"id":"starter","kind":"starter","label":"Contenus de départ","detail":"7 entraînements, 2 plans de départ, 4 parcours de démonstration des biomes","state":"installing","network":false,"size_mb":null,"progress_pct":40}]}
```

**Séquence nominale**

| Étape | Sens | Message ou événement |
| --- | --- | --- |
| 1 | core | Démarre, se connecte au trainer et au Click, émet `state` avec `session_state` = `IDLE` |
| 2 | engine vers core | `hello` |
| 3 | core vers engine | `hello_ack` |
| 4 | engine et core | `cmd list_routes` et `cmd list_workouts`, réponses `routes` et `workouts` ; `input` (menu piloté au Click ou au clavier) |
| 5 | engine vers core | `cmd select_route`, éventuellement `select_workout` |
| 6 | core | `LOADING`, lit la couche route, puis `READY` |
| 7 | engine vers core | `cmd start` |
| 8 | core vers engine | `state` à 30 Hz avec `RUNNING` ; `heartbeat` de l'engine à 2 Hz |
| 9 | engine vers core | `cmd end_session` avec `save` vrai |
| 10 | core vers engine | `state` avec `FINISHED` et `summary` (chemin du FIT) |

**Séquence : changement de profil** (révision 1.5, lot MJ6)

| Étape | Sens | Message ou événement |
| --- | --- | --- |
| 1 | engine vers core | `cmd list_profiles` (écran « Qui roule ? ») ; réponse `profiles` |
| 2 | engine vers core | `cmd select_profile` `{ "id": … }` (A maintenu sur un profil), hors séance |
| 3 | core | Recharge la configuration effective, la progression, les records, le plan et le dossier des séances du profil ; garde la liaison du trainer et du Click |
| 4 | core vers engine | `hello_ack` complet (`config.profile` du nouveau profil), puis `settings` et `progression` |
| 5 | engine vers core | `cmd list_routes`, `list_workouts`, … comme après une poignée de main |

**Séquence : ERG dans une session libre** (révision 1.5, lot O18)

| Étape | Sens | Message ou événement |
| --- | --- | --- |
| 1 | core vers engine | `state` avec `RUNNING`, `mode` = `SIM`, pas d'objet `erg` (session libre, sans entraînement ni run) |
| 2 | Click ou engine vers core | Y court (Click, ou touche envoyée par `input_event`) : le core passe en `PAUSED` (`pause_reason` = `user`) ; l'engine affiche l'écran de pause avec la ligne Mode |
| 3 | engine vers core | `cmd set_ride_mode` `{ "mode": "erg" }` (A long sur la ligne Mode) ; le core la compte dans `last_cmd_id` et journalise « Mode de la séance : ERG, cible … W » |
| 4 | core vers engine | `state` avec `mode` = `ERG` et `erg.kind` = `free`, `erg.paused` vrai tant que la séance est en pause |
| 5 | engine vers core | facultatif : `cmd set_ride_mode` `{ "mode": "erg", "target_w": … }` (ligne Puissance cible) ou `{ "mode": "cadence" }` (ERG cadence : `erg.kind` = `cadence`, champs `cadence_*`) |
| 6 | engine vers core | `Y_SHORT` ou ligne Reprendre : `RUNNING` ; le core écrit la cible au trainer (consigne de puissance FTMS, braquet ignoré) ; ± changent `bias_pct` (cible de puissance, ou cadence cible en ERG cadence) |
| 7 | engine vers core | retour : pause, `cmd set_ride_mode` `{ "mode": "sim" }` ; `state` sans `erg`, `mode` = `SIM`, la pente reprend depuis 0 % avec la limitation de variation |

Refus : hors `RUNNING` et `PAUSED`, pendant un entraînement (`erg.kind` = `workout`) ou une run, `error` `busy` ; `mode` inconnu ou nombre mal typé, `error` `bad_args` ; dans les deux cas rien ne change.

## 8. Compatibilité et évolution du contrat

Le champ `v` est la version majeure du contrat.

- **Compatible, `v` inchangé :** ajouter un champ facultatif, un message, une valeur d'énumération ; les lecteurs ignorent ce qu'ils ne connaissent pas.
- **Incompatible, `v` + 1 :** supprimer un champ, changer son unité ou son sens, rendre un champ obligatoire.
- **Transition :** pendant une version majeure, le core accepte la version précédente et la précédente est retirée à la suivante.
- **Schémas :** chaque message a un schéma JSON dans `docs/contracts/ipc/`, avec des trames d'exemple ; les tests des deux programmes valident leurs messages contre ces schémas.
- **Révisions :** elles se suivent dans l'ordre des fusions ; un programme qui annonce `rev` « 1.3 » connaît tout ce qui est noté jusqu'à la 1.3. Une révision fermée ne reçoit plus d'ajout : la 1.2 est fermée depuis la fusion de la 1.3, qui reste ouverte jusqu'à l'étiquette `v1.0.0` et reçoit les ajouts de la 1.0 fusionnés avant elle ; la 1.4 est celle des séries R, T et V, la 1.5 celle de la série W (spécification générale §6.1, décision du propriétaire du 27 octobre).
- **Journal des changements :** tenu en bas de ce document.
- **Ajouts en revue :** les changements du contrat portés par des PR encore ouvertes ne sont notés ici qu'à leur fusion ; leur liste à jour est dans la [spécification générale §6.1](../SPECIFICATION_GENERALE.md#61-révisions-du-contrat-ipc).

| Version | Date | Changement |
| --- | --- | --- |
| 1 | 21 octobre 2026 | Première version : état à 30 Hz, commandes avec accusé, heartbeat, gestion des pannes |
| 1 | 22 octobre 2026 | Ajout compatible : commande `input_event` ; événements `input` relayés aussi pendant `RUNNING` (retour sonore) |
| 1 | 23 octobre 2026 | Ajouts compatibles : remise à zéro de `last_cmd_id` à chaque `hello` ; `pause_reason` = `recording_failed` ; `summary.fit_path` peut valoir `null` ; schémas de tous les messages publiés ; clarification du double sens de `v` dans `state` |
| 1 (révision 1.1) | 24 octobre 2026 | Ajouts compatibles (lot N1) : commandes `list_routes` et `list_workouts`, messages `routes` et `workouts` (jusqu'à 60 000 octets, en parties) ; objet `devices` dans `state` une fois par seconde ; bilan enrichi dans `summary` ; forme de `bots` ; `pause_reason` = `core_restarted` et reprise après un plantage du core |
| 1 (révision 1.2) | 25 octobre 2026 | Ajouts compatibles (lot Q1) : commande `set_difficulty`, champ `difficulty_pct` (entier) dans `state` et `hello_ack.config` |
| 1 (révision 1.2) | 25 octobre 2026 | Ajouts compatibles (lot N13, accepté par le propriétaire le 25 octobre ; même révision que Q1, numérotation confirmée par le propriétaire le 26 octobre) : commandes `scan_devices`, `identify_click_plus` et `pair_devices`, message `scan_results`, codes d'erreur `busy`, `scan_failed` et `pairing_failed` |
| 1 (révision 1.3) | 26 octobre 2026 | Ajouts compatibles (lot P1, décisions du propriétaire du 25 octobre ; révision 1.3 parce que Q1 et N13 ont pris la 1.2) : objet facultatif `wind` dans `state` (2 fois par seconde, absent quand le vent est coupé), champs facultatifs `draft` et `draft_bot` ; limite de `state` portée à 4 096 octets (§2, décision D1 de l'audit IPC) ; champ facultatif `rev` dans `hello` et `hello_ack`, liste facultative `modes` dans `hello_ack.config` (§5, décision D3 ; décisions acceptées par le propriétaire le 26 octobre) |
| 1 (révision 1.3) | 26 octobre 2026 | Précisions sans changement de format (lot X25) : encodage UTF-8 sans échappement ; trame `state` trop grande allégée par le core au lieu d'être jetée (§3, liste `bots`) |
| 1 (révision 1.3) | 26 octobre 2026 | Ajouts compatibles (lots O3 et O4, acceptés par le propriétaire le 26 octobre ; révision 1.3 et non 1.2, décision du propriétaire du 27 octobre : les ajouts de la 1.0 fusionnés après la 1.3 y entrent) : commandes `list_settings` et `set_setting`, message `settings`, code d'erreur `setting_invalid` ; un réglage demandé pendant une séance reçoit `busy` (décision D6 de l'audit IPC, validée par le propriétaire le 26 octobre) |
| 1 (révision 1.3) | 26 octobre 2026 | Documenté sans changement de code (audit IPC du 26 octobre, décision D5) : code d'erreur `bad_args`, déjà émis par le core depuis le lot Q1 ; `hello_ack.config.difficulty_pct` facultatif dans le schéma, comme le veut la règle ci-dessus (décision D9) |
| 1 (révision 1.3) | 26 octobre 2026 | Ajouts compatibles (lot N16, décision D4 de l'audit IPC) : commandes `list_imports`, `create_workout` et `import_workout`, messages `imports` et `workout_saved`, code d'erreur `workout_write_failed` ; le core reste seul à écrire le dossier des entraînements |
| 1 (révision 1.3) | 27 octobre 2026 | Ajouts compatibles (validés par le propriétaire le 27 octobre ; même révision que P1, O3 et O4) : événements `input` de tous les boutons du Click V2 (`A_SHORT`, `A_LONG`, `Z_SHORT`, `Z_LONG`, `Y_SHORT`, `LEFT_SHORT`, `RIGHT_SHORT`, `UP_SHORT`, `DOWN_SHORT`) et de l'appui ambigu (`PLUS_UNCLEAR`, `MINUS_UNCLEAR`) ; Y n'est plus consommé par le core hors `RUNNING` (écran précédent ou reprise par le menu) |
| 1 (révision 1.3) | 27 octobre 2026 | Ajouts compatibles (lot O12 ; révision 1.3, décision du propriétaire du 27 octobre : tous les ajouts jusqu'à la v1.0.0 y entrent) : commandes `list_plans`, `start_plan`, `stop_plan` et `accept_ftp`, arguments `ftp_test` et `plan_day` de `start`, message `plans`, `summary.ftp_test`, champs `stats` et `library` des parcours et `unit` des entraînements, codes d'erreur `plan_invalid`, `ftp_result_missing` et `ftp_result_doubtful` ; argument `bots` de `start` et code `bot_invalid` (lot O7) |
| 1 (révision 1.4) | 27 octobre 2026 | Ajouts compatibles des séries R, T et V réunis en une révision (lot T1, décision D4 du propriétaire du 27 octobre ; anciens lots R1 et V1) : mode `ROGUE` et valeur `"rogue"` de `modes`, `lat`, `lon` et `alt` à `null` en run ; champs `segment`, `powerup`, `jerseys`, `bot_ahead`, `bot_behind` et objet `rogue` dans `state`, champs de profil des bots ; `summary.segments` et `summary.rogue` ; messages `segment_result`, `room`, `loot`, `garage`, `progression` et `xp_result` ; commandes `start_run`, `rogue_resync`, `list_garage`, `equip`, `buy`, `set_avatar` ; `hello_ack.config.rogue` et `hello_ack.config.progression` ; champ `terrain` des parcours ; codes `run_invalid`, `item_locked`, `not_enough_coins`, `avatar_invalid` ; aucun nouvel événement de bouton ; couche `segments` du format `.world` 1.3 |
| 1 (révision 1.5) | 27 octobre 2026 | Ajouts compatibles (lot W1, monde ouvert de la 2.0, numéro 1.5 validé par le propriétaire le 26 octobre (audit IPC, décision D2) ; après les révisions 1.3 (P1) et 1.4 (T1)) : commandes `start_open_world`, `choose_branch`, `world_search`, `world_map`, `world_regions`, `world_pin` ; messages `world_status`, `places`, `world_map`, `world_regions` ; champ `open_world` de `state` ; `hello_ack.config.open_world_dir` ; `pause_reason` = `world_data` ; codes `branch_locked`, `unknown_junction`, `world_unavailable` |
| 1 (révision 1.5) | 27 octobre 2026 | Changement compatible (décision du propriétaire du 27 octobre, essai-69 : la liste `settings` dépassait 1 400 octets avec les thèmes installés et était jetée) : une seule limite de 4 096 octets pour tout message hors messages en parties (§2), au lieu de 1 400 octets et 4 096 pour `state` ; l'engine annonce `rev` « 1.5 » |
| 1 (révision 1.5) | 27 octobre 2026 | Changement compatible (Réglages en sous-écrans, volumes et compteur d'images/s, docs/AUDIO.md) : champ `group` des éléments de `settings` ; réglages `bike.mass_kg`, `wind.from_deg`, `wind.gust_pct`, `render.fps` (`off`, `on` ou, depuis le 29 octobre, `detail` : temps CPU et GPU en plus ; simple valeur de `choices`, aucun changement de message), `audio.master_pct`, `audio.ride_pct`, `audio.ambience_pct` et `audio.events_pct` (`applies` = `now`) ; liste `settings` portée à 24 éléments au plus (12 avant), toujours sous 4 096 octets ; l'engine ignore déjà les clés qu'il ne connaît pas |
| 1 (révision 1.5) | 28 octobre 2026 | Ajout compatible (lot T12, bots à profil) : élément `{ "kind": "profile", "profile" }` de l'argument `bots` de `start` (`climber`, `rouleur`, `sprinter`, `diesel`), compté dans les 4 bots ; profil inconnu : `bot_invalid`. Dans la trame, le bot garde `kind` = `constant` avec les champs de profil de la révision 1.4 |
| 1 (révision 1.5) | 28 octobre 2026 | Ajout compatible (lot T13, équilibrage des bots à profil) : champ facultatif `level_pct` de l'élément `{ "kind": "profile" }` de `start.bots` (50 à 150 % de la FTP ; sans lui, le réglage `bots.level_pct`, « Niveau des bots ») ; hors bornes : `bot_invalid`. CP et masse calibrées publiées dans `cp_w` et `mass_kg` de la trame, sans nouveau champ |
| 1 (révision 1.5) | 28 octobre 2026 | Ajout compatible (lot O18, ERG d'une session libre, demande du propriétaire du 28 octobre) : commande `set_ride_mode` ; champs facultatifs `kind`, `cadence_target_rpm`, `cadence_low_rpm`, `cadence_high_rpm` et `cadence_zone` de l'objet `erg` |
| 1 (révision 1.5) | 29 octobre 2026 | Ajout compatible (jauge d'abri, demande du propriétaire du 29 octobre) : réglage `render.draft_gauge` (`off` ou `on`, `applies` = `now`, coupé par défaut) dans `settings` ; l'engine affiche alors au-dessus du bot `draft_bot` une jauge remplie selon `draft` ; aucun champ nouveau dans `state` |
| 1 (révision 1.5) | 28 octobre 2026 | Ajout compatible (décrochages du trainer de la séance A) : champ facultatif `busy` de `devices.trainer`, vrai tant que le Control Point est occupé par un autre appareil ; la séance n'est pas mise en pause tant que les mesures arrivent |
| 1 (révision 1.5) | 29 octobre 2026 | Ajouts compatibles (lot WTF2, mode « What the fuck », demande du propriétaire du 29 octobre) : argument `mode` de `start` ; valeur `"wtf"` de `hello_ack.config.modes` ; objet facultatif `wtf` dans `state` et `summary.wtf` ; commandes `list_wtf_rules` et `set_wtf_rule`, message `wtf_rules`, code d'erreur `wtf_rule_invalid` ; `set_ride_mode` vers l'ERG refusé (`busy`) pendant une séance WTF |
| 1 (révision 1.5) | 30 octobre 2026 | Ajouts compatibles (fin de la série R, demande du propriétaire du 30 octobre) : réglages `audio.rogue_sfx_pct` et `audio.rogue_music_pct` (`applies` = `now`, défauts 70 et 40, docs/AUDIO.md) dans `settings`, liste portée à 32 éléments au plus et rangée avec `plans` parmi les messages de 60 000 octets au plus (§2 ; avec les thèmes installés, 26 réglages dépassaient 4 096 octets, l'engine lit déjà ces tailles) ; champ facultatif `last` de `hello_ack.config.rogue` (dernière run : objectif et durée) ; `chassis.selected` donne le châssis de la dernière run |
| 1 (révision 1.5) | 30 octobre 2026 | Ajouts compatibles (lot MJ6, profils de joueurs, plan de la série MJ validé par le propriétaire le 29 octobre) : commandes `list_profiles`, `select_profile`, `create_profile`, `rename_profile` et `delete_profile`, message `profiles` (8 profils au plus, moins de 1 000 octets), objet facultatif `profile` de `hello_ack.config`, `hello_ack` renvoyé en cours de route après un changement de profil (§5), codes d'erreur `profile_invalid` et `name_invalid` |
| 1 (révision 1.5) | 31 octobre 2026 | Ajouts compatibles (lot O25, audit des options du 31 octobre accepté par le propriétaire) : commandes `list_contents` et `install_content`, message `contents` (rangé parmi les messages de 60 000 octets au plus), codes d'erreur `content_invalid` et `content_failed` ; le core installe les contenus de départ au premier lancement |
| 1 (révision 1.5) | 31 octobre 2026 | Ajouts compatibles (lot O29) : valeurs `route_pack` et `theme` de `contents.items[].kind`, champs facultatifs `disk_free_mb`, `themes_mb` et `themes_max_mb` de `contents` |
