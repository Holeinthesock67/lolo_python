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
| `rafale_0x80` | Rafale de braquets (séance A du 28 octobre) : Control Point occupé 0,6 s après chaque réponse (`busy_window_s`), écritures rapprochées refusées avec l'erreur ATT 0x80 ; cinq « − » en 6 s à 10 s, cinq « + » en 1 s à 25 s. Liaison gardée, aucune pause. |
| `montre_garmin` | Montre Garmin sur le trainer (séance A du 28 octobre) : toute écriture refusée (ATT 0x80) 8 s à 15 s puis 6 s à 40 s, braquets changés pendant ce temps. Consignes reportées, liaison gardée, `devices.trainer.busy` vrai (bandeau de l'engine). |
| `frein_lache` | Le trainer lâche le frein sans aucune erreur (séance du 29 octobre) : relances à 320 W, puissance annoncée nulle pendant 4 s à 20 s ; une nouvelle prise de contrôle rend le frein. Le pilote détecte la chute, reprend le contrôle et renvoie la consigne. |
| `connexions_retardees` | Trainer : 4 s de connexion et deux échecs ; Click : 2 s ; ceinture : 3 s et un échec. |
| `coupures` | Trainer coupé à 30 s, Click « − » à 40 s (réveillé à 50 s), ceinture à 45 s, trainer muet 12 s à 70 s, contrôle FTMS retiré à 100 s. |
| `controle_refuse` | Le trainer refuse le contrôle à partir de 10 s : la séance passe en ERROR après deux reprises. |
| `realiste` | Tout se connecte en une seconde ; trainer à réponse réaliste (lot X6, voir plus bas). |
| `pignon_unique` | Séance du 29 octobre, en valeurs génériques (lot X46) : trainer réaliste, cycliste à braquet réel 50 × 14 (pignon unique, grand plateau) à 85 rpm, soit ≈ 38 km/h au volant, au plus 600 W. La cadence annoncée suit le volant : dans une pente trop dure, elle baisse. |
| `decrochage_trainer` | Même braquet ; relances à 100 rpm de 25 à 45 s et de 85 à 105 s ; décrochages du frein (`brake_loss`, 8 s) à 33 s, 93 s et 160 s : puissance annoncée qui tombe vers 0 W en moins de 2 s, vitesse du volant qui baisse, cadence inchangée, sans erreur ni reconnexion. Le rapport `decrochages` les classe « indéterminé » : une cadence gardée ne prouve rien (lot X49) ; avec le repère Z long du cycliste (lot X47), « trainer ». |

## Écrire un scénario (JSON)

```json
{
  "seed": 0,
  "trainer": {"appear_at": 2, "connect_delay_s": 0.5},
  "rider": {"strategy": "constante", "watts": 200, "cadence_rpm": 90},
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

Une section absente retire l'appareil. `control_file` (facultatif, chemin) : fichier suivi pendant la séance, une ligne JSON par événement appliqué tout de suite, sans `t` (par exemple `{"action": "press", "button": "A", "duration_s": 1.1}`) ; le banc des menus (`engine/tests/menu_bench.py`) y écrit ses appuis du Click. Les temps sont en secondes depuis le lancement du core. Une clé ou une action inconnue est refusée au lancement, avec un message clair.

**Réglages communs** (`trainer`, `click`, `click.plus`, `click.minus`, `hr`, `hr_watch`) : `appear_at` (s), `connect_delay_s`, `connect_failures` (connexions refusées avant la première réussie), `asleep`, `address` (sauf `click`).

- **trainer :** `name`, `ibd_hz`, `erg_tau_s`, `cp_latency_s`, `power_range` ([min, max, pas]), `refuse_control`, `busy_window_s` (Control Point encore occupé ce temps après chaque réponse : erreur ATT 0x80 aux écritures rapprochées) ; réponse du trainer (lot X6) : `response` (`instant` par défaut, `realiste`), puis pour `realiste` seulement `brake_delay_s`, `brake_tau_up_s`, `brake_tau_down_s`, `flywheel_kg_m2`, `notify_jitter_s`, `rider_max_w` et `calibration` (chemin d'un `steps.csv` du banc de paliers).
- **rider** (cycliste virtuel qui pédale sur le trainer, `core/src/openride_core/sim_rider.py`, lot X27 ; absente : 180 W et 88 rpm) : `strategy` et ses réglages, `seed` (bruit déterministe) :
  - `constante` (défaut) : `watts`, `cadence_rpm` ; un peu plus en montée (+4 % par point de pente) ;
  - `pente` : `ftp_w`, `pct_ftp` ; la puissance suit la pente reçue (+6 % par point, de 40 à 150 %) ;
  - `cadence` : comme `pente`, et la cadence est tenue entre `cadence_low` et `cadence_high` (80 et 95 rpm) par des appuis du Click simulé (un toutes les 2 s au plus) ;
  - `rampe` : `ramp_start_w`, `ramp_w_per_min` (20) ; le cycliste lâche (cadence 0) quand la puissance, ou la cible ERG du trainer, dépasse `ramp_fail_pct_ftp` % de la FTP (133) ; pour le test de FTP (O10) ;
  - `sprint` : comme `pente`, avec des sprints de `sprint_s` s (10) à `sprint_w` (2,5 × FTP) aux temps `sprint_at_s` ;
  - `fatigue` : `fatigue_pct_ftp` % de la FTP (110) tant que la réserve W′bal (`w_prime_j`, CP = FTP) le permet, puis `recover_frac` × CP (0,85) jusqu'à ce que la réserve remonte au-dessus de `resume_pct` % (30) ;
  - `vitesse` : `speed_kmh` ; la puissance qui tient cette vitesse sur la pente reçue, avec la physique du core (`sim_bench.py --speed-kmh`, lot X35).

  Braquet réel (lot X46), pour toutes les stratégies : `chainring` et `sprocket` (dents, ensemble) et `wheel_m` (circonférence, 2,105 m). Le cycliste roule à braquet fixe sur un trainer à entraînement direct à pignon unique : avec le trainer réaliste, la vitesse du volant visée est celle de sa cadence à ce braquet, et la cadence annoncée suit le volant (elle baisse quand le frein bat le cycliste).

  En ERG, le trainer tient sa cible tant que le cycliste pédale (cadence non nulle).

**Trainer réaliste (lot X6).** En réponse `instant`, la puissance rejoint la consigne ERG ou l'effort du cycliste avec la constante `erg_tau_s` (1,5 s) et la pente ne change pas la résistance. En `realiste` (`ble_sim.TrainerResponse`) :
- le frein voit la consigne avec un retard pur (`brake_delay_s`, 0,6 s) puis la rejoint en `brake_tau_up_s` (2 s) quand l'effort monte et en `brake_tau_down_s` (4,9 s) quand il baisse : 90 % du relâchement vers 12 s, comme à l'essai du 25 octobre ;
- en ERG, la force du frein est la cible divisée par la vitesse ; en SIM, l'effort de la route à la vitesse du volant : m g (sin θ + Crr cos θ) + ½ Cw (v + vent)² (Cw = ρ · CdA, comme dans ANT+ FE-C et FTMS), avec la pente, le Crr, le Cw et le vent de la trame SIM (masse et valeurs absentes : réglages par défaut du core) ;
- le volant (`flywheel_kg_m2`, 0,6, ramené à la jante) relie l'effort et la vitesse ; le cycliste tient sa cadence à braquet fixe (vitesse de sa cadence au braquet réel `chainring` × `sprocket`, sinon vitesse de son effort sur le plat, ou `speed_kmh` de la stratégie `vitesse`) sans dépasser `rider_max_w` (2,5 fois l'effort du cycliste par défaut) : dans une montée trop raide pour lui, le volant ralentit ;
- la puissance envoyée est celle du cycliste (frein et accélération du volant), la vitesse celle du volant ;
- les trames Indoor Bike Data partent à `ibd_hz` avec une gigue de ± `notify_jitter_s` (40 ms), tirée à part du hasard du monde.

Banc du trainer sur le simulé : `trainer_steps --trainer sim --scenario decrochage_trainer --mode relances` prend le braquet du scénario (ou `--plateau`/`--pignon`, transmis au cycliste simulé avec `--cadence`) et déroule ses événements.

`calibration` remplace le retard et les constantes de temps par ceux d'un essai réel (`trainer_steps`, lot X5) : τ = (t63 − t10) / 0,895 et retard = t63 − τ, médianes des paliers montants et descendants. Vérification : `python -m openride_core.tools.trainer_steps --trainer sim --response realiste --mode erg_paliers` compare chaque t63 au modèle (± 20 %).
- **click :** `status_hz`, `battery_pct`, `sleep_on_drop`, `relay_delay_s` ([min, max]).
- **hr** et **hr_watch :** `name`, `rest_bpm`, `max_bpm`, `ftp_w`, `tau_s`, `bpm` (valeur fixe), `contact` (vrai par défaut ; faux : contact absent ; null : non géré), `battery_pct` (0 à 100 ; null : pas de service Battery), `rssi`.

**Événements** (`device` : `trainer`, `click_plus`, `click_minus`, `hr`, `hr_watch` ; `trainer` par défaut) :

| Action | Paramètres | Effet |
| --- | --- | --- |
| `press` | `button` (`+`, `-`, `A`, `B`, `Y`, `Z`, `LEFT`, `UP`, `RIGHT`, `DOWN` : boutons du Click V2), `duration_s` (0,12 par défaut) | Appui sur le Click : +, A, B, Y et Z sur le boîtier droit (`click_plus`), − et flèches sur le gauche (`click_minus`) ; un « + » est relayé par le « − ». |
| `drop` | | Coupure du lien côté appareil. |
| `wake`, `sleep` | | L'appareil s'annonce, ou plus (et refuse les connexions). |
| `connect_failures` | `count` | Les prochaines connexions échouent. |
| `connect_delay` | `seconds` | Durée des prochaines connexions. |
| `att_error` | `code` (128 = 0x80), `count` | Les prochaines écritures du Control Point échouent. |
| `cp_silent` | `count` | Les prochaines commandes restent sans réponse 0x80. |
| `brake_loss` | `seconds`, `value` (vrai par défaut : une nouvelle prise de contrôle rend le frein) | Trainer : frein lâché (séance du 29 octobre) pendant ce temps. La puissance annoncée tombe vers 0 W (divisée par e en 0,5 s) et la vitesse du volant baisse (constante de 8 s, lot X46). Cadence, Control Point et liaison restent inchangés, sans statut ni erreur. |
| `other_device` | `seconds` | Trainer : un autre appareil (montre) occupe le Control Point, toute écriture échoue avec l'erreur ATT 0x80 pendant ce temps. |
| `silence` | `seconds` | Trainer : plus d'Indoor Bike Data pendant ce temps. Boîtier du Click (`click_plus`, `click_minus`) : plus aucune notification, lien gardé (défaut du boîtier gauche à l'essai 69, recette guidée du Click, lot X8). |
| `control_lost` | | Fitness Machine Status 0xFF : contrôle retiré. |
| `refuse_control` | `value` (vrai par défaut) | Les demandes de contrôle sont refusées (0x05). |
| `rider` | `watts`, `cadence_rpm` | Effort du cycliste virtuel (`watts` : stratégie `constante` ; `cadence_rpm` 0 : arrêt de pédalage). |
| `bpm` | `bpm` (null : suit la puissance) | Fréquence de la ceinture. |
| `contact` | `value` (vrai par défaut, faux : absent, null : non géré) | Contact du capteur de la ceinture (ou de la montre). |

## Rejouer une panne vue sur le vélo

Après une coupure ou une erreur sur le vélo, `tools/log_scenario.py` (lot M5) convertit le journal du core en scénario : mêmes connexions, coupures, erreurs ATT, pertes de contrôle et appuis du Click, aux mêmes instants (secondes depuis « Core démarré »).

```bash
cd core && python -m openride_core.tools.log_scenario -o ~/panne.json          # dernière séance de ~/run_trainer.log
python -m openride_core.tools.log_scenario ~/run_trainer.log --session 2 --from 60 --to 180 -o ~/panne.json
cd .. && scripts/openride-dev.sh --trainer sim --input sim --hr sim --sim-scenario ~/panne.json --autostart
```

Correspondances : première connexion d'un appareil → `appear_at` ; « Reconnexion au trainer » → `drop` (sauf juste après « plus de données du trainer », qui devient un `silence` commencé 10 s plus tôt) ; erreur ATT lue (« ATT error: 0xNN » ou « renvoi ») → `att_error` avec son code ; « contrôle FTMS perdu » et commande refusée → `control_lost` (`refuse_control` si la séance a fini sur un refus du contrôle) ; coupure d'un boîtier du Click → `drop` sur `click_plus` (adresse `click_address` de la configuration, `--config`, sinon celle du « + » simulé) ou `click_minus`, puis `wake` avant sa reconnexion ; appuis → `press` (long : 1 s) ; ceinture connectée puis coupée → `drop`. Le reste (pauses, mesures `Perf`, transitions) est ignoré et compté dans le résumé écrit sur la sortie d'erreur. Le format de scénario n'a pas de clé pour l'origine : elle est écrite dans `description`.

## Tests automatiques

`core/tests/test_sim_matrix.py` (lot M6, marqué `slow`) joue chaque scénario de `SCENARIOS` en séance complète `CoreSession`, en ERG (`.zwo` court) et en SIM, pendant la durée du scénario plus 10 s (au plus 130 s), chaque séance dans son processus, en parallèle (~2 min 30 en tout) ; il vérifie l'absence d'erreur inattendue, l'état final (`FINISHED`, `ERROR` pour `controle_refuse`), le FIT (SDK Garmin, autant d'échantillons que de lignes `record`), la relâche du trainer (pente 0 % puis Reset), les bornes des consignes, la lecture par `summary` et `log_report`, et une table d'attentes propre à chaque scénario. Un scénario ajouté à `SCENARIOS` est joué sans modifier le test.

`core/tests/test_log_scenario.py` (lot M5) convertit des journaux d'exemple (deux boîtiers du Click, anciens formats, fenêtre, choix de séance, journaux inutilisables), charge le scénario produit dans une séance de 20 s, et fait l'aller-retour séance `coupures` → journal → scénario (marqué `slow`, ~105 s).

`core/tests/test_hr_monitor.py` (lot M2) vérifie le décodage complet de 0x2A37, le contact absent puis retrouvé, le choix de la ceinture face à une montre, `hr_name`, `hr_address` et la batterie faible avec la ceinture et la montre simulées.

`core/tests/test_ble_sim.py` rejoue ces comportements par de courts scénarios (quelques secondes chacun) dans la CI : règles du Control Point, ERG et SIM, relâche à l'arrêt, erreur ATT 0x80 suivie d'un renvoi sans reconnexion (une ou deux erreurs de suite ; à la troisième, Control Point occupé : consigne reportée avec un délai croissant, liaison gardée ; reconnexion pour un autre code ATT), écriture qui attend la réponse d'une procédure lente et erreur 0xFE renvoyée après cette réponse, Control Point occupé par une montre (liaison gardée, seule la dernière pente écrite), cible ERG gardée sans Reset ni pente 0 %, rafale de braquets sur un Control Point lent, liaison coupée pendant une écriture (reconnexion sans renvoi), lecture du code ATT dans les messages de BlueZ, scénario `erreur_0x80` en séance complète (lot M1, marqué `slow`), contrôle perdu puis repris, contrôle refusé, réveil tardif et connexion refusée, coupure et silence du trainer, relais et appuis longs du Click, Click endormi, ceinture, et une séance complète `CoreSession` sans matériel.

**Défaut trouvé à la mise en place :** quand le trainer refuse une consigne (0x05) ou annonce la perte du contrôle (0xFF) pendant une écriture, `FtmsDriver` effaçait la consigne envoyée puis la réécrivait au retour de l'écriture : la reprise de contrôle n'avait jamais lieu et la séance finissait en ERROR après trois refus. Corrigé (`_forget_sent`).

**Ce que le simulateur ne dit pas :** les délais réels de BlueZ, la qualité radio, le comportement exact du HomeTrainer (latence de la résistance, réponse à un Reset refusé) et la mise en veille du Click après de longues minutes restent à vérifier sur le matériel.
