# Outils de test d'OpenRide

Liste du 25 octobre 2026. Tous les outils se lancent depuis `Open_ride_linux/`. `GODOT` désigne l'exécutable Godot 4.3 (`~/Applications/godot/Godot_v4.3-stable_linux.x86_64` sur le PC cible). Aucun n'écrit dans le vrai dossier personnel, sauf mention contraire (rapports dans `~/OpenRide/…`).

## 1. Suites automatiques

| Commande | Ce qu'elle vérifie | Durée |
| --- | --- | --- |
| `(cd core && pytest -q)` | Core : physique, braquets, FTMS, Click, ceinture, journal, FIT, IPC, lanceur, scénarios Bluetooth simulés (`test_sim_matrix.py`, `test_ble_sim.py`), cohérence de la documentation. `-m "not slow"` : ~20 s | ~3 min |
| `(cd compiler && pytest -q)` | Compilateur : GPX/FIT/TCX, route, terrain, couches OSM, thèmes (réseau coupé ; `-m network` pour Copernicus) | ~1 min |
| `pytest -m fuzz --hypothesis-profile=long` (dans `core/` ou `compiler/`) | Fuzz des lecteurs de fichiers (lot X26, `hypothesis`) : `.zwo`, `.erg`, `.mrc`, GPX, TCX et FIT, nus ou en `.gz` / `.zip`, générés puis abîmés ; la lecture rend un résultat valide ou l'erreur documentée (`WorkoutError`, `CompileError`) en moins de 2 s ; bombe XML et entité externe refusées. 200 exemples par lecteur dans les suites ordinaires, 5 000 avec le profil `long` | ~5 s ; ~5 min en `long` |
| `engine/tests/run_engine_tests.sh` | Engine sans écran : tests unitaires `engine/tests/unit/`, couches OSM, rendu par tronçons, ERG et menus face au faux core, scénarios IPC, rendu Xvfb du shader, tests graphiques à 1280×720. Budgets de temps à part (lot X2) : `OPENRIDE_PERF=strict` pour qu'un dépassement échoue, `PERF_CSV=FICHIER` pour garder les mesures | ~3 min |
| `engine/tests/run_e2e.sh` | Bout en bout : vrai core (trainer `mock`) et vrai engine, hello, débit des trames, commande, perte de l'engine, fin de séance, FIT | ~10 s |
| `engine/tests/menu_bench.py --rotation` | Banc des menus face au vrai core sur Bluetooth simulé : chaque scénario de `engine/tests/menu_scenarios/` sur une voie à tour de rôle (Click V2 simulé, clavier, souris) ; sans `--rotation`, les trois voies (§3) | ~10 min |
| `engine/tests/vitrine_rendu.gd` (lot Y14) | Vitrine de rendu sans core : route, herbe, spectateurs, passants, cyclistes et animaux vus de près par préréglage, sur une route droite de démonstration ; captures PNG et `vitrine.csv` (triangles, appels de dessin) pour comparer avant et après une retouche graphique. `xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility --audio-driver Dummy --script res://tests/vitrine_rendu.gd -- --out DOSSIER [--quality low,medium,high]` | ~1 min |
| `engine/tests/vitrine_biomes.gd` (série U, lots U7, U8 et U12) | Vitrine des biomes sans core : pour chaque biome forcé (16 par défaut), route droite dans un paysage plat avec le sol, la végétation, les détails de sol, les animaux, un étang, le brouillard et la lumière du biome ; quatre vues par biome (`route`, `bord`, `haut`, `faune`), captures PNG et `vitrine_biomes.csv` (arbres, triangles, appels de dessin, préparation des arbres, bêtes et oiseaux affichés, espèces, placement des animaux, rochers, herbes hautes et termitières). `xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility --audio-driver Dummy --script res://tests/vitrine_biomes.gd -- --out DOSSIER [--biomes alpine,savanna] [--quality low,medium,high] [--size 1680x1050]` | ~5 min |
| `engine/tests/vitrine_sols.gd` (série U, lot U6) | Vitrine du sol multi-biome sans core : pour huit paires de biomes, deux tuiles de 1 km avec un relief de collines et un fondu de 250 m de part et d'autre de leur bord commun, vue aérienne oblique ; captures PNG et `vitrine_sols.csv` (triangles, appels de dessin, préparation du matériau). `xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility --audio-driver Dummy --script res://tests/vitrine_sols.gd -- --out DOSSIER [--quality low,medium,high] [--size 1680x1050]` | ~1 min |
| `engine/tests/run_visual_tests.sh [--open] [--native]` | Tests graphiques de la scène principale face au faux core : captures, HUD, bandeau, images de référence, rapport HTML dans `~/OpenRide/visual_tests/` | ~2 min |

