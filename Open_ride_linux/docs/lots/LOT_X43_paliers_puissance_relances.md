# Lot X43 – Banc du trainer : paliers SIM à puissance cible, plafond, relances courtes, vitesse du volant

## 1. Objectif

Séance du 29 octobre : le banc `trainer_steps` (lot X5) envoyait des paliers de pente fixes. Le palier à 6 % demandait environ 600 W pendant 40 s. Il était intenable, et le lâcher venait alors du cycliste (la cadence baissait d'abord). Il ne prouvait donc rien sur le trainer. Le protocole revu (`/mnt/project-files/plans/PROTOCOLE_PALIERS_RETARD_TRAINER.md`, fil FTMS) demande :
- des paliers SIM tenables (250 à 350 W au plus), définis par la puissance et non par la pente ;
- des relances courtes de 10 à 15 s à 450–500 W, pour voir si le frein lâche à cadence constante.

Il faut aussi savoir à quelle vitesse tourne le volant. En entraînement direct, elle suit le braquet réel, plateau et pignon, et non le braquet virtuel.

## 2. Spécification

| # | Règle |
| --- | --- |
| X43-1 | Nouveau type de palier `sim_w` : un palier SIM défini par la puissance visée (W). La pente envoyée est celle qui donne cette puissance à la cadence demandée : P = v·(m·g·(pente + Crr) + ½·Cw·v²). Ici v est la vitesse du volant (cadence × plateau / pignon × circonférence), m la masse du `config.toml` local, et Cw la valeur que le pilote envoie au trainer. |
| X43-2 | Options `--plateau`, `--pignon` (dents) et `--roue` (circonférence, 2,105 m par défaut). Un protocole avec des paliers `sim_w` est refusé sans plateau ni pignon. Ces valeurs ne sont jamais écrites dans le dépôt. |
| X43-3 | Plafond `--plafond W` : une puissance moyenne sur 3 s au-dessus du plafond coupe le palier en cours (événement `ceiling`, alerte à l'écran) et passe au suivant. Par défaut, le plafond vaut 125 % du plus fort palier en watts. Un protocole de pentes n'a pas de plafond. |
| X43-4 | Protocoles :<br>– `paliers_puissance` : 150, 200, 250, 300, 200 et 150 W en SIM, environ 4 min 20 ;<br>– `relances` : trois fois 12 s à 470 W en SIM, avec 45 s de récupération à 150 W ;<br>– `relances_erg` : les mêmes en ERG. |
| X43-5 | `samples.csv` ajoute la vitesse annoncée par le trainer (`speed_kmh`, le volant) et le niveau de résistance (`resistance`), lus dans chaque trame Indoor Bike Data. `steps.csv`, `steps.txt` et `rapport.html` ajoutent par palier : la pente envoyée, l'écart à la cible (puissance finale − visée), la vitesse du volant et la résistance (médianes). Un ancien `samples.csv` sans ces colonnes se relit (`--analyse`). |

## 3. Fichiers

- `core/src/openride_core/tools/trainer_steps.py` (`Gearing`, `grade_for_power`, `plan_steps`, `default_ceiling`, plafond dans `run_bench`, colonnes) ;
- `tools/guide.py` (commandes et durées de l'essai) ;
- `core/tests/test_trainer_steps.py` ;
- `docs/OUTILS_DE_TEST.md`.

## 4. Critères d'acceptation

1. `pytest` passe. La pente calculée redonne la puissance visée à ± 1 W avec la même physique. Le grand plateau demande une pente plus faible que le petit.
2. Sur le trainer simulé (`--trainer sim --fast --plateau 38 --pignon 15 --mode relances`) : les paliers, la vitesse du volant et l'écart à la cible apparaissent dans le rapport.
3. Un plafond bas coupe le palier en moins de 7 s, et le rapport le note.
4. Sur le PC (via le fil de fusion), avec #580 et #582 : `paliers_puissance` au petit plateau, puis `relances` au grand plateau.

## 5. Hors périmètre

Distinguer un décrochage du trainer de la fatigue, statuts FTMS et analyse du pompage : lot X44. Fenêtre de suivi qui reste ouverte : lot X45.
