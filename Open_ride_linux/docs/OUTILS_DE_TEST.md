# Outils de test d'OpenRide

Liste du 25 octobre 2026. Tous les outils se lancent depuis `Open_ride_linux/`. `GODOT` désigne l'exécutable Godot 4.3 (`~/Applications/godot/Godot_v4.3-stable_linux.x86_64` sur le PC cible). Aucun n'écrit dans le vrai dossier personnel, sauf mention contraire (rapports dans `~/OpenRide/…`).

## 1. Suites automatiques

| Commande | Ce qu'elle vérifie | Durée |
| --- | --- | --- |
| `(cd core && pytest -q)` | Core : physique, braquets, FTMS, Click, ceinture, journal, FIT, IPC, lanceur, scénarios Bluetooth simulés (`test_sim_matrix.py`, `test_ble_sim.py`), cohérence de la documentation. `-m "not slow"` : ~20 s | ~3 min |
| `(cd compiler && pytest -q)` | Compilateur : GPX/FIT/TCX, route, terrain, couches OSM, thèmes (réseau coupé ; `-m network` pour Copernicus) | ~1 min |
| `engine/tests/run_engine_tests.sh` | Engine sans écran : tests unitaires `engine/tests/unit/`, couches OSM, rendu par tronçons, ERG et menus face au faux core, scénarios IPC, rendu Xvfb du shader, tests graphiques à 1280×720 | ~3 min |
| `engine/tests/run_e2e.sh` | Bout en bout : vrai core (trainer `mock`) et vrai engine, hello, débit des trames, commande, perte de l'engine, fin de séance, FIT | ~10 s |
| `engine/tests/run_visual_tests.sh [--open] [--native]` | Tests graphiques de la scène principale face au faux core : captures, HUD, bandeau, images de référence, rapport HTML dans `~/OpenRide/visual_tests/` | ~2 min |

Détail des tests de l'engine : [engine/tests/README.md](../engine/tests/README.md).

## 2. Matériel simulé

| Outil | Usage |
| --- | --- |
| `--trainer sim --input sim --hr sim [--sim-scenario NOM\|FICHIER.json]` | Vrais pilotes FTMS, Click et ceinture devant des appareils simulés (`ble_sim.py`). Scénarios intégrés : `demo`, `nominal`, `reveil_tardif`, `erreur_0x80`, `connexions_retardees`, `coupures`, `controle_refuse`. Guide : [SIMULATION_BLE.md](SIMULATION_BLE.md) |
| `--trainer mock --input keyboard` | Générateur de puissance sans Bluetooth, clavier du terminal |
| `openride-core run --replay SEANCE.jsonl\|.fit` | Rejoue une séance enregistrée avec le simulateur |
| `--bot W`, `--ghost FICHIER` | Bots à puissance constante, fantôme d'une séance passée |
| `python -m openride_core.tools.log_scenario` | Convertit un journal du core (panne vue sur le vélo) en scénario simulé |
| `engine/tests/fake_core.py` | Faux core (bibliothèque standard) pour tester l'engine seul |

## 3. Banc d'essai simulé (`engine/tests/sim_bench.py`)

Vrai core sur Bluetooth simulé (trainer, paire de Click, ceinture) et vraie scène Godot, sous Xvfb ou dans une fenêtre (`--native`). Le banc capture l'écran à intervalle régulier et juste après chaque événement du scénario, vérifie ce qui doit se voir, puis écrit un rapport HTML (vérifications, courbes altitude, puissance et cible, fréquence cardiaque, pente et pente envoyée, braquet, vitesse, planche des captures, bandeau, `summary`, `log_report`, lignes d'événements du journal du core).

```bash
python3 engine/tests/sim_bench.py --list                                    # scénarios disponibles
python3 engine/tests/sim_bench.py --scenario coupures_village --native     # fenêtre visible
python3 engine/tests/sim_bench.py --scenario difficulte --difficulty 50 --out ~/OpenRide/sim_bench/d50
python3 engine/tests/sim_bench.py --scenario erg_village --scenario ceinture --scenario click_sommeil
python3 engine/tests/sim_bench.py --scenario erreur_0x80 --world village --duration 60
```

Options : `--world demo|village|osm|DOSSIER.world`, `--workout erg_court|FICHIER.zwo`, `--duration S`, `--every S` (intervalle des captures), `--difficulty PCT` (`[trainer] difficulty_pct`), `--size 1280x720`, `--quality low|medium|high`, `--native`, `--out DOSSIER` (défaut `~/OpenRide/sim_bench/<date>`), `--keep` (garde le HOME temporaire). Code de sortie : 0 si tout passe, 1 sinon, 2 si Godot ou `xvfb-run` manque.

