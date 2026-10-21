# OpenRide Linux – Contrat IPC v1

21 octobre 2026

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

## 2. Transport : UDP localhost, ports, fréquences

Deux sockets UDP non bloquantes sur `127.0.0.1`, sans connexion : chaque programme écoute sur son port et envoie vers l'autre.

| Sens | Port par défaut | Contenu | Fréquence |
| --- | --- | --- | --- |
| core vers engine | 5005 | `state`, `input`, `hello_ack`, `error`, `shutdown` | `state` à 30 Hz ; le reste sur événement |
| engine vers core | 5006 | `hello`, `heartbeat`, `cmd`, `bye` | `heartbeat` à 2 Hz ; `cmd` sur événement |

- Les ports sont modifiables dans `config.toml` (section `ipc`) ; si un port est occupé, le programme s'arrête avec un message explicite.
- Taille maximale d'un datagramme : 1 400 octets.
- Un datagramme illisible (JSON invalide) est ignoré et compté dans les journaux.
- Le trainer notifie à 1 à 4 Hz ; la fréquence de 30 Hz du message `state` est indépendante et vient de la physique du core (50 Hz).

## 3. Message core vers engine : état de séance

`type: "state"`, envoyé à 30 Hz en continu, y compris hors séance. L'engine ne garde que le message au `seq` le plus élevé reçu.

| Champ | Type | Description |
| --- | --- | --- |
| `seq` | entier | Numéro croissant des trames d'état |
| `t` | nombre | Temps de séance en secondes (horloge du core, arrêtée en pause) |
| `session_state` | chaîne | `IDLE`, `LOADING`, `READY`, `RUNNING`, `PAUSED`, `FINISHED`, `ERROR` |
| `pause_reason` | chaîne ou `null` | `user`, `trainer_lost`, `engine_lost` quand `session_state` vaut `PAUSED` |
| `trainer_status` | chaîne | `CONNECTED`, `RECONNECTING`, `LOST`, `MOCK` |
| `input_status` | chaîne | `CONNECTED`, `LOST`, `KEYBOARD` |
| `mode` | chaîne | `SIM` ou `ERG` |
| `route_id` | chaîne ou `null` | Nom du `.world` chargé ; l'engine en déduit le dossier |
| `route_length_m` | nombre ou `null` | Longueur de la route |
| `s` | nombre | Position le long de la route, en mètres |
| `v` | nombre | Vitesse virtuelle |
| `grade` | nombre | Pente réelle du terrain à `s` |
| `grade_sent` | nombre | Pente effective envoyée au trainer |
| `power` | nombre | Puissance mesurée, lissage court |
| `power_3s` | nombre | Puissance moyennée sur 3 s |
| `cadence` | nombre | Cadence |
| `hr` | entier ou `null` | Fréquence cardiaque |
| `gear` | entier | Vitesse virtuelle `k` (1 à 24) |
| `gears_total` | entier | Nombre de vitesses |
| `lat`, `lon`, `alt` | nombres | Position géographique correspondant à `s` |
| `erg` | objet ou `null` | Présent en mode ERG, voir ci-dessous |
| `summary` | objet ou `null` | Présent quand `session_state` vaut `FINISHED` : `duration_s`, `distance_m`, `avg_power_w`, `fit_path` |
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

Les bots, quand ils existeront, s'ajouteront dans un champ optionnel `bots` (liste de `{id, s, v}`) sans changer la version du contrat.

## 4. Message engine vers core : commandes

`type: "cmd"`, envoyé sur événement. L'UDP peut perdre ou dupliquer un datagramme, donc chaque commande porte un `cmd_id` entier croissant propre à l'engine.

**Fiabilité.** L'engine renvoie la commande toutes les 200 ms jusqu'à voir son `cmd_id` dans le champ `last_cmd_id` du message `state` (abandon après 3 s avec un message d'erreur à l'écran). Le core ignore un `cmd_id` déjà traité : toutes les commandes sont donc idempotentes.

| `name` | `args` | Effet |
| --- | --- | --- |
| `select_route` | `{ "route_id": chaîne }` | Charge le parcours ; `session_state` passe à `LOADING` puis `READY` |
| `select_workout` | `{ "workout_id": chaîne ou null }` | Choisit un entraînement (mode ERG) ; `null` revient au mode SIM |
| `start` | `{}` | Démarre la séance (`READY` vers `RUNNING`) |
| `pause` | `{}` | Met en pause (`pause_reason` = `user`) |
| `resume` | `{}` | Reprend après une pause, quelle qu'en soit la raison |
| `end_session` | `{ "save": booléen }` | Termine ; avec `save` vrai, produit le FIT puis passe à `FINISHED` |
| `skip_block` | `{}` | Équivalent de l'appui long + en ERG, pour le clavier ou le menu |

**Événements du Click.** Hors séance (`IDLE`, `READY`), le core transmet les boutons à l'engine pour qu'il pilote le menu : `type: "input"`, `event` parmi `PLUS_SHORT`, `MINUS_SHORT`, `PLUS_LONG`, `MINUS_LONG`. Pendant `RUNNING`, le core les consomme lui-même (braquet, biais, saut de bloc, pause). Un événement `input` perdu n'est pas rejoué : sur localhost la perte est négligeable et un appui de menu manqué se refait.

## 5. Messages de session : hello, heartbeat, fin

| Message | Sens | Champs | Rôle |
| --- | --- | --- | --- |
| `hello` | engine vers core | `v`, `engine_version` | Premier message de l'engine, répété chaque seconde jusqu'au `hello_ack` |
| `hello_ack` | core vers engine | `v`, `core_version`, `config` (pour l'affichage : `ftp_w`, `gears_total`, `theme`) | Confirme la version du contrat et donne la configuration utile |
| `heartbeat` | engine vers core | `seq`, `fps` (nombre, facultatif) | À 2 Hz ; prouve que l'engine est vivant |
| `error` | core vers engine | `code`, `message` | Erreur à afficher (voir codes ci-dessous) |
| `bye` | engine vers core | — | L'engine se ferme volontairement |
| `shutdown` | core vers engine | — | Le core se ferme : l'engine quitte ou revient à l'écran d'attente |

**Codes d'erreur :** `version_mismatch` (versions majeures différentes), `route_not_found`, `route_invalid`, `workout_invalid`, `trainer_control_refused`, `recording_failed`.

**Version.** Le core refuse un `hello` dont `v` diffère du sien, répond par une erreur `version_mismatch` et n'ouvre pas la séance. La règle d'évolution est au §8.

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
| Échec d'écriture du journal | Exception d'écriture | Erreur `recording_failed`, pause | Affiche le message |

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

**Séquence nominale**

| Étape | Sens | Message ou événement |
| --- | --- | --- |
| 1 | core | Démarre, se connecte au trainer et au Click, émet `state` avec `session_state` = `IDLE` |
| 2 | engine vers core | `hello` |
| 3 | core vers engine | `hello_ack` |
| 4 | core vers engine | `input` (menu piloté au Click ou au clavier) |
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
