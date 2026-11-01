# Lot X46 – Trainer simulé : braquet réel à pignon unique et décrochages du frein

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : trainer simulé à braquet réel (pignon unique, grand plateau), action `brake_loss` (décrochage du frein), scénarios `pignon_unique` et `decrochage_trainer`, `trainer_steps --scenario` | Python | X43, X44 | Petite | Livré le 29 octobre (PR #590) |

## 1. Objectif

Séance du 29 octobre : le cycliste roulait sur le grand plateau, sur un trainer à entraînement direct à pignon unique. Le volant tournait vite et l'effort de la route en SIM était lourd même sur le plat. Après une relance, la puissance annoncée tombait vers 0 W en moins de 2 s alors que la cadence restait la même. Le trainer simulé ne savait reproduire ni l'un ni l'autre : son cycliste tenait la vitesse de son effort sur le plat, sans braquet.

Le passage à ½ · Cw · v² (Cw = ρ · CdA) dans le trainer simulé est fait par le fil FTMS (#582). Ce lot ne touche pas à cette formule.

## 2. Spécification

| # | Règle |
| --- | --- |
| X46-1 | `physics.gear_speed_mps(cadence, plateau, pignon, roue)` et sa réciproque `gear_cadence_rpm`. `WHEEL_CIRCUMFERENCE_M` = 2,105 m. Le `Gearing` de `trainer_steps` (lot X43) s'en sert. |
| X46-2 | Section `rider` d'un scénario : `chainring` et `sprocket` (ensemble, > 0), `wheel_m` (> 0). Une erreur donne `SimScenarioError`. |
| X46-3 | Trainer réaliste avec braquet réel : la vitesse visée est celle de la cadence au braquet. La cadence annoncée suit le volant : elle baisse quand le cycliste (au plus `rider_max_w`) ne tient plus l'effort demandé. |
| X46-4 | Action `brake_loss` (ajoutée par le fil FTMS dans #580 : `seconds`, et `value` pour dire si une nouvelle prise de contrôle rend le frein). Pendant ce temps, la puissance annoncée ne passe plus d'un coup à 0 W : elle y tombe avec une constante de 0,5 s, et la vitesse du volant baisse avec une constante de 8 s. La cadence, le Control Point et la liaison ne changent pas. |
| X46-5 | Scénarios `pignon_unique` (50 × 14 à 85 rpm, au plus 600 W) et `decrochage_trainer` (relances à 100 rpm, trois décrochages de 8 s). Les valeurs sont génériques : ni modèle de trainer, ni poids, ni FTP. |
| X46-6 | `trainer_steps --scenario NOM` sur le trainer simulé. L'outil prend le braquet du scénario quand `--plateau` et `--pignon` manquent. Sinon il les transmet au cycliste simulé, avec `--cadence`. Il déroule les événements du scénario, et un scénario réaliste donne les paliers courts du modèle réaliste. |
| X46-7 | La trame Indoor Bike Data est construite par `SimTrainer.frame(t, dt)`, testable sans horloge réelle. `_data_loop` ne fait plus que l'envoyer. |

## 3. Fichiers

- `core/src/openride_core/physics.py` ;
- `core/src/openride_core/sim_rider.py` ;
- `core/src/openride_core/ble_sim.py` ;
- `core/src/openride_core/sim_scenarios.py` ;
- `core/src/openride_core/tools/trainer_steps.py` ;
- `core/tests/test_ble_sim_braquet.py` ;
- `docs/SIMULATION_BLE.md`, `docs/OUTILS_DE_TEST.md`.

## 4. Critères d'acceptation

1. `pytest` passe :
   - 50 × 14 à 85 rpm donne ≈ 38,3 km/h ;
   - à 10 % de pente, le cycliste plafonne à 600 W, et la cadence et la vitesse baissent ;
   - les trois décrochages de `decrochage_trainer` sont trouvés à 33, 93 et 160 s puis la puissance revient. Le lot X49 les classe « indéterminé » sans repère du cycliste, « trainer » avec.
2. `trainer_steps --trainer sim --scenario decrochage_trainer --mode relances --fast` va jusqu'au rapport. Le décrochage de 33 s y est classé « trainer ».
3. La matrice de simulation (M6) joue les deux nouveaux scénarios en ERG et en SIM sans erreur.

## 5. Hors périmètre

- La formule de l'effort aérodynamique : #582 (fil FTMS).
- La détection du décrochage dans le pilote FTMS : #580 (fil FTMS). Ces scénarios servent à la tester.

## Livraison

PR #590, fusionnée le 29 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Séance du 29 octobre ; en PR ».