Détail des tests de l'engine : [engine/tests/README.md](../engine/tests/README.md).

**Isolation des suites pytest (27 octobre) :** `core/tests/conftest.py` et `compiler/tests/conftest.py` chargent `scripts/isolation_tests.py` avant tout import. HOME, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME` et `XDG_STATE_HOME` pointent vers un dossier temporaire neuf (`~/OpenRide/...` compris), supprimé en fin de suite ; `zenity`, `kdialog` et `notify-send` sont remplacés par des programmes muets, sous-processus compris. Garde-fou : un test qui écrit, crée, renomme ou supprime un fichier hors du dossier temporaire du système, ou dans ce HOME temporaire (sous-processus compris), échoue avec le chemin et la ligne en cause ; un test écrit dans son `tmp_path`. Une seule suite à la fois sur la machine : pytest, `scripts/recette_pc.py`, `scripts/pre_vol.py`, `sim_bench.py`, `menu_bench.py` et `e2e_check.py` prennent le même verrou (`/tmp/openride-tests-<uid>.lock`) et une deuxième suite attend la fin de la première, pour ne pas fausser les mesures de performance. Le journal temporaire de `run_engine_tests.sh` est supprimé quand tout passe.

**Hygiène des suites (lot X34) :** `python3 scripts/recompte_tests.py` réécrit les nombres de tests annoncés dans `README.md` et `docs/SUIVI_AVANCEMENT.md` (tests collectés du core et du compilateur, fichiers de tests unitaires et de rendu de l'engine), `--verifier` dit seulement ce qui diffère ; à lancer après chaque fusion de `main` dans une branche. Dans `run_engine_tests.sh`, toute ligne `ERROR`, `SCRIPT ERROR` ou `WARNING` d'un test fait échouer ce test, sauf les objets non libérés à la sortie et les erreurs du serveur de rendu factice de `--headless` (ligne `at:` dans `servers/rendering/dummy/`). Aucun seuil de temps n'est écrit en dur dans un test : il passe par `PerfBudget.check` et `engine/tests/perf_budgets.json` (vérifié par `test_no_hardcoded_timing.gd`) ; `PerfBudget.check(nom, valeur, "%")` pour un surcoût relatif.

Protocole pas à pas sur le PC et le vélo (tout sur `main` depuis le 27 octobre, sauf deux essais qui attendent leur PR) : [PROTOCOLE_TEST_2026-10-26.md](PROTOCOLE_TEST_2026-10-26.md).

**Tout d'un coup sur le PC (lot X4) :** `scripts/recette_pc.py` enchaîne core, compilateur, engine, bout en bout, tests graphiques, banc des menus (`menu_bench.py`, trois voies, rapport dans `menus/`) et scanner de confidentialité, garde un journal par étape dans `~/OpenRide/recettes/<date>_<heure>/` avec `resume.txt`, `resume.json` et `perf.csv` (budgets de temps), et compare au passage précédent (étape passée d'OK à ÉCHEC, nombre de tests changé). Options : `--rapide` (core sans les tests lents, sans tests graphiques ni banc des menus), `--seulement core,engine`, `--sans visual`, `--perf-strict`. Utilise `core/.venv` s'il existe.

**Pré-vol avant une séance vélo (lot X36) :** `scripts/pre_vol.py --seance t11_j7` vérifie en une commande tout ce qui se contrôle sans pédaler, pour que la séance tienne en 20 minutes de vélo : git (branche, rien de non commité, à jour avec origin), tests pytest de la marque `recette_sans_velo`, tests unitaires Godot de la séance (`UNIT`), séance simulée (scénarios du lot X33 quand ils existent), `config.toml` sauvegardé en `config.toml.<séance>`, parcours compilés présents, fichiers de la séance posés (`powerups.toml` de la séance A) ou mis de côté, trainer et Click visibles en Bluetooth (`openride-core devices --json`). Verdict « PRÊT À ROULER » ou la liste de ce qui bloque, avec bip. Séances dans `scripts/pre_vol_seances.toml` (`t11_j7`, `p27`, `erg`, `recette_1_0`, `--liste`) ; options `--sans-engine`, `--sans-bluetooth`, `--sans-reseau`, `--muet` ; journaux dans `~/OpenRide/pre_vol/<date>_<heure>/`. Code de sortie : 0 si prêt, 1 sinon, 2 si l'appel est invalide.

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
python3 engine/tests/sim_bench.py --native --probe --scenario rendu_invisible --culling on    # essai du tri du visible, coupé par défaut (lot S1, docs/ETUDE_RENDU_INVISIBLE.md)
python3 engine/tests/compare_captures.py AVANT_DOSSIER APRES_DOSSIER --out ECARTS   # captures de deux bancs comparées image par image (lot S1)
python3 engine/tests/sim_bench.py --native --probe --scenario rendu_invisible --world ~/.local/share/openride/routes/essai-69.world --every-m 200   # --world l'emporte sur le monde du scénario ; captures tous les 200 m
python3 engine/tests/sim_bench.py --scenario erg_village --scenario ceinture --scenario click_sommeil
python3 engine/tests/sim_bench.py --scenario erreur_0x80 --world village --duration 60
```

