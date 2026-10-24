# Bluetooth simulé : HomeTrainer, Zwift Click et ceinture cardio sans matériel

Ajout du 24 octobre 2026. Code : `core/src/openride_core/ble_sim.py` (appareils) et `core/src/openride_core/sim_scenarios.py` (scénarios). Tests : `core/tests/test_ble_sim.py`.

## Principe

`--trainer mock` remplace le pilote du trainer par un générateur de puissance. Le mode `sim` garde les **vrais pilotes** (`FtmsDriver`, `ZwiftClickProvider`, `HeartRateProvider`) et remplace seulement la radio : recherche, connexion, abonnements, écritures et notifications passent par des appareils simulés. Ce qui marche en `sim` a donc de bonnes chances de marcher sur le vélo, et les pannes vues aux essais se rejouent à la demande.

Les trois options sont indépendantes : `--trainer sim --input click` garde le vrai Click avec un trainer simulé, par exemple.

```bash
scripts/openride-dev.sh --trainer sim --input sim --hr sim --autostart                         # scénario demo
scripts/openride-dev.sh --trainer sim --input sim --hr sim --sim-scenario reveil_tardif --autostart
openride-core run --trainer sim --input sim --hr sim --sim-scenario ~/mon_scenario.json --autostart
```

Dans `config.toml`, section `[drivers]` : `trainer = "sim"`, `input = "sim"`, `hr = "sim"`, `sim_scenario = "coupures"`.

## Ce qui est simulé

