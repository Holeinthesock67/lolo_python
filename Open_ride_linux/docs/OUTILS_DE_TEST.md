# Outils de test d'OpenRide

Liste du 25 octobre 2026. Tous les outils se lancent depuis `Open_ride_linux/`. `GODOT` désigne l'exécutable Godot 4.3 (`~/Applications/godot/Godot_v4.3-stable_linux.x86_64` sur le PC cible). Aucun n'écrit dans le vrai dossier personnel, sauf mention contraire (rapports dans `~/OpenRide/…`).

## 1. Suites automatiques

| Commande | Ce qu'elle vérifie | Durée |
| --- | --- | --- |
| `(cd core && pytest -q)` | Core : physique, braquets, FTMS, Click, ceinture, journal, FIT, IPC, lanceur, scénarios Bluetooth simulés (`test_sim_matrix.py`, `test_ble_sim.py`), cohérence de la documentation. `-m "not slow"` : ~20 s | ~3 min |
| `(cd compiler && pytest -q)` | Compilateur : GPX/FIT/TCX, route, terrain, couches OSM, thèmes (réseau coupé ; `-m network` pour Copernicus) | ~1 min |
| `engine/tests/run_engine_tests.sh` | Engine sans écran : tests unitaires `engine/tests/unit/`, couches OSM, rendu par tronçons, ERG et menus face au faux core, scénarios IPC, rendu Xvfb du shader, tests graphiques à 1280×720. Budgets de temps à part (lot X2) : `OPENRIDE_PERF=strict` pour qu'un dépassement échoue, `PERF_CSV=FICHIER` pour garder les mesures | ~3 min |
| `engine/tests/run_e2e.sh` | Bout en bout : vrai core (trainer `mock`) et vrai engine, hello, débit des trames, commande, perte de l'engine, fin de séance, FIT | ~10 s |
| `engine/tests/vitrine_rendu.gd` (lot Y14) | Vitrine de rendu sans core : route, herbe, spectateurs, passants, cyclistes et animaux vus de près par préréglage, sur une route droite de démonstration ; captures PNG et `vitrine.csv` (triangles, appels de dessin) pour comparer avant et après une retouche graphique. `xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility --audio-driver Dummy --script res://tests/vitrine_rendu.gd -- --out DOSSIER [--quality low,medium,high]` | ~1 min |
| `engine/tests/run_visual_tests.sh [--open] [--native]` | Tests graphiques de la scène principale face au faux core : captures, HUD, bandeau, images de référence, rapport HTML dans `~/OpenRide/visual_tests/` | ~2 min |

Détail des tests de l'engine : [engine/tests/README.md](../engine/tests/README.md).

