# Lot X6 – Trainer simulé réaliste

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : Trainer simulé réaliste : frein du 1er ordre à retard, volant d'inertie, gigue des notifications | Python | X5 | Moyenne | **Livré le 28 octobre** (branche `claude/project-thread-818r6t-x6`, sur X35) ; issue #204 |

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

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x6`, sur X35 pour la vitesse imposée).

- **`ble_sim.TrainerResponse`** : frein du 1er ordre à retard pur, serrage plus rapide que relâchement, volant d'inertie, cycliste qui tient sa cadence à braquet fixe sans dépasser `rider_max_w`, effort de la route en SIM avec la pente, le Crr, le Cw et le vent lus dans la trame SIM (le trainer simulé lit maintenant les quatre champs). `SimTrainer(response="realiste")` l'utilise ; `instant` reste le défaut, sans changement de comportement (même tirage du hasard du monde).
- **Préréglage** (`ble_sim.REALISTE`) : retard 0,6 s, serrage 2 s, relâchement 4,9 s (90 % vers 12 s), volant 0,6 kg·m², gigue de 40 ms. `calibration` (`steps.csv` du lot X5) remplace retard et constantes de temps ; un fichier sans palier montant et descendant mesurés est refusé à la validation du scénario.
- **Scénarios** : scénario du core `realiste` (`--sim-scenario realiste`) ; protocoles du banc de paliers `marche_pente`, `erg_paliers` et `rogue_fenetres` (`trainer_steps --mode`), qui sont des suites de consignes et non des scénarios d'appareils.
- **Vérification** : `trainer_steps --trainer sim --response realiste [--calibration steps.csv]` compare chaque t63 au modèle (écriture de la consigne + retard + constante de temps + une trame pour la moyenne glissante de l'analyse), code 1 au-delà de ± 20 % (jamais moins de deux trames, la résolution de la mesure) ; en `--fast`, paliers de 20 s au plus pour laisser le relâchement finir. Mesuré dans le conteneur : ERG 150 → 250 → 150 W, t63 2,77 s et 5,78 s (t90 du relâchement 12,2 s) ; pente 0 → 7 → 0 %, t63 2,79 s et 5,64 s, tous à moins de 10 % du modèle.
- Tests : `core/tests/test_ble_sim_realiste.py` (10 tests : t63 à ± 10 % du retard + τ en ERG, retard pur, relâchement plus lent et à 90 % vers 12 s, effort de la route en SIM, cycliste plafonné, volant, calibration, validation, trame SIM, mode `instant` inchangé) ; `test_trainer_steps.py` (banc sur le modèle réaliste à ± 20 %, protocoles).