| Appareil | Comportement |
| --- | --- |
| HomeTrainer (FTMS) | Nom « HomeTrainer 0000 (sim) ». Fitness Machine Feature (SIM et ERG), plage de puissance 0 à 2000 W. Control Point : une procédure à la fois (erreur ATT 0xFE si l'on écrit avant la réponse 0x80), 0xFD sans abonnement aux indications, 0x05 sans contrôle, « Start/Resume » refusé quand il tourne déjà, Reset qui rend le contrôle, Fitness Machine Status (0x08, 0x12, 0xFF). Indoor Bike Data à 4 Hz ; en ERG la puissance rejoint la cible en ~1,5 s ; en SIM le cycliste pousse un peu plus en montée. |
| Zwift Click | Deux boîtiers « Zwift Click » (« + » à l'adresse réelle `C1:1C:00:00:00:01`, « − » à `…:E8`). Handshake `RideOn`, niveau de batterie, état des touches (type 0x23) à 10 Hz. Le « − » relaie les appuis du « + » 5 à 40 ms plus tard. Un boîtier endormi ne s'annonce qu'après un appui, et cet appui est perdu ; après une coupure il se rendort. |
| Ceinture cardio | Service Heart Rate (0x180D), une mesure par seconde, fréquence qui suit la puissance du trainer simulé avec ~20 s de retard ; bit de contact du capteur, intervalle RR cohérent avec la fréquence, niveau de batterie (service 0x180F, 80 % par défaut), RSSI annoncé (lot M2). |
| Montre qui diffuse (`hr_watch`, facultative) | Même appareil que la ceinture, nommé « Forerunner 265 (sim) » (adresse `C0:FF:EE:00:57:A7`, RSSI −50 par défaut) : sert à vérifier que la ceinture est préférée à une montre Garmin qui diffuse sa fréquence. |

Avec `--input sim`, le clavier du terminal du core (`+`, `-`, `u`, `d`) appuie sur le Click simulé ; un appui sur un boîtier endormi ou déconnecté est perdu, comme sur le vrai. `openride-dev.sh` détache le core du terminal : les appuis viennent alors du scénario (le scénario `demo` en contient).

## Scénarios intégrés

| Nom | Ce qu'il rejoue |
| --- | --- |
| `demo` (défaut) | Tout se connecte en une seconde ; appuis courts toutes les 6 s, deux appuis longs, effort du cycliste variable. |
| `nominal` | Tout se connecte en une seconde, aucun événement. |
| `reveil_tardif` | Trainer allumé à 6 s, ceinture à 10 s, boîtiers du Click réveillés par un appui (perdu) à 15 s et 25 s. |
| `erreur_0x80` | Une écriture du Control Point échoue avec l'erreur ATT 0x80 à 20 s (vue le 24 octobre). Depuis le lot M1, le pilote renvoie la commande 0,25 s plus tard, sans couper la liaison. |
| `connexions_retardees` | Trainer : 4 s de connexion et deux échecs ; Click : 2 s ; ceinture : 3 s et un échec. |
| `coupures` | Trainer coupé à 30 s, Click « − » à 40 s (réveillé à 50 s), ceinture à 45 s, trainer muet 12 s à 70 s, contrôle FTMS retiré à 100 s. |
| `controle_refuse` | Le trainer refuse le contrôle à partir de 10 s : la séance passe en ERROR après deux reprises. |

## Écrire un scénario (JSON)

```json
{
  "seed": 0,
  "trainer": {"appear_at": 2, "connect_delay_s": 0.5, "rider_power_w": 200, "cadence_rpm": 90},
  "click": {"appear_at": 3, "relay_delay_s": [0.005, 0.04], "minus": {"connect_failures": 1}},
  "hr": {"appear_at": 1, "rest_bpm": 58},
  "events": [
    {"t": 10, "action": "press", "button": "+"},
    {"t": 12, "action": "press", "button": "-", "duration_s": 1.0},
    {"t": 20, "device": "trainer", "action": "att_error", "code": 128},
    {"t": 40, "device": "click_minus", "action": "drop"},
    {"t": 60, "device": "trainer", "action": "rider", "watts": 260}
  ]
}
```

Une section absente retire l'appareil. Les temps sont en secondes depuis le lancement du core. Une clé ou une action inconnue est refusée au lancement, avec un message clair.

**Réglages communs** (`trainer`, `click`, `click.plus`, `click.minus`, `hr`, `hr_watch`) : `appear_at` (s), `connect_delay_s`, `connect_failures` (connexions refusées avant la première réussie), `asleep`, `address` (sauf `click`).

- **trainer :** `name`, `ibd_hz`, `rider_power_w`, `cadence_rpm`, `erg_tau_s`, `cp_latency_s`, `power_range` ([min, max, pas]), `refuse_control`.
- **click :** `status_hz`, `battery_pct`, `sleep_on_drop`, `relay_delay_s` ([min, max]).
- **hr** et **hr_watch :** `name`, `rest_bpm`, `max_bpm`, `ftp_w`, `tau_s`, `bpm` (valeur fixe), `contact` (vrai par défaut ; faux : contact absent ; null : non géré), `battery_pct` (0 à 100 ; null : pas de service Battery), `rssi`.

**Événements** (`device` : `trainer`, `click_plus`, `click_minus`, `hr`, `hr_watch` ; `trainer` par défaut) :

| Action | Paramètres | Effet |
| --- | --- | --- |
| `press` | `button` (`+` ou `-`), `duration_s` (0,12 par défaut) | Appui sur le Click, relayé par le « − » pour un « + ». |
| `drop` | | Coupure du lien côté appareil. |
| `wake`, `sleep` | | L'appareil s'annonce, ou plus (et refuse les connexions). |
| `connect_failures` | `count` | Les prochaines connexions échouent. |
| `connect_delay` | `seconds` | Durée des prochaines connexions. |
| `att_error` | `code` (128 = 0x80), `count` | Les prochaines écritures du Control Point échouent. |
| `cp_silent` | `count` | Les prochaines commandes restent sans réponse 0x80. |
| `silence` | `seconds` | Plus d'Indoor Bike Data pendant ce temps. |
| `control_lost` | | Fitness Machine Status 0xFF : contrôle retiré. |
| `refuse_control` | `value` (vrai par défaut) | Les demandes de contrôle sont refusées (0x05). |
| `rider` | `watts`, `cadence_rpm` | Effort du cycliste en SIM (0 : arrêt de pédalage). |
| `bpm` | `bpm` (null : suit la puissance) | Fréquence de la ceinture. |
| `contact` | `value` (vrai par défaut, faux : absent, null : non géré) | Contact du capteur de la ceinture (ou de la montre). |

## Rejouer une panne vue sur le vélo

Après une coupure ou une erreur sur le vélo, `tools/log_scenario.py` (lot M5) convertit le journal du core en scénario : mêmes connexions, coupures, erreurs ATT, pertes de contrôle et appuis du Click, aux mêmes instants (secondes depuis « Core démarré »).

```bash
cd core && python -m openride_core.tools.log_scenario -o ~/panne.json          # dernière séance de ~/run_trainer.log
python -m openride_core.tools.log_scenario ~/run_trainer.log --session 2 --from 60 --to 180 -o ~/panne.json
cd .. && scripts/openride-dev.sh --trainer sim --input sim --hr sim --sim-scenario ~/panne.json --autostart
```

Correspondances : première connexion d'un appareil → `appear_at` ; « Reconnexion au trainer » → `drop` (sauf juste après « plus de données du trainer », qui devient un `silence` commencé 10 s plus tôt) ; erreur ATT lue (« ATT error: 0xNN » ou « renvoi ») → `att_error` avec son code ; « contrôle FTMS perdu » et commande refusée → `control_lost` (`refuse_control` si la séance a fini sur un refus du contrôle) ; coupure d'un boîtier du Click → `drop` sur `click_plus` (adresse du « + », `…E1:E7`) ou `click_minus`, puis `wake` avant sa reconnexion ; appuis → `press` (long : 1 s) ; ceinture connectée puis coupée → `drop`. Le reste (pauses, mesures `Perf`, transitions) est ignoré et compté dans le résumé écrit sur la sortie d'erreur. Le format de scénario n'a pas de clé pour l'origine : elle est écrite dans `description`.

## Tests automatiques

`core/tests/test_sim_matrix.py` (lot M6, marqué `slow`) joue chaque scénario de `SCENARIOS` en séance complète `CoreSession`, en ERG (`.zwo` court) et en SIM, pendant la durée du scénario plus 10 s (au plus 130 s), chaque séance dans son processus, en parallèle (~2 min 30 en tout) ; il vérifie l'absence d'erreur inattendue, l'état final (`FINISHED`, `ERROR` pour `controle_refuse`), le FIT (SDK Garmin, autant d'échantillons que de lignes `record`), la relâche du trainer (pente 0 % puis Reset), les bornes des consignes, la lecture par `summary` et `log_report`, et une table d'attentes propre à chaque scénario. Un scénario ajouté à `SCENARIOS` est joué sans modifier le test.

`core/tests/test_log_scenario.py` (lot M5) convertit des journaux d'exemple (deux boîtiers du Click, anciens formats, fenêtre, choix de séance, journaux inutilisables), charge le scénario produit dans une séance de 20 s, et fait l'aller-retour séance `coupures` → journal → scénario (marqué `slow`, ~105 s).

`core/tests/test_hr_monitor.py` (lot M2) vérifie le décodage complet de 0x2A37, le contact absent puis retrouvé, le choix de la ceinture face à une montre, `hr_name`, `hr_address` et la batterie faible avec la ceinture et la montre simulées.

`core/tests/test_ble_sim.py` rejoue ces comportements par de courts scénarios (quelques secondes chacun) dans la CI : règles du Control Point, ERG et SIM, relâche à l'arrêt, erreur ATT 0x80 suivie d'un renvoi sans reconnexion (une ou deux erreurs de suite ; reconnexion à la troisième), erreur 0xFE renvoyée après la réponse de la procédure en cours, liaison coupée pendant une écriture (reconnexion sans renvoi), lecture du code ATT dans les messages de BlueZ, scénario `erreur_0x80` en séance complète (lot M1, marqué `slow`), contrôle perdu puis repris, contrôle refusé, réveil tardif et connexion refusée, coupure et silence du trainer, relais et appuis longs du Click, Click endormi, ceinture, et une séance complète `CoreSession` sans matériel.

**Défaut trouvé à la mise en place :** quand le trainer refuse une consigne (0x05) ou annonce la perte du contrôle (0xFF) pendant une écriture, `FtmsDriver` effaçait la consigne envoyée puis la réécrivait au retour de l'écriture : la reprise de contrôle n'avait jamais lieu et la séance finissait en ERROR après trois refus. Corrigé (`_forget_sent`).

**Ce que le simulateur ne dit pas :** les délais réels de BlueZ, la qualité radio, le comportement exact du HomeTrainer (latence de la résistance, réponse à un Reset refusé) et la mise en veille du Click après de longues minutes restent à vérifier sur le matériel.