**Isolation des suites pytest (27 octobre) :** `core/tests/conftest.py` et `compiler/tests/conftest.py` chargent `scripts/isolation_tests.py` avant tout import. HOME, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME` et `XDG_STATE_HOME` pointent vers un dossier temporaire neuf (`~/OpenRide/...` compris), supprimé en fin de suite ; `zenity`, `kdialog` et `notify-send` sont remplacés par des programmes muets, sous-processus compris. Garde-fou : un test qui écrit, crée, renomme ou supprime un fichier hors du dossier temporaire du système, ou dans ce HOME temporaire (sous-processus compris), échoue avec le chemin et la ligne en cause ; un test écrit dans son `tmp_path`. Une seule suite à la fois sur la machine : pytest, `scripts/recette_pc.py`, `sim_bench.py`, `menu_bench.py` et `e2e_check.py` prennent le même verrou (`/tmp/openride-tests-<uid>.lock`) et une deuxième suite attend la fin de la première, pour ne pas fausser les mesures de performance. Le journal temporaire de `run_engine_tests.sh` est supprimé quand tout passe.

Protocole pas à pas sur le PC et le vélo (tout sur `main` depuis le 27 octobre, sauf deux essais qui attendent leur PR) : [PROTOCOLE_TEST_2026-10-26.md](PROTOCOLE_TEST_2026-10-26.md).

**Tout d'un coup sur le PC (lot X4) :** `scripts/recette_pc.py` enchaîne core, compilateur, engine, bout en bout, tests graphiques et scanner de confidentialité, garde un journal par étape dans `~/OpenRide/recettes/<date>_<heure>/` avec `resume.txt`, `resume.json` et `perf.csv` (budgets de temps), et compare au passage précédent (étape passée d'OK à ÉCHEC, nombre de tests changé). Options : `--rapide` (core sans les tests lents, sans tests graphiques), `--seulement core,engine`, `--sans visual`, `--perf-strict`. Utilise `core/.venv` s'il existe.

**Installation sur un système propre (lot X29) :** `scripts/recette_install.py` lance `scripts/recette_install/check_install.sh` dans un compte vierge, avec le code commité (HEAD publié dans un dépôt d'origine temporaire) : par défaut un conteneur Ubuntu 24.04 neuf sans Bluetooth (docker, compte `cycliste`), ou `--mode home` (HOME temporaire sur ce PC ; `--sans-pip` pour un essai rapide avec le venv actuel). Il vérifie le clone, `install.sh` sans terminal, les commandes de `~/.local/bin`, `config.toml` et le chemin de Godot, les raccourcis de bureau et l'icône (`desktop-file-validate`), le premier démarrage (`openride --compile-only`, core sur le trainer simulé), puis la mise à jour : parcours, séance et réglage modifié à la main, nouveau commit sur l'origine, `update.sh` et `install.sh` relancé ; le code avance et les données restent identiques octet pour octet. Journal et résumé dans `~/OpenRide/recettes_install/<date>/`. Avec un mandataire, `--ca-bundle` ajoute son certificat dans le conteneur. Reste à la main : le même essai sur un second compte du PC (`sudo adduser essai`, puis `scripts/install.sh` depuis ce compte).

## 2. Matériel simulé

| Outil | Usage |
| --- | --- |
| `--trainer sim --input sim --hr sim [--sim-scenario NOM\|FICHIER.json]` | Vrais pilotes FTMS, Click et ceinture devant des appareils simulés (`ble_sim.py`). Scénarios intégrés : `demo`, `nominal`, `reveil_tardif`, `erreur_0x80`, `connexions_retardees`, `coupures`, `controle_refuse`. Guide : [SIMULATION_BLE.md](SIMULATION_BLE.md) |
| `--trainer mock --input keyboard` | Générateur de puissance sans Bluetooth, clavier du terminal |
| `openride-core run --replay SEANCE.jsonl\|.fit` | Rejoue une séance enregistrée avec le simulateur |
| `--bot W`, `--ghost FICHIER` | Bots à puissance constante, fantôme d'une séance passée |
| `python -m openride_core.tools.seance_guidee [--materiel\|--retirer]` | Séances guidées sur le vrai HomeTrainer : parcours `recette-velo` (SIM, 25 min) et `recette-erg` (ERG, 13 min, entraînement `recette_erg`) avec consignes à l'écran au temps de séance, bip, préavis d'une minute quand il faut préparer du matériel, et une ligne `[essai]` au journal du lanceur par consigne (temps, puissance, cadence, FC, braquet, pente envoyée). Format des consignes : `engine/scripts/cue_model.gd` (`at_m` ou `at_s`, `prepare`, `warn_s`, `warn_m`) |
| `python -m openride_core.tools.log_scenario` | Convertit un journal du core (panne vue sur le vélo) en scénario simulé |
| `engine/tests/fake_core.py` | Faux core (bibliothèque standard) pour tester l'engine seul |

## 3. Banc d'essai simulé (`engine/tests/sim_bench.py`)

Vrai core sur Bluetooth simulé (trainer, paire de Click, ceinture) et vraie scène Godot, sous Xvfb ou dans une fenêtre (`--native`). Le banc capture l'écran à intervalle régulier et juste après chaque événement du scénario, vérifie ce qui doit se voir, puis écrit un rapport HTML (vérifications, courbes altitude, puissance et cible, fréquence cardiaque, pente et pente envoyée, braquet, vitesse, planche des captures, bandeau, `summary`, `log_report`, lignes d'événements du journal du core).

```bash
python3 engine/tests/sim_bench.py --list                                    # scénarios disponibles
python3 engine/tests/sim_bench.py --scenario coupures_village --native     # fenêtre visible
python3 engine/tests/sim_bench.py --scenario difficulte --difficulty 50 --out ~/OpenRide/sim_bench/d50
python3 engine/tests/sim_bench.py --native --probe --scenario erg_village --display fullscreen   # mode d'affichage (protocole J10)
python3 engine/tests/sim_bench.py --scenario erg_village --scenario ceinture --scenario click_sommeil
python3 engine/tests/sim_bench.py --scenario erreur_0x80 --world village --duration 60
```

Options : `--world demo|village|osm|DOSSIER.world`, `--workout erg_court|FICHIER.zwo`, `--duration S`, `--every S` (intervalle des captures), `--difficulty PCT` (`[trainer] difficulty_pct`), `--size 1280x720`, `--quality low|medium|high`, `--native`, `--out DOSSIER` (défaut `~/OpenRide/sim_bench/<date>`), `--keep` (garde le HOME temporaire). Code de sortie : 0 si tout passe, 1 sinon, 2 si Godot ou `xvfb-run` manque.

Images par seconde : relevées à chaque capture (avec le nombre de maillages affichés et d'appels de dessin), sous chaque image du rapport, en courbe dans le rapport, dans `fps.csv` et dans `engine.log` (lignes `[test] screenshot`) ; la console affiche minimum, médiane et maximum. Journaux gardés dans le dossier de sortie de chaque scénario : `core.log`, `engine.log`, `seance.jsonl`, `log_report.txt`, `summary.txt`, `fps.csv`, captures et `rapport.html`.

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

### Banc des menus (`engine/tests/menu_bench.py`, lot N13)

Même principe que le banc simulé, mais sans `--autostart` : le core démarre en attente, comme depuis l'icône. Le banc joue des appuis du Click dans l'engine (message de test `menu_input`), capture chaque écran et vérifie titres et éléments. Rien n'est écrit dans le vrai dossier personnel.

```bash
python3 engine/tests/menu_bench.py --list                      # parcours disponibles
python3 engine/tests/menu_bench.py                             # tous les parcours, rapport.html
python3 engine/tests/menu_bench.py --parcours appareils --native   # fenêtre visible
```

Parcours : `erg` (lot N16 : entraînement créé puis lu par le core, fichier des Téléchargements importé) ; `reglages` (lots O3 et O4 : FTP écrite dans `config.toml`, qualité appliquée tout de suite, curseur de difficulté de la pause) ; `connexion_auto` (tout se connecte, l'écran de connexion passe seul à l'accueil) ; `sessions` (lot N15 : monde, session libre, pause, bilan, session ERG, « Session simulée » : code 65) ; `appareils` (un seul boîtier du Click, « Passer », Réglages → Appareils, recherche, enregistrement dans `config.toml`, « Relancer » : code de sortie 64). Code de sortie : 0 si tout passe, 1 sinon, 2 si Godot ou `xvfb-run` manque.

## 4. Parcours d'essai sans réseau

| Outil | Parcours produit |
| --- | --- |
| `python -m openride_core.tools.fake_world --demo --terrain --out DOSSIER` | `demo` : parcours synthétique avec terrain |
| `python3 engine/tests/make_sim_world.py --out DOSSIER [--seed N]` | `village-simule` (bâtiments sans texture pour l'instant : une couleur unie par bâtiment, `building:colour` ou couleur déterministe) : 5 km, plat, montée à 7 %, descente à −6 %, deux villages (178 bâtiments de hauteurs et couleurs variées, église), fermes, forêts, verger, rivière, ruisseau, lac, points d'intérêt ; compilé par le vrai compilateur (relief et réponse Overpass fabriqués, origine fictive des tests) |
| `python3 engine/tests/make_sim_world.py --out DOSSIER --live` | `monde-ouvert-simule` : monde vivant de 20 km (format §13, lot W15) autour d'un point fictif en mer, carrefours scriptés avec amorces, relief analytique, pour mesurer le rendu du monde ouvert (W10) |
| `openride-worldgen-fake [--offline] [--missing-after-m M] [--crash-after-m M]` | Faux générateur du monde ouvert (lot W15) : le vrai générateur sur une base et un relief synthétiques, départ forcé sur la base fictive, pannes simulées ; se branche à la place d'`openride-worldgen` pour essayer le core (W9) et l'engine sans réseau |
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
| `python -m openride_core.tools.trainer_steps --mode sim\|erg` | Banc de latence du trainer (lot X5, outil de l'essai R0) : paliers de pente ou de puissance à cadence tenue ; par palier, délai consigne → écriture → accusé 0x80, t10, t63, t90, stabilisation et dépassement de la puissance ; `samples.csv`, `steps.csv` et `rapport.html` dans `~/OpenRide/trainer_steps/<date>/`. `--trainer sim --fast` pour l'essayer sans matériel, `--analyse DOSSIER` pour refaire l'analyse |
| `python -m openride_core.tools.click_recette [--minutes 30] [--rappel 5]` | Recette guidée du Zwift Click (lot X8, recette 1.0 ligne 6) : demande chaque bouton (+, − du boîtier gauche, B et Y du boîtier droit, appuis longs) et coche l'événement reçu et le boîtier qui l'a envoyé ; puis surveille 30 min avec un rappel d'appui toutes les 5 min : silences de chaque boîtier (lien tenu, plus de 2 s sans notification), coupures et reprises, messages sans bouton, batterie. `rapport.txt`, `rapport.json` et `notifications.csv` dans `~/OpenRide/click_recette/<date>/`. `--sim` pour l'essayer sans matériel |
| `python -m openride_core.tools.boutons_click [--sim] [--delai 30] [--lecture 4]` | Test guidé des boutons du Zwift Click (protocole G3) : les 17 appuis du plan des boutons (spécification générale §7.1) demandés un par un, boîtier gauche d'abord ; bip au début de chaque étape, étape suivante dès que l'appui est reconnu ; chaque appui reçu s'affiche dans un encadré (vert si demandé, jaune sinon) avec l'événement décodé, la touche, le boîtier et son action dans chaque mode, et bipe avec les notes du jeu ; verdict à la fin. `rapport.txt`, `rapport.json` et `guide.jsonl` dans `~/OpenRide/boutons_click/<date>/` |
| `engine/tests/sim_bench.py --native --probe` ; `engine/tests/perf_probe.py watch` | Sonde de performance du moteur (lot X13) : chaque seconde, temps d'image p50 et p99, temps CPU et GPU de la vue, appels de dessin, objets, primitives, mémoire vidéo, tuiles et arbres (engine lancé avec `--perf-probe` ou `OPENRIDE_PERF_PROBE`), plus nvidia-smi et CPU de chaque processus ; `sonde.csv`, `sonde.txt` (médianes, p99, dérive) et `rapport.html` (courbes) |
| `engine/tests/sim_bench.py --native --scenario endurance` | Endurance d'une heure (lot X16, recette 1.0 lignes 17 et 18) : village simulé relancé à chaque fin de parcours, sonde de performance ; images/s (médiane ≥ 30, baisse < 10 %), saccades (≤ 6 par heure), pente de la mémoire de Godot, du core et de la mémoire vidéo, engine vivant jusqu'à la fin, erreurs Godot |
| `python -m openride_core.tools.guide materiel [ESSAI]` ; `… guide bips` | Guidage des essais sur le PC et sur le vélo : matériel à préparer, durée et commande de chaque essai (`trainer_steps`, `click_recette`, `boutons_click`, `endurance`, `recette_pc`), à lire à l'avance ; `bips` joue chaque bip pour régler le volume. Pendant l'essai, `trainer_steps` et `click_recette` rappellent le matériel et attendent « Entrée », puis affichent en plein terminal la consigne, un grand compte à rebours, les valeurs en direct (puissance, cadence) et les relevés ; bip au début de chaque étape, à 3, 2, 1 s de la fin et à la fin, bip d'alerte (cadence hors de ± 10 rpm, boîtier Click muet ou coupé), bip de verdict. `sim_bench.py` et `recette_pc.py` bipent au départ et au verdict. Chaque essai écrit `guide.jsonl` (étapes, relevés, alertes, avec l'heure). Options `--materiel`, `--sans-attente`, `--muet` ; son par pw-play, paplay ou aplay, `OPENRIDE_GUIDE_MUET=1` pour le couper. Agrandir la police du terminal (Ctrl + +) pour lire depuis le vélo |
| `python -m openride_core.tools.ble_diag` | Diagnostic Bluetooth du HomeTrainer et du Click (matériel réel) |
| `openride-core release-trainer` | Libère un trainer resté réservé |
| `openride-core recover` | Convertit un journal de séance en FIT après un plantage |
| `python -m openride_core.tools.workouts check FICHIER.zwo` | Lecture et charge d'un entraînement ERG |
| `python -m openride_core.tools.route_vectors` | Vecteurs de test de la route, partagés core et engine |
| `openride-compiler world-measure --lat LAT --lon LON [--heading DEG] [--km 10] [--region R] [--synthetic]` | Monde ouvert (lot W0) : volumes du relief, des tuiles vectorielles et de l'extrait régional, temps de génération par carré de 1 km ; rapport dans `~/OpenRide/Cache/monde/mesures/<date>/` |
| `python -m openride_core.ipc_budget` | Taille de la trame `state` la plus lourde de chaque révision du contrat face à la limite de 1 400 octets (lot X25) ; une trame trop grande est allégée par le core au lieu d'être jetée |

## 6. Confidentialité (lot X23)

Le dépôt est public. `scripts/privacy/privacy_scan.py` (bibliothèque standard seulement) cherche les mots interdits (noms, lieux, nom du trainer…), les coordonnées dans une zone privée, les adresses Bluetooth qui ne sont pas des adresses de test, les clés et jetons, et les fichiers d'activité ou de secrets. Les mots trouvés sont masqués dans la sortie.

| Commande (depuis la racine du dépôt) | Usage |
| --- | --- |
| `Open_ride_linux/scripts/privacy/install_hook.sh` | Installe le crochet pre-commit : un commit qui ajoute une donnée interdite est refusé |
| `python3 Open_ride_linux/scripts/privacy/privacy_scan.py --all` | Tous les fichiers suivis (à lancer avant une étiquette de version, O8 §5.4) |
| `python3 Open_ride_linux/scripts/privacy/privacy_scan.py --commits origin/main..HEAD` | Auteur, committer, message et lignes ajoutées de chaque commit d'une branche |

La liste des mots et des zones interdits reste hors du dépôt : `~/OpenRide/privacy_denylist.txt` sur le PC (modèle : `scripts/privacy/privacy_denylist.example.txt`), secret GitHub `PRIVACY_DENYLIST` pour le workflow `.github/workflows/confidentialite.yml`, qui passe chaque PR. Sans liste, seuls les contrôles génériques tournent (avertissement à l'écran).

## 7. Ce qui demande encore le matériel

Le simulateur ne dit rien des délais réels de BlueZ, de la qualité radio, de la réponse exacte du HomeTrainer (latence de la résistance, Reset), du boîtier gauche du Click qui se tait après la connexion, de la vraie ceinture, ni des images par seconde sur la GTX 1060 : le banc sous Xvfb rend en OpenGL logiciel (quelques images par seconde), seul `--native` sur le PC cible mesure le rendu réel.
