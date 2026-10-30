# Lot X49 – Corrections après les essais sur le PC des outils de décrochage (X43 à X47)

## 1. Objectif

Les essais du 30 octobre sur le PC (file 7an) ont relevé trois défauts dans les outils des lots X43 à X47.

1. `decrochages` classait « trainer » des relâchements du cycliste. Une cadence gardée ne prouve rien, puisqu'on peut tourner les jambes sans appuyer. Deux cas sur les relevés du 29 octobre :
   - 534 → 158 W sur le palier à 6 %, effort intenable que le cycliste a lâché ;
   - 188 → 44 W à 80 tr/min sur le plat, jambes à vide.
2. `trainer_steps --trainer sim --scenario decrochage_trainer --mode relances` sortait en code 1. Le t63 des retours à 150 W était comparé au modèle du frein alors que le palier d'avant avait été coupé par le plafond, ou qu'un décrochage venait d'avoir lieu : le départ n'était pas établi.
3. Il manquait `--renvoi S` pour le test du pompage avec et sans renvoi de la consigne (file 7ak). Le PC en avait une version locale.

## 2. Spécification

| # | Règle |
| --- | --- |
| X49-1 | Un relevé porte aussi la vitesse du volant et la pente envoyée : `speed_kmh` de `samples.csv` ou `speed` du journal ; pente du palier `sim`/`sim_w` ou `grade_sent` du journal en SIM. Une chute garde la variation du volant (médiane des 5 s d'après contre les 5 s d'avant), la pente, la durée de l'effort au-dessus de 450 W juste avant, et la raison du diagnostic. |
| X49-2 | Diagnostic, dans l'ordre :<br>1. `arret` ;<br>2. `fatigue` si la cadence tombe d'abord ;<br>3. `indetermine` si la cadence n'est pas restée stable ;<br>4. `trainer` seulement sur preuve : repère Z long à ± 10 s, Fitness Machine Status d'arrêt ou de remise à zéro (RESET, STOPPED_OR_PAUSED_BY_USER, STOPPED_BY_SAFETY_KEY, SPIN_DOWN_STATUS, CONTROL_PERMISSION_LOST) à ± 5 s, ou volant qui s'emballe de 5 % ou plus ;<br>5. `fatigue` après plus de 450 W tenus 8 s ou plus ;<br>6. `relachement` sous 250 W sur une pente à ± 1 % ;<br>7. sinon `indetermine`.<br>Une autre preuve s'ajoute après les essais 7av : le pilote voit le frein lâcher (« frein lâché ») et la puissance revient au plus 3 s après sa reprise du contrôle (« puissance revenue », #580). Un cycliste qui relâche ne repart pas pile à ce moment. Restent sans valeur de preuve : les échos de consigne (SIM_PARAMS_CHANGED…), et le « frein lâché » du pilote tout seul. Un volant qui s'effondre non plus : le frein l'arrête aussi quand le cycliste n'appuie plus. |
| X49-3 | `trainer_steps` ne compare au modèle simulé que les paliers dont le départ est établi. Les autres sont notés « pas comparé » avec leur raison : palier coupé par le plafond, palier qui en suit un, ou décrochage pendant le palier ou le précédent. Ils ne comptent pas dans le code de sortie. |
| X49-4 | `trainer_steps --renvoi S` règle `[trainer] resend_s` pour l'essai. `--renvoi 0` ne renvoie jamais une consigne inchangée : une seule écriture par palier. La valeur est notée dans `events.csv` (type `config`) et dans `rapport.html`. Une valeur négative est refusée (code 2). |

## 3. Fichiers

- `core/src/openride_core/tools/decrochages.py` et `tools/trainer_steps.py` ;
- `core/src/openride_core/sim_scenarios.py` (description de `decrochage_trainer`) ;
- `core/tests/test_decrochages.py`, `test_trainer_steps.py`, `test_ble_sim_braquet.py` ;
- `docs/OUTILS_DE_TEST.md`, `docs/SIMULATION_BLE.md`, cahier X46.

## 4. Critères d'acceptation

1. `pytest` passe :
   - les deux cas du 30 octobre donnent `fatigue` et `relachement` ;
   - une cadence gardée sans preuve donne `indetermine`, et avec le repère Z long, `trainer` ;
   - un écho de consigne ne prouve rien, mais SPIN_DOWN_STATUS prouve ;
   - les paliers sans départ établi ne sont pas comparés ;
   - `--renvoi 0` veut dire jamais.
2. `trainer_steps --trainer sim --scenario decrochage_trainer --mode relances --fast --renvoi 0` sort en code 0, avec une seule écriture SIM par palier.
3. Sur le PC (via le fil de fusion), `decrochages` est relancé sur `~/OpenRide/mesures/2026-10-29/paliers/`. Les deux relâchements du 29 octobre ne sont plus « trainer ».
