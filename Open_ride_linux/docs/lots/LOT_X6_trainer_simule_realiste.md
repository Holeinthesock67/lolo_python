# Lot X6 – Trainer simulé réaliste

## 1. Objectif

Le trainer simulé de `ble_sim.py` répond presque tout de suite : la puissance suit la consigne ERG avec une constante de temps de 1,5 s, et en SIM la pente ne change rien à la résistance ressentie. Les tests au cloud ne voient donc ni le relâchement du frein (10 à 15 s mesurés à l'essai 69), ni l'inertie du volant, ni le retard des notifications. Les séries T et R (fenêtres de timing de 1,5 s) en ont besoin.

## 2. À lire

`core/src/openride_core/ble_sim.py` (`SimTrainer`, `_data_loop`, `_rider_power`), `sim_scenarios.py` (clés du trainer), `docs/SIMULATION_BLE.md`, `core/src/openride_core/tools/trainer_steps.py` (mesures X5 : t10, t63, t90), `physics.py`.

## 3. Travail demandé

- **Modèle de réponse** dans `SimTrainer`, choisi par la clé `response` du scénario : `instant` (comportement actuel, défaut pour ne rien casser) ou `realiste` : frein du 1er ordre avec retard pur (`brake_delay_s`, `brake_tau_up_s`, `brake_tau_down_s` : serrage plus rapide que relâchement), volant d'inertie (`flywheel_kg_m2`) qui relie couple et vitesse de rotation, effet de la résistance de l'air ajoutée par le trainer en SIM (`cw` reçu dans la trame SIM), notifications à `ibd_hz` avec gigue (`notify_jitter_s`).
- **Préréglage** `"response": "realiste"` calé sur les valeurs moyennes de l'essai 69 (relâchement 12 s) ; un fichier `calibration` facultatif (`--calibration steps.csv` de X5) remplace ces valeurs par celles mesurées. Aucune marque ni numéro de série dans le dépôt.
- **Scénarios** : `marche_pente` (0 → 7 → 0 %), `erg_paliers` (150 → 250 → 150 W), `rogue_fenetres` (consignes de 1,5 s).
- **Vérification** : `trainer_steps --trainer sim --response realiste --fast` retrouve à ± 20 % les t63 du modèle.

## 4. Fichiers

- **Modifiés :** `ble_sim.py`, `sim_scenarios.py`, `tools/trainer_steps.py` (option `--response`), `docs/SIMULATION_BLE.md`, `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `core/tests/test_ble_sim_realiste.py`.

## 5. Critères d'acceptation

1. Réponse à une marche : t63 à ± 10 % de `brake_tau_*`, retard pur respecté, relâchement plus lent que le serrage.
2. Mode `instant` inchangé : toute la suite core passe sans retouche.
3. `trainer_steps` sur le modèle réaliste mesure les valeurs du modèle (± 20 %).

## 6. Hors périmètre

Le cycliste qui réagit (X27), le réglage du lissage de pente (Q4).
