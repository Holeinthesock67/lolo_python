# OpenRide Linux – Contrat IPC v1

21 octobre 2026, révision 1.1 du 24 octobre 2026, révision 1.2 du 25 octobre 2026, révision 1.3 du 26 octobre 2026 (ajouts compatibles, `v` reste 1)

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
| core vers engine | 5005 | `state`, `input`, `hello_ack`, `error`, `shutdown`, `routes`, `workouts`, `settings` | `state` à 30 Hz ; le reste sur événement |
| engine vers core | 5006 | `hello`, `heartbeat`, `cmd`, `bye` | `heartbeat` à 2 Hz ; `cmd` sur événement |

- Les ports sont modifiables dans `config.toml` (section `ipc`) ; si un port est occupé, le programme s'arrête avec un message explicite.
- Encodage : JSON compact en UTF-8, caractères accentués écrits tels quels (sans échappement `\u`) ; un lecteur JSON standard lit les deux formes.
- Taille maximale d'un datagramme : 1 400 octets, sauf `routes` et `workouts` (§4) : 60 000 octets, et, depuis la révision 1.3, `state` : 4 096 octets. Ces messages restent sur `127.0.0.1`, où un datagramme de cette taille passe sans fragmentation ; l'engine lit sa socket avec un tampon d'au moins 65 536 octets. Un engine antérieur à la 1.3 lit donc déjà ces trames : le changement est compatible (décision D1 de l'audit IPC du 26 octobre, acceptée par le propriétaire). Le core allège une trame `state` qui dépasse sa limite (§3, liste `bots`, lot X25) ; il jette, avec un avertissement, tout autre message trop grand.
- Un datagramme illisible (JSON invalide) est ignoré et compté dans les journaux.
- Le trainer notifie à environ 1 Hz (mode puissance) à 8 Hz (mode pente), mesuré ; la fréquence de 30 Hz du message `state` est indépendante et vient de la physique du core (50 Hz).

## 3. Message core vers engine : état de séance

`type: "state"`, envoyé à 30 Hz en continu, y compris hors séance. L'engine ne garde que le message au `seq` le plus élevé reçu.