Vérifications : démarrage du core, liaison de l'engine, parcours chargé, captures enregistrées, aucune erreur Godot, aucune exception du core, journal et FIT écrits, `summary` et `log_report` lisibles, fin de séance, HOME réel inchangé ; selon le scénario : chaque coupure suivie d'une ligne `down` puis `up` au journal, pause `PAUSED (trainer_lost)` visible pendant un silence du trainer puis reprise, consignes ERG et bandeau ERG à l'écran, fréquence cardiaque au journal.

Scénarios du banc (`engine/tests/sim_bench_scenarios/`, format de `SIMULATION_BLE.md` plus une section `bench` : `world`, `workout`, `duration_s`, `every_s`, `difficulty_pct`) :

| Scénario | Parcours | Ce qu'il montre |
| --- | --- | --- |
| `montee_descente` | village | Parcours complet (14 min) : plat, montée à 7 %, sommet, descente à −6 %, braquets au Click, effort qui suit la pente |
| `difficulte` | village | Montée à 350 W constants : comparer la pente envoyée avec `--difficulty 50` puis `100` |
| `erg_village` | village | ERG court de 5 min 30 (`erg_court`), biais au Click, appui long, coupure du « + » |
| `coupures_village` | village | Scénario `coupures` du core devant les bâtiments |
| `ceinture` | demo | Montre qui diffuse (la ceinture doit être préférée), contact perdu puis retrouvé, batterie à 8 %, fréquence figée, coupure |
| `click_sommeil` | demo | Connexions lentes, appuis longs, « − » coupé qui se rendort, « + » qui refuse une connexion |

Défaut trouvé à la mise en place : en séance, les bâtiments et l'eau OSM n'étaient jamais affichés (`WorldStreamer` ne faisait pas entrer les tronçons préparés par `OsmStreamer`), corrigé le 25 octobre.

## 4. Parcours d'essai sans réseau

| Outil | Parcours produit |
| --- | --- |
| `python -m openride_core.tools.fake_world --demo --terrain --out DOSSIER` | `demo` : parcours synthétique avec terrain |
| `python3 engine/tests/make_sim_world.py --out DOSSIER [--seed N]` | `village-simule` : 5 km, plat, montée à 7 %, descente à −6 %, deux villages (178 bâtiments de hauteurs et couleurs variées, église), fermes, forêts, verger, rivière, ruisseau, lac, points d'intérêt ; compilé par le vrai compilateur (relief et réponse Overpass fabriqués, origine fictive des tests) |
| `python3 engine/tests/make_osm_world.py --out DOSSIER` | `osm-test` : 3 km à 5 % avec les réponses Overpass enregistrées des tests du compilateur |
| `python3 engine/tests/make_texture_theme.py` | Thème à trois textures 2 048² pour mesurer le shader (essai E2) |

Pour rouler le village dans une vraie séance : `make_sim_world.py --out ~/.local/share/openride/routes`, puis `scripts/openride-dev.sh --trainer sim --input sim --hr sim --autostart --route village-simule`.

## 5. Diagnostic et analyse

| Outil | Usage |
| --- | --- |
| `python -m openride_core.tools.log_report [JOURNAL] [--all] [--json]` | Analyse de `~/run_trainer.log` : connexions, coupures, Click, ERG, performances |
| `openride-core summary [FICHIER]` | Bilan d'une séance : NP, IF, TSS, zones, meilleures puissances |
| `openride-core history` | Historique des séances et cumul hebdomadaire |
| `openride-core devices` | Inventaire des appareils Bluetooth et bloc `[drivers]` proposé |
| `python -m openride_core.tools.ble_diag` | Diagnostic Bluetooth du HomeTrainer et du Click (matériel réel) |
| `openride-core release-trainer` | Libère un trainer resté réservé |
| `openride-core recover` | Convertit un journal de séance en FIT après un plantage |
| `python -m openride_core.tools.workouts check FICHIER.zwo` | Lecture et charge d'un entraînement ERG |
| `python -m openride_core.tools.route_vectors` | Vecteurs de test de la route, partagés core et engine |

## 6. Ce qui demande encore le matériel

Le simulateur ne dit rien des délais réels de BlueZ, de la qualité radio, de la réponse exacte du HomeTrainer (latence de la résistance, Reset), du boîtier gauche du Click qui se tait après la connexion, de la vraie ceinture, ni des images par seconde sur la GTX 1060 : le banc sous Xvfb rend en OpenGL logiciel (quelques images par seconde), seul `--native` sur le PC cible mesure le rendu réel.