Options : `--world demo|village|osm|DOSSIER.world`, `--workout erg_court|FICHIER.zwo`, `--duration S`, `--every S` (intervalle des captures), `--difficulty PCT` (`[trainer] difficulty_pct`), `--size 1280x720`, `--quality low|medium|high`, `--native`, `--out DOSSIER` (défaut `~/OpenRide/sim_bench/<date>`), `--keep` (garde le HOME temporaire). Code de sortie : 0 si tout passe, 1 sinon, 2 si Godot ou `xvfb-run` manque.

**Lisibilité du HUD et débordements (lot X22)** : `visual_check.py --lisibilite` (passé par `run_visual_tests.sh`) mesure dans chaque capture la hauteur des chiffres principaux (puissance, vitesse, cadence, FC, pente), ramenée à 1080 lignes (au moins 28 px, lisible à 2 m), et le contraste WCAG texte/fond (4,5:1 pour les valeurs, 3:1 pour les libellés, l'encart des bots, les blocs segment et bonus, le vent) ; à chaque capture, sans option, les panneaux du HUD (colonnes, vent, abri, segment, bonus, bots, profil) doivent tenir dans l'écran sans se chevaucher. La scène `bots_segment_bonus` charge la colonne de droite (4 bots à profil, deux voisins, segment en cours, bonus en réserve) jusqu'en 1024×600. Calculs dans `engine/tests/hud_lisibilite.py`.

**Qualité réellement appliquée (lot X32)** : le banc vérifie dans le journal de l'engine (`engine/tests/quality_guard.py`) que chaque capture a été rendue dans la qualité demandée par `--quality`, et que la sonde l'a notée ; sinon, ÉCHEC « qualité demandée medium, appliquée low ». Même contrôle dans `visual_check.py` et dans `perf_probe.py watch|report --quality Q`. `python3 engine/tests/quality_guard.py engine.log medium` vérifie un journal à la main.

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
| `decor_vivant_2` | osm | Décor vivant de la deuxième vague (lot P27) : 5 min en SIM à 300 W (vers 21 km/h) sur le monde de test OSM (prés, champs, routes voisines, troupeau, lac, canal, montée à 5 %), à lancer avec `--probe` en `low`, `medium` et `high` ; vérifie les sortes vues et les sons du décor (lot P30 : `decor_expect`, `sounds_expect`, `decor.csv`) |

Défaut trouvé à la mise en place : en séance, les bâtiments et l'eau OSM n'étaient jamais affichés (`WorldStreamer` ne faisait pas entrer les tronçons préparés par `OsmStreamer`), corrigé le 25 octobre.

### Banc des menus (`engine/tests/menu_bench.py`, lots N13 puis Z menus du 28 octobre)

Tous les menus pilotés de bout en bout, sans rien faire à la main : vrai core sur Bluetooth simulé, sans `--autostart` (le core démarre en attente, comme depuis l'icône), et vraie scène Godot sous Xvfb ou dans une fenêtre (`--native`). Les arguments de l'engine sont tirés de `config.toml` par le vrai lanceur (`build_supervisor`). Chaque scénario déclaratif (`engine/tests/menu_scenarios/*.json`) est joué une fois par **voie d'entrée** :

| Voie | Chemin parcouru |
| --- | --- |
| `click` | Appui sur le bouton du Zwift Click V2 simulé (+, −, A, B, Y, Z, flèches ; fichier de commandes `control_file` du monde simulé) : notifications Bluetooth, `PressClassifier`, relais du core, engine |
| `clavier` | Touche appuyée puis relâchée après la durée de l'appui (message de test `key`, `Input.parse_input_event`) : `_unhandled_input` et `key_map.gd`, comme une vraie touche ; en séance, la touche part au core |
| `souris` | Molette (+ et −), clic droit (Y), clic gauche sur la rangée (A maintenu) (message de test `mouse`) ; un événement sans geste de souris passe par le clavier et le rapport le compte |

Un seul tableau bouton → geste (`GESTES` dans le banc, d'après la spécification générale §7.1, `key_map.gd` et `menu_view.gd`). Les vérifications portent sur les identifiants stables des menus (écran, sous-écran de Réglages, focus, identifiants des éléments) lus par le message de test `menu_state`, sur `config.toml`, les journaux du core et de l'engine, les fichiers écrits dans le HOME temporaire et le code de sortie de l'engine (64 : relancer, 65 : session simulée). Chaque vérification attend son résultat quelques secondes au lieu d'attentes fixes. Étape `relancer` : core et engine arrêtés proprement puis relancés sur le même HOME, pour vérifier qu'un réglage persiste. Le format des étapes est décrit en tête de `menu_bench.py`.

```bash
python3 engine/tests/menu_bench.py --list                                  # scénarios et voies
python3 engine/tests/menu_bench.py                                         # tout, trois voies, rapport.html
python3 engine/tests/menu_bench.py --scenario reglages --voies clavier     # un scénario, une voie
python3 engine/tests/menu_bench.py --scenario appareils --native           # fenêtre visible
python3 engine/tests/menu_bench.py --captures ecrans --out ~/OpenRide/menu_bench/$(date +%F)   # capture de chaque écran vérifié
```

| Scénario | Voies | Ce qu'il vérifie |
| --- | --- | --- |
| `connexion_auto` | clavier | Tout se connecte, l'écran « Connexion des appareils » passe seul à l'accueil, entrées de l'accueil |
| `appareils` | trois | Un seul boîtier du Click : « Passer » ; Réglages → Appareils : recherche, Enregistrer → confirmation (Non : rien d'écrit, Oui : `config.toml`), « Relancer » (code 64) |
| `sessions` | trois | Parcours choisi, session libre, Y en séance (pause), fin enregistrée, bilan, session ERG, « Session simulée » confirmée (code 65) |
| `reglages` | trois | Sous-écrans, FTP + 15 W écrite, Y annule une modification, qualité appliquée tout de suite et écrite, ligne de version |
| `erg` | trois | Créer un entraînement par intervalles (fichier écrit), importer un fichier des Téléchargements |
| `pause` | trois | Y reprend, curseur de difficulté (`set_difficulty`), « Abandonner » confirmé (Non, puis Oui : bilan, aucun FIT) |
| `quitter` | trois | « Quitter » : focus sur Non, Non et Y reviennent, Oui ferme l'engine (code 0) |
| `plans_ftp` | trois | Plans de référence : liste, fiche, démarrage, arrêt confirmé ; test de FTP par rampe jusqu'à « Prêt » |
| `records` | trois | Records depuis « Prêt » (temps fictifs posés dans `records.json`) : segment sans temps désactivé, table, A court bascule « sans bonus » / « avec bonus », retours |
| `garage` | trois | Garage : vélo et tenue (catalogue du core), avatar modifié, annulé, puis enregistré dans `profile.json` |
| `monde_ouvert` | click, clavier | Menu du monde ouvert : globe, recherche ouverte par une lettre (les lettres y sont du texte), Échap ou Y revient puis ferme |
| `cyber_rogue` | trois | Départ du Cyber-Rogue : objectif et durée, avertissement du premier lancement, run composée jusqu'à « Prêt », « Changer les choix » et run recomposée, départ, pause, abandon |
| `clavier_synonymes` | clavier | Entrée, Maj+A, Page haut et bas, Échap, `=` et pavé +, flèches gauche et droite ; appui ambigu de 0,7 s ignoré ; flèches haut et bas sans effet en menu |
| `souris_gestes` | souris | Clic sur un élément sans focus, molette, clic droit, clic hors des éléments et survol sans effet |

Un nouvel écran s'ajoute au banc par un fichier JSON, sans toucher au script. Clé d'en-tête `fichiers` : fichiers posés dans le HOME avant le lancement (records, profil…).

Défauts trouvés par le banc à sa mise en service (28 octobre), corrigés dans la même PR : catalogue du Garage jamais reçu par l'engine (plus de 4 096 octets, jeté par `send_raw` : la liste des messages à 60 000 octets reprend désormais celle du contrat §2, `plans` compris) ; Cyber-Rogue bloqué sur « Composition de la run… » quand la run est recomposée depuis « Prêt » (le core repasse en READY dans la même commande : l'engine attend maintenant l'accusé de `start_run`).

Rapport dans `--out` (défaut : dossier temporaire) : `rapport.html` (tableau scénario × voie, chaque vérification, captures prises à chaque échec avec l'écran, le titre et les rangées affichées), `resultats.json`, `resume.txt`, et les journaux `core.log` et `engine.log` de chaque passage. Durée : environ 40 s par scénario et par voie sous Xvfb. Code de sortie : 0 si tout passe, 1 sinon, 2 si Godot ou `xvfb-run` manque.

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
| `openride-core session-report [FICHIER] [--log …] [--engine-log …]` | Analyse automatique d'une séance réelle (lot X12), en local : sections de pente (pente envoyée, braquet, puissance, cadence, vitesse, FC), retard pente → effort à chaque marche de plus de 3 points, écart ERG par bloc, coupures, appuis du Click, images/s, segments et bonus ; `rapport.html`, `sections.csv`, `resume.json` dans `~/OpenRide/rapports/<séance>/` |
| `openride-core history` | Historique des séances et cumul hebdomadaire |
| `openride-core xp --save F` ; `openride-core xp --compare F` | Écart de progression avant/après une PR (lot X39) : instantané de l'expérience, des pièces et des défis recalculés depuis les journaux sur `main`, puis écart des totaux, des défis et de chaque séance sur la branche (code 1 si écart). Avec les vrais journaux du PC, l'instantané reste local |
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
