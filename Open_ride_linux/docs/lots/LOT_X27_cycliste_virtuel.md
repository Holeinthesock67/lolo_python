# Lot X27 – Cycliste virtuel et course accélérée

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : Cycliste virtuel (cadence, pente, rampe, sprint, W′bal) et course contre les bots accélérée | Python | T12 pour `bots_race` | Moyenne | **Livré le 28 octobre** (branche `claude/project-thread-818r6t-x27`) ; issue #225 |

## 1. Objectif

Le Bluetooth simulé pédale à puissance constante (un peu plus en montée) et le trainer simulé plafonne vers 21 km/h. Le test de FTP (O10), les plans (O11), le combat Cyber-Rogue (R5, R7) et les bots à profil (T12, T13) ont besoin d'un cycliste qui réagit. Le fil de la série T (28 octobre) demande en plus une course contre les bots en temps accéléré, sans écran.

## 2. À lire

`core/src/openride_core/ble_sim.py` (`_rider_power`), `sim_scenarios.py`, `tools/rogue_sim.py` (cycliste simulé du Cyber-Rogue), `physics.py`, `bots.py` et la calibration des bots (T13, #488), `session.py`.

## 3. Travail demandé

- **`core/src/openride_core/sim_rider.py`** : stratégies `constante` (actuelle), `cadence` (cadence tenue, changements de braquet au Click simulé quand la cadence sort de 80–95 rpm), `pente` (puissance qui suit la pente, `ftp_w`, `pct_ftp`), `rampe` (+20 W par minute jusqu'à l'échec, pour O10), `sprint` (sprints de 10 s aux points demandés), `fatigue` (W′bal : la puissance baisse quand la réserve est vide) ; bruit déterministe par graine.
- **Scénarios** : section `"rider": {"strategy": "pente", "ftp_w": 250, "pct_ftp": 75}` dans le scénario Bluetooth (trainer simulé) ; une stratégie peut émettre des appuis du Click (braquets).
- **`python -m openride_core.tools.bots_race --route demo|plat|col|FICHIER.world --rider-pct 85 --bots climber,rouleur,sprinteur,diesel`** : `CoreSession` en temps accéléré (pas fixe de 20 ms, sans trainer réel ni engine), tableau par bot : temps d'arrivée, écart avec le cycliste, W′ le plus bas, passages de sprint et de montée, maillots ; échec si un bot calibré à 100 % finit à plus de 2 % du cycliste, ou si une trame `state` dépasse la limite du contrat (4 096 octets).

## 4. Fichiers

- **Nouveaux :** `core/src/openride_core/sim_rider.py`, `tools/bots_race.py`, `core/tests/test_sim_rider.py`, `core/tests/test_bots_race.py`.
- **Modifiés :** `ble_sim.py`, `sim_scenarios.py`, `docs/SIMULATION_BLE.md`, `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. Chaque stratégie testée (cadence tenue dans la plage, rampe qui s'arrête à l'échec, W′bal qui fait baisser la puissance).
2. `bots_race` sur `demo` en moins de 30 s au cloud ; sans bots à profil sur `main` (avant T12), l'outil le dit et sort en code 2.
3. Le comportement par défaut du Bluetooth simulé est inchangé (suite core verte).

## 6. Hors périmètre

L'équilibrage lui-même (T13, R7).

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x27`, sur X35).

- `core/src/openride_core/sim_rider.py` : sept stratégies (les six du cahier et `vitesse`, qui reprend la vitesse imposée de X35). Le cycliste devient une section `rider` du scénario, au lieu des clés `rider_power_w` et `cadence_rpm` du trainer et de `target_speed_kmh` (X35) : une seule façon de décrire le cycliste. Les scénarios du banc (`difficulte.json`, `endurance.json`) et `sim_bench.py --speed-kmh` sont réécrits. Le défaut (180 W, 88 rpm, +4 % par point de pente, sinusoïde) est inchangé.
- Le trainer simulé appuie sur le Click simulé quand la stratégie `cadence` le demande ; en ERG, il tient sa cible tant que la cadence n'est pas nulle (la rampe qui lâche coupe la puissance).
- `tools/bots_race.py` : la vraie `CoreSession` au pas de 20 ms. Les parcours `plat` et `col` sont écrits à la volée par `demo_world.write_world`, qui accepte maintenant un profil de pente. Le FIT de fin de parcours est écrit dans un dossier temporaire. Sur `demo` au cloud : 7,5 s, écarts de +0,08 à +0,20 % au niveau du cycliste, trame `state` la plus grande à 1 289 octets.
- Proposition du fil V5, banc de calibrage des bots : couvert par `bots_race --niveau` (80, 100, 120 % du niveau du cycliste) sur `plat`, `col` et `demo`. Les équipements (série V) restent à ajouter quand la séance les applique aux bots.
- Tests : `test_sim_rider.py` (12), `test_bots_race.py` (6), `test_ble_sim.py` et `test_sim_bench_fiabilite.py` réécrits pour la section `rider`.
