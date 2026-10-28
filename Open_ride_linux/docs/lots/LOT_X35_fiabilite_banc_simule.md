# Lot X35 – Fiabilité du banc simulé

## 1. Objectif

Défauts du banc signalés le 28 octobre par le fil des mesures et le fil du décor :

1. faux échec « captures 49 ou 50/51 » revenu cinq fois en une matinée : des captures demandées pendant le chargement du parcours ne reviennent pas à temps ;
2. les captures elles-mêmes provoquent des pics de 142 à 150 ms comptés dans le p99 de la sonde ;
3. le banc démarre même si le compilateur installé ne connaît pas une couche du monde demandé (P27 a échoué sur la couche `roads`) ;
4. le trainer simulé plafonne vers 21 km/h : le décor qui dépend de la vitesse (cyclistes, véhicules) ne se mesure pas à vitesse réaliste ; il faut une vitesse imposée (`bench.speed_kmh`).

## 2. À lire

`engine/tests/sim_bench.py` (`_shot`, `_capture_loop`, `prepare_world`), `perf_probe.py`, `perf_probe.gd`, `make_sim_world.py`, `ble_sim.py`.

## 3. Travail demandé

- **Captures** : la première capture attend `route_loaded` et la fin du chargement initial (première image jouable, X15, ou à défaut 5 s) ; une capture sans réponse est réessayée une fois ; le compte « captures » ne compte que celles demandées après le chargement ; délai de réponse par capture dans le rapport.
- **Pics des captures** : l'engine marque l'image de la capture et les deux suivantes (`capture=1` dans `moteur.csv`) ; `perf_probe.py` les retire du p99 et des saccades, et les compte à part.
- **Couches** : avant de lancer, `prepare_world` vérifie avec le compilateur installé (`openride-compiler layers` ou la liste exportée par `osm_layers`) que chaque couche demandée est connue ; sinon arrêt avec code 2 et message « compilateur installé trop ancien : réinstaller (`pip install -e compiler`) ».
- **Vitesse imposée** : `bench.speed_kmh` (ou `--speed-kmh`) : le trainer simulé règle la puissance du cycliste pour tenir cette vitesse sur le plat et la pente du moment (même physique que le core), avec une vérification « vitesse médiane à ± 10 % ».

## 4. Fichiers

- **Modifiés :** `sim_bench.py`, `perf_probe.py`, `engine/scripts/perf_probe.gd`, `engine/scripts/main.gd` (marque de capture), `ble_sim.py`, `sim_scenarios.py` (clé `target_speed_kmh`), `docs/OUTILS_DE_TEST.md`, `docs/SIMULATION_BLE.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `core/tests/test_sim_bench_fiabilite.py`.

## 5. Critères d'acceptation

1. Sondes fabriquées : les images marquées « capture » sortent du p99.
2. Couche inconnue : arrêt immédiat, code 2, message clair.
3. `sim_bench --speed-kmh 35 --scenario nominal --duration 40` : vitesse médiane 35 ± 3,5 km/h.

## 6. Hors périmètre

Les comptes du décor par sorte dans le rapport (fil du décor vivant).