| Champ | Type | Description |
| --- | --- | --- |
| `seq` | entier | Numéro croissant des trames d'état |
| `t` | nombre | Temps de séance en secondes (horloge du core, arrêtée en pause) |
| `session_state` | chaîne | `IDLE`, `LOADING`, `READY`, `RUNNING`, `PAUSED`, `FINISHED`, `ERROR` |
| `pause_reason` | chaîne ou `null` | `user`, `trainer_lost`, `engine_lost`, `recording_failed`, `core_restarted` (§6) quand `session_state` vaut `PAUSED` |
| `trainer_status` | chaîne | `CONNECTED`, `RECONNECTING`, `LOST`, `MOCK` |
| `input_status` | chaîne | `CONNECTED`, `LOST`, `KEYBOARD` |
| `mode` | chaîne | `SIM` ou `ERG` |
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
| `lat`, `lon`, `alt` | nombres | Position géographique correspondant à `s` |
| `erg` | objet ou `null` | Présent en mode ERG, voir ci-dessous |
| `summary` | objet ou `null` | Présent quand `session_state` vaut `FINISHED` (ou `ERROR` après une séance) : `duration_s` (temps chronométré), `distance_m`, `avg_power_w`, `fit_path` (`null` si aucun FIT n'a été produit) ; champs facultatifs du bilan enrichi ci-dessous |
| `devices` | objet, facultatif | État détaillé des appareils, voir ci-dessous ; envoyé une trame sur 30 (une fois par seconde) et dans la trame qui suit un changement, absent des autres trames |
| `bots` | liste, facultatif | Concurrents virtuels, voir ci-dessous |
| `wind` | objet, facultatif | Révision 1.3 : vent ressenti au point `s`, voir ci-dessous ; envoyé 2 fois par seconde (une trame sur quinze, jamais avec `devices`) et absent quand le vent est coupé |
| `draft` | nombre, facultatif | Révision 1.3 : coefficient d'aspiration appliqué au cycliste, de 0 à 0,45 (SRS §5) ; absent sans bot |
| `draft_bot` | chaîne, facultatif | Révision 1.3 : `id` du bot qui abrite le cycliste ; absent quand `draft` vaut 0 ou manque |
| `last_cmd_id` | entier | Dernier `cmd_id` traité par le core (§4) |

**Objet `erg`**

| Champ | Type | Description |
| --- | --- | --- |
| `workout_name` | chaîne | Nom de l'entraînement |
| `block_index`, `block_count` | entiers | Bloc en cours et nombre total, en comptant à partir de 1 |
| `block_type` | chaîne | `warmup`, `steady`, `interval_on`, `interval_off`, `ramp`, `cooldown`, `freeride` |
| `block_remaining_s`, `block_total_s` | nombres | Temps restant et durée du bloc |
| `target_w` | nombre | Cible de puissance en cours, biais inclus |
| `next_target_w` | nombre ou `null` | Cible du bloc suivant |
| `bias_pct` | nombre | Biais d'intensité (80 à 120) |
| `paused` | booléen | ERG en pause |

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
| `trainer` | `{status, name, address}` : `status` reprend `trainer_status` ; `name` (nom annoncé) et `address` sont des chaînes ou `null` |
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

## 4. Message engine vers core : commandes

`type: "cmd"`, envoyé sur événement. L'UDP peut perdre ou dupliquer un datagramme, donc chaque commande porte un `cmd_id` entier croissant propre à l'engine.

**Fiabilité.** L'engine renvoie la commande toutes les 200 ms jusqu'à voir son `cmd_id` dans le champ `last_cmd_id` du message `state` (abandon après 3 s avec un message d'erreur à l'écran). Le core ignore un `cmd_id` déjà traité : toutes les commandes sont donc idempotentes. Le compteur `cmd_id` est propre à une instance de l'engine : le core remet `last_cmd_id` à 0 à chaque `hello`, si bien qu'un engine relancé peut renuméroter ses commandes à partir de 1.

| `name` | `args` | Effet |
| --- | --- | --- |
| `select_route` | `{ "route_id": chaîne }` | Charge le parcours ; `session_state` passe à `LOADING` puis `READY` |
| `select_workout` | `{ "workout_id": chaîne ou null }` | Choisit un entraînement (mode ERG) ; `null` revient au mode SIM |
| `start` | `{}` | Démarre la séance (`READY` vers `RUNNING`) |
| `pause` | `{}` | Met en pause (`pause_reason` = `user`) |
| `resume` | `{}` | Reprend après une pause, quelle qu'en soit la raison |
| `end_session` | `{ "save": booléen }` | Termine ; avec `save` vrai, produit le FIT puis passe à `FINISHED` |
| `input_event` | `{ "event": chaîne }` | Touches lues par l'engine, même effet qu'un appui sur le Click (`PLUS_SHORT`, `MINUS_SHORT`, …) |
| `skip_block` | `{}` | Équivalent de l'appui long + en ERG, pour le clavier ou le menu |
| `list_routes` | `{}` | Demande la liste des parcours ; réponse `routes` |
| `list_workouts` | `{}` | Demande la liste des entraînements ; réponse `workouts` |
| `set_difficulty` | `{ "pct": nombre }` | Change la difficulté du trainer (0 à 100) pour la séance en cours |
| `scan_devices` | `{ "timeout_s": nombre }` (8 par défaut, 1 à 30) | Révision 1.2 : recherche des appareils Bluetooth ; réponses `scan_results` |
| `identify_click_plus` | `{}` | Révision 1.2 : attend un appui « + » du Click pendant 15 s ; réponse `scan_results` avec `plus_address` |
| `pair_devices` | `{ "trainer", "click_plus", "click_minus", "hr" }` : adresse ou `null` | Révision 1.2 : écrit les appareils choisis dans `config.toml` ; `error` `pairing_failed` en cas d'échec |
| `list_settings` | `{}` | Révision 1.3 : demande les réglages du menu ; réponse `settings` |
| `set_setting` | `{ "key": texte, "value": nombre ou texte }` | Révision 1.3 : écrit un réglage dans `config.toml` ; réponse `settings`, ou `error` `busy` / `setting_invalid` |

**Listes des parcours et des entraînements.** Le core est la seule source de vérité : l'engine ne lit ni le dossier des parcours ni les fichiers `.zwo`. Le core lit le disque à la demande, hors de la boucle physique à 50 Hz, et répond dans les 500 ms pour 200 parcours.

| Message | Sens | Champs |
| --- | --- | --- |
| `routes` | core vers engine | `v`, `request_cmd_id`, `part`, `parts`, `items`, `truncated` |
| `workouts` | core vers engine | `v`, `request_cmd_id`, `part`, `parts`, `items`, `truncated` |

- `request_cmd_id` reprend le `cmd_id` de la demande. Le core répond à chaque demande reçue, y compris quand ce `cmd_id` est déjà traité, puisque la réponse a pu se perdre.
- Une réponse tient en un ou plusieurs datagrammes de 60 000 octets au plus : `part` va de 1 à `parts`, et chaque élément est dans une seule partie. L'engine assemble les parties d'une même réponse. S'il lui en manque une seconde après la première reçue, il renvoie la commande avec un nouveau `cmd_id`, au plus 3 fois.
- Au plus 200 éléments au total, triés par nom ; `truncated` est vrai s'il y en a davantage.
- Élément de `routes` : `id` (nom du `.world`, sert à `select_route`), `name`, `status` (`ready`, `to_compile`, `outdated`, `invalid`, comme `catalog.py`), `length_m` (nombre ou `null`), `route_type` (`open`, `loop`, `out_and_back` ou `null`), `has_terrain` (booléen), `error` (chaîne ou `null`). Seul un parcours `ready` ou `outdated` peut être choisi.
- Élément de `workouts` : `id` (sert à `select_workout`), `name`, `duration_s`, `block_count`, `selectable` (booléen), `error` (chaîne ou `null`), `profile` : au plus 30 triplets `[durée_s, fraction de FTP au début, fraction à la fin]` pour l'aperçu, fractions `null` en roue libre ; au-delà, les premiers 30 et `profile_truncated` vrai.
- La compilation d'une trace GPX depuis le menu n'est pas prévue en v1.1 : le lanceur compile les traces nouvelles au démarrage (lot N11). Un parcours `to_compile` est affiché mais pas sélectionnable.

**Appairage depuis le menu (révision 1.2, lot N13).** Le core recherche et écrit ; l'engine affiche et choisit.

| Message | Sens | Champs |
| --- | --- | --- |
| `scan_results` | core vers engine | `v`, `request_cmd_id`, `done` (booléen), `items` : liste de `{role, name, address, rssi, configured}`, `plus_address` (adresse ou `null`) |

- Hors séance seulement (`IDLE` ou `READY`) : sinon le core répond `error` avec le code `busy`.
- `scan_devices` : un premier `scan_results` avec `done` faux part aussitôt (résultat précédent), le dernier avec `done` vrai à la fin de la recherche. `role` vaut `trainer`, `click`, `hr_strap` ou `hr_watch` ; `configured` est vrai si l'adresse est déjà dans `config.toml`. Les appareils déjà reliés à la séance (muets en recherche) sont listés grâce à BlueZ. Au plus 12 appareils, noms coupés à 24 caractères, 1 400 octets au plus.
- `identify_click_plus` : le core attend un appui « + » pendant 15 s sur le Click relié à la séance (ou, s'il n'y en a pas, en se connectant aux boîtiers trouvés). Cet appui ne pilote pas le menu (pas d'`input`). Réponse : `scan_results` avec `done` vrai, `request_cmd_id` de la commande et `plus_address` (`null` sans appui).
- `pair_devices` : une adresse `null` garde la valeur actuelle ; le nom du trainer et de la ceinture vient de la dernière recherche. L'écriture garde le reste du fichier (copie `config.toml.bak`) et la nouvelle configuration sert au prochain lancement. Adresse mal formée ou même boîtier en « + » et « − » : `error` `pairing_failed`, rien n'est écrit.

**Événements du Click (révision 1.3).** `type: "input"`, `event` parmi : `PLUS_SHORT`, `MINUS_SHORT`, `PLUS_LONG`, `MINUS_LONG` (+ et −, B valant −) ; `PLUS_UNCLEAR`, `MINUS_UNCLEAR` (appui de + ou − entre 0,5 et 0,9 s : sans effet, l'engine explique comment refaire l'appui) ; `A_SHORT`, `A_LONG`, `Z_SHORT`, `Z_LONG` (entre court et long : aucun événement) ; `Y_SHORT`, `LEFT_SHORT`, `RIGHT_SHORT`, `UP_SHORT`, `DOWN_SHORT` (un seul événement, quelle que soit la durée). Le rôle de chaque bouton dans les menus et dans chaque mode est fixé par la spécification générale §7.1, seule référence. Le core relaie tous les événements à l'engine, hors séance (menus) comme pendant `RUNNING` (retour sonore et explications ; l'engine ignore alors leur sens de menu), sauf `Y_SHORT` pendant `RUNNING`, que le core consomme (pause). Pendant `RUNNING`, le core agit lui-même sur + et − (braquet, biais, saut de bloc, pause ERG). Un événement `input` perdu n'est pas rejoué : sur localhost la perte est négligeable et un appui de menu manqué se refait.

## 5. Messages de session : hello, heartbeat, fin

| Message | Sens | Champs | Rôle |
| --- | --- | --- | --- |
| `hello` | engine vers core | `v`, `engine_version`, `rev` (facultatif, révision 1.3) | Premier message de l'engine, répété chaque seconde jusqu'au `hello_ack` |
| `hello_ack` | core vers engine | `v`, `core_version`, `rev` (facultatif, révision 1.3), `config` (pour l'affichage : `ftp_w`, `gears_total`, `theme`, `difficulty_pct` ; `modes`, facultatif, révision 1.3) | Confirme la version du contrat et donne la configuration utile |
| `heartbeat` | engine vers core | `seq`, `fps` (nombre, facultatif) | À 2 Hz ; prouve que l'engine est vivant |
| `error` | core vers engine | `code`, `message` | Erreur à afficher (voir codes ci-dessous) |
| `bye` | engine vers core | — | L'engine se ferme volontairement |
| `shutdown` | core vers engine | — | Le core se ferme : l'engine quitte ou revient à l'écran d'attente |

**Réglages depuis le menu (révision 1.3, lots O3 et O4).** Le core lit, valide et écrit ; l'engine affiche et change les valeurs au Click.

| Message | Sens | Champs |
| --- | --- | --- |
| `settings` | core vers engine | `v`, `request_cmd_id`, `items` : liste de `{key, label, type, value, applies}` ; `type` vaut `int` (avec `min`, `max`, `step`, `unit`) ou `choice` (avec `choices`) ; `applies` vaut `next_session` (séance suivante, sans relancer) ou `now` (qualité et thème : l'engine les applique tout de suite au décor) |

- Réglages proposés : `rider.ftp_w`, `rider.mass_kg`, `trainer.difficulty_pct`, `gearing.start_gear`, `render.quality`, `render.theme` (`default` et les thèmes de `~/OpenRide/Themes/`). Bornes et choix : ceux de la validation de `config.toml`.
- `set_setting` : hors séance seulement (`IDLE`, `READY`, `FINISHED`, `ERROR`) ; pendant `RUNNING` ou `PAUSED`, `error` `busy` et rien n'est écrit (pendant la séance, la difficulté se change par `set_difficulty`). Valeur hors bornes ou choix inconnu : `error` `setting_invalid`, rien n'est écrit. Sinon le fichier est modifié comme pour `pair_devices` (copie `.bak`), la valeur sert dès la séance suivante (`hello_ack.config` aussi) et le core renvoie `settings` avec `request_cmd_id` de la commande.

**Codes d'erreur :** `version_mismatch` (versions majeures différentes), `route_not_found`, `route_invalid`, `workout_invalid`, `trainer_control_refused`, `recording_failed` ; révision 1.2 : `busy` (recherche ou appairage demandé pendant une séance ; aussi un réglage en révision 1.3), `scan_failed` (Bluetooth indisponible), `pairing_failed` (écriture refusée) ; révision 1.3 : `setting_invalid` (réglage inconnu ou valeur refusée).

**Version.** Le core refuse un `hello` dont `v` diffère du sien, répond par une erreur `version_mismatch` et n'ouvre pas la séance. La règle d'évolution est au §8.

**Révision (1.3, décision D3 de l'audit IPC).** `hello` et `hello_ack` portent le champ facultatif `rev`, la révision du contrat que suit l'émetteur, en texte (« 1.3 »). Absent : émetteur antérieur à la 1.3. Une révision différente n'est pas une erreur, puisque les révisions d'une même version sont compatibles : chaque programme l'écrit dans son journal et continue, en ignorant les champs qu'il ne connaît pas.

**Modes de jeu (1.3).** `hello_ack.config.modes` est la liste des modes que ce core sait lancer : `"ride"` (parcours libre) et `"erg"` (entraînement) en 1.3 ; d'autres valeurs s'ajouteront (`"rogue"` avec la série R, `"open_world"` avec la série W). Absent : l'engine suppose `["ride", "erg"]`. L'accueil de l'engine n'affiche que les modes annoncés, sans entrée grisée, et ignore une valeur qu'il ne connaît pas.

## 6. Gestion des pannes

Règle générale : la séance ne se perd jamais ; en cas de doute, le core met en pause et lâche la résistance.

| Situation | Détection | Réaction du core | Réaction de l'engine |
| --- | --- | --- | --- |
| Engine disparu | Pas de `heartbeat` depuis 2 s | Pause (`engine_lost`), pente 0 % envoyée au trainer, chronomètre arrêté, journal conservé | À son retour : `hello`, puis l'utilisateur décide de reprendre |
| Core injoignable | Pas de `state` depuis 1 s | — | Bandeau « core non joignable », caméra figée après 1 s d'extrapolation, `hello` toutes les secondes |
| Trainer perdu | Pas de données depuis 3 s | Pause (`trainer_lost`), reconnexion avec délai croissant | Bandeau d'alerte à partir de `trainer_status` |
| Trainer revenu | Notifications reprises | Reste en pause jusqu'à `resume` | Affiche le choix de reprise |
| Click perdu | Déconnexion BLE | `input_status` = `LOST`, la séance continue, le clavier reste actif | Affiche l'état du Click |
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

## 8. Compatibilité et évolution du contrat

Le champ `v` est la version majeure du contrat.

- **Compatible, `v` inchangé :** ajouter un champ facultatif, un message, une valeur d'énumération ; les lecteurs ignorent ce qu'ils ne connaissent pas.
- **Incompatible, `v` + 1 :** supprimer un champ, changer son unité ou son sens, rendre un champ obligatoire.
- **Transition :** pendant une version majeure, le core accepte la version précédente et la précédente est retirée à la suivante.
- **Schémas :** chaque message a un schéma JSON dans `docs/contracts/ipc/`, avec des trames d'exemple ; les tests des deux programmes valident leurs messages contre ces schémas.
- **Journal des changements :** tenu en bas de ce document.

| Version | Date | Changement |
| --- | --- | --- |
| 1 | 21 octobre 2026 | Première version : état à 30 Hz, commandes avec accusé, heartbeat, gestion des pannes |
| 1 | 22 octobre 2026 | Ajout compatible : commande `input_event` ; événements `input` relayés aussi pendant `RUNNING` (retour sonore) |
| 1 | 23 octobre 2026 | Ajouts compatibles : remise à zéro de `last_cmd_id` à chaque `hello` ; `pause_reason` = `recording_failed` ; `summary.fit_path` peut valoir `null` ; schémas de tous les messages publiés ; clarification du double sens de `v` dans `state` |
| 1 (révision 1.1) | 24 octobre 2026 | Ajouts compatibles (lot N1) : commandes `list_routes` et `list_workouts`, messages `routes` et `workouts` (jusqu'à 60 000 octets, en parties) ; objet `devices` dans `state` une fois par seconde ; bilan enrichi dans `summary` ; forme de `bots` ; `pause_reason` = `core_restarted` et reprise après un plantage du core |
| 1 (révision 1.2) | 25 octobre 2026 | Ajouts compatibles (lot Q1) : commande `set_difficulty`, champ `difficulty_pct` (entier) dans `state` et `hello_ack.config` |
| 1 (révision 1.2) | 25 octobre 2026 | Ajouts compatibles (lot N13, accepté par le propriétaire le 25 octobre ; même révision que Q1, numérotation confirmée par le propriétaire le 26 octobre) : commandes `scan_devices`, `identify_click_plus` et `pair_devices`, message `scan_results`, codes d'erreur `busy`, `scan_failed` et `pairing_failed` |
| 1 (révision 1.2) | 26 octobre 2026 | Précisions sans changement de format (lot X25) : encodage UTF-8 sans échappement ; trame `state` trop grande allégée par le core au lieu d'être jetée (§3, liste `bots`) |
| 1 (révision 1.3) | 26 octobre 2026 | Ajouts compatibles (lot P1, décisions du propriétaire du 25 octobre ; révision 1.3 parce que Q1 et N13 ont pris la 1.2) : objet facultatif `wind` dans `state` (2 fois par seconde, absent quand le vent est coupé), champs facultatifs `draft` et `draft_bot` ; limite de `state` portée à 4 096 octets (§2, décision D1 de l'audit IPC) ; champ facultatif `rev` dans `hello` et `hello_ack`, liste facultative `modes` dans `hello_ack.config` (§5, décision D3 ; décisions acceptées par le propriétaire le 26 octobre) |
| 1 (révision 1.3) | 26 octobre 2026 | Ajouts compatibles (lots O3 et O4, acceptés par le propriétaire le 26 octobre ; révision 1.3 et non 1.2, décision du propriétaire du 27 octobre : les ajouts de la 1.0 fusionnés après la 1.3 y entrent) : commandes `list_settings` et `set_setting`, message `settings`, code d'erreur `setting_invalid` ; un réglage demandé pendant une séance reçoit `busy` (décision D6 de l'audit IPC, validée par le propriétaire le 26 octobre) |
| 1 (révision 1.3) | 27 octobre 2026 | Ajouts compatibles (validés par le propriétaire le 27 octobre ; même révision que P1, O3 et O4) : événements `input` de tous les boutons du Click V2 (`A_SHORT`, `A_LONG`, `Z_SHORT`, `Z_LONG`, `Y_SHORT`, `LEFT_SHORT`, `RIGHT_SHORT`, `UP_SHORT`, `DOWN_SHORT`) et de l'appui ambigu (`PLUS_UNCLEAR`, `MINUS_UNCLEAR`) ; Y n'est plus consommé par le core hors `RUNNING` (écran précédent ou reprise par le menu) |
