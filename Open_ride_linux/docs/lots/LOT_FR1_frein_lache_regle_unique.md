# Lot FR1 – Frein lâché : une seule règle, sans faux décrochage à l'arrêt du pédalage

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 1.x série FR : frein lâché jugé par une règle commune au pilote et au rapport des décrochages | Python | X44, X46 | Petite | **Livré le 19 novembre** (PR #923, remplace #902), **version 1.x** |

## 1. Objectif

Faux « frein lâché » vus au vélodrome (14 novembre, fin d'épreuve) et en Cyber-Rogue (15 novembre, fins de salle) :
le cycliste arrête net de pédaler, la puissance annoncée tombe aussitôt à 0 W, mais la cadence annoncée par le
trainer garde son ancienne valeur environ 1 s. Pendant cette seconde, l'arrêt ressemble exactement au frein lâché du
29 octobre (449 W puis 0 W à cadence constante). Le pilote reprenait alors le contrôle du trainer, écrivait « frein
lâché » au journal, puis « puissance revenue » quand le cycliste repartait, ce que le rapport des décrochages prenait
pour une preuve contre le trainer.

Le détecteur est dans le pilote (`ftms_driver.py`), sous tous les modes : la correction vaut pour la route, l'ERG, le
Cyber-Rogue, le vélodrome, le Grand Prix et le reste, sans exception par mode. Plan : fil global du 17 novembre.

## 2. Travail fait

- `core/src/openride_core/brake_watch.py` (module pur) : seule définition de la chute et des « pédales qui tournent
  encore », utilisée par le pilote et par `tools/decrochages.py`.
  - chute : sous 10 W moins de 3 s après le dernier relevé à 150 W ou plus (niveau d'avant : médiane des 3 s), volant
    à 15 km/h ou plus, consigne qui demande un effort ; plus de seuil fixe à 200 W (« lâchers vers 200 W ») ;
  - preuve : pendant 2 s (deux fois le retard de la cadence), chaque relevé reste sous 10 W avec une cadence d'au
    moins 40 tr/min et d'au moins 75 % de celle de la chute, sur au moins 2 relevés ; sans assez de relevés en 4 s,
    rien n'est conclu ; une chute n'est jugée qu'une fois (il faut repasser à 150 W) ;
  - « puissance revenue » seulement si les pédales n'ont jamais cessé de tourner depuis la reprise du contrôle ;
    sinon le journal du core dit « le cycliste a cessé de pédaler » et rien n'est écrit en ligne `ftms` ;
  - une reprise du contrôle au plus toutes les 10 s, comme avant.
- `ftms_driver.py` : reprend les commits de la PR #902 (confirmer avant d'agir) et délègue la règle à `BrakeWatch`.
- `tools/decrochages.py` : seuils lus dans `brake_watch.py` ; une chute à 0 W dont la cadence ne se maintient pas dans
  les 2 s est un « arrêt », même avec un vieux journal où le pilote avait écrit « frein lâché » puis « puissance
  revenue ».
- `ble_sim.py` : à l'arrêt du pédalage, la puissance tombe aussitôt, la cadence annoncée reste `CADENCE_LAG_S` = 1,5 s
  et le volant ralentit en roue libre ; nouveau scénario Bluetooth `arrets_pedalage` et scénario de banc
  `engine/tests/sim_bench_scenarios/arrets_pedalage_demo.json` (trois arrêts nets, puis un vrai frein lâché à 100 s).

Pas de changement du contrat IPC ni du format du journal. Le vrai frein lâché est vu 2 s après la chute au lieu
de 1 s (#902) ; la reprise du contrôle arrive 1 s plus tard.

## 3. Tests

- `core/tests/test_brake_watch.py` : retard de cadence de 1,0, 1,5 et 1,9 s à 1 Hz et à 8 Hz, vrai lâcher confirmé à
  2 s, frein revenu, une reprise au plus toutes les 10 s, bloc ERG à 0 W, volant presque arrêté, moins de 150 W,
  cycliste qui s'arrête après la reprise.
- `test_ftms_trace.py` : cas de #902, cadence en retard de 1,5 s, cadence qui fond à 8 Hz, trop peu de relevés,
  cycliste qui s'arrête puis repart sans « puissance revenue ».
- `test_decrochages.py` : arrêt à cadence en retard classé « arrêt » malgré un faux « frein lâché » au journal.
- `test_ble_sim.py` : deux arrêts nets sur le Bluetooth simulé, cadence en retard bien vue (0 W à plus de
  40 tr/min), aucun frein lâché ; le frein lâché simulé reste détecté une fois.

## 4. Recette

Banc PC, en low, medium et high :

```bash
python3 engine/tests/sim_bench.py --scenario arrets_pedalage_demo --quality low
python3 engine/tests/sim_bench.py --scenario arrets_pedalage_demo --quality medium
python3 engine/tests/sim_bench.py --scenario arrets_pedalage_demo --quality high
```

Attendu : un seul « frein lâché » (celui de 100 s), GPU et à-coups comme sur `main`. Pas d'essai vélo dédié : relire
le journal de la prochaine séance prévue et compter les « frein lâché » à chaque arrêt de pédalage.

## 5. Livraison

PR FR1 du 19 novembre (remplace la PR #902, fermée sans fusion sur décision du propriétaire du 17 novembre).
