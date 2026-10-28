# OpenRide Linux

[![Tests OpenRide](https://github.com/Holeinthesock67/lolo_python/actions/workflows/openride.yml/badge.svg)](https://github.com/Holeinthesock67/lolo_python/actions/workflows/openride.yml)

Simulateur de cyclisme indoor 3D à usage personnel, natif Linux, plus léger que Zwift.
Matériel de référence : home trainer HomeTrainer (FTMS), Zwift Cog, Zwift Click, PC Ubuntu.

**Pour rouler :** le [guide d'utilisation](docs/GUIDE_UTILISATION.md) explique l'installation, l'appairage, les parcours, l'ERG et le dépannage, sans terminal. Le reste de ce fichier s'adresse au développement.

## État (27 octobre 2026)

Version `0.9.0` (fichier `VERSION`) ; la 1.0 réunit les séries N et O. OpenRide s'installe en une commande et s'utilise ensuite depuis son icône, au Click ou au clavier, sans terminal : [docs/GUIDE_UTILISATION.md](docs/GUIDE_UTILISATION.md). Le détail des lots est dans [docs/SUIVI_AVANCEMENT.md](docs/SUIVI_AVANCEMENT.md), les essais restants dans son §3 et dans [docs/PROTOCOLE_TEST_2026-10-26.md](docs/PROTOCOLE_TEST_2026-10-26.md).

- **Sur `main` :** HomeTrainer en SIM et ERG validé sur le matériel, Zwift Click V2 à deux boîtiers, fréquence cardiaque relayée par le trainer ; séance, journal, FIT et bilan ; lancement sans terminal, écran des appareils et menus pilotés au Click selon le plan des boutons commun ; réglages ; entraînements `.zwo`, `.erg` et `.mrc` (choix, création, import) ; test de FTP, plans d'entraînement, bibliothèque de parcours et pack « Cols célèbres » ; rendu 3D (route, terrain, ciel, arbres, bâtiments, eau, sons), décor vivant et vent (série P, mises à jour 1.x), brouillard par préréglage ; outils de test de la série X.
- **Reste pour la 1.0 :** la recette sur le matériel et la publication (O8). Écrans des plans, du test de FTP et de la bibliothèque (O12), courbes de la séance (O14), bots à l'écran (O7) et guide d'utilisation (O6) sont sur `main`.
- **Déjà prêt pour la 2.0, sans branchement :** contrat IPC 1.4 (lot T1), modules purs des segments, bonus, records, maillots et écarts (série T), de la progression et de l'équipement (série V), mesures du monde ouvert (W0).

## Installation (PC Ubuntu)

En une commande (lot N14), depuis `Open_ride_linux/` après `sudo apt install python3-venv bluez` et le téléchargement de Godot 4.3 :

```bash
scripts/install.sh
```

Le script crée l'environnement Python `core/.venv`, y installe le core et le compilateur, relie `openride` et `openride-core` dans `~/.local/bin`, crée `~/OpenRide/config.toml` depuis `scripts/config.example.toml`, demande une fois le chemin de Godot 4.3 (gardé dans `[engine] godot`) et installe trois entrées de menu : **OpenRide**, **OpenRide – Libérer le trainer** et **OpenRide – Mettre à jour** (`scripts/update.sh` : `git pull --ff-only` puis réinstallation, refusée s'il y a des modifications locales). Il peut être relancé sans dommage. Ensuite, tout se fait depuis l'icône : au premier lancement, OpenRide crée `~/OpenRide/GPX/` et `~/OpenRide/Workouts/` et rappelle de configurer les appareils ; une erreur au lancement (Godot introuvable, configuration invalide, port occupé, trainer réservé par une autre application, plantages répétés) s'affiche dans une fenêtre avec le chemin du journal.

Tout le reste (appairage, parcours, entraînements, commandes, dépannage) est dans le [guide d'utilisation](docs/GUIDE_UTILISATION.md).

## Développement

Cette partie s'adresse à qui modifie le code ; les sections « Version », « Lancer une séance » et « Diagnostic matériel » plus bas en font aussi partie.

### Documents de référence (à fournir à l'IA au début de chaque session)

Avec Claude Code, lancer `claude` depuis `Open_ride_linux/` : le fichier `CLAUDE.md` est lu automatiquement, et les commandes `/tests`, `/seance` et `/lot` sont disponibles.

- `docs/SRS_v1.1.md` : spécification logicielle
- `docs/contracts/ipc_v1.md` : contrat de messages core ↔ engine
- `docs/contracts/world_format_v1.md` : format des parcours compilés `.world`
- `docs/SUIVI_AVANCEMENT.md` : état d'avancement, tests effectués et tests restants
- `docs/AUDIT_2026-10-23.md` : audit du projet (constats et recommandations, complété le soir : §8 et §9)
- `docs/VERIFICATION_2026-10-24.md`, `docs/AUDIT_FTMS_2026-10-24.md` et `docs/REVUE_CODE_2026-10-24.md` : vérification, audit FTMS et revue de code du 24 octobre
- `docs/lots/` : cahiers des charges des lots confiables à une autre IA (commencer par `00_INDEX.md`)
- `docs/spikes.md` : faits mesurés sur le matériel (sprint 0)

### Structure

```text
Open_ride_linux/
  docs/        spécifications, contrats, audit, lots
  core/        openride-core (Python) : BLE, physique, braquets, journal, FIT, IPC
  engine/      openride-engine (Godot 4.3) : rendu, HUD
  scripts/     outils de lancement (openride-dev.sh)
  compiler/    openride-compiler (Python) : GPX vers .world, couches route et terrain (lots B1 et B2)
```

### Tests

- **Tests :** 1611 tests automatiques côté core (dont conformité FTMS, cohérence documentation/code, robustesse IPC, validation de `config.toml`, catalogue des parcours, recherche BLE sans matériel, Bluetooth simulé (trainer, Click, ceinture), rejeu JSONL/FIT, endurance de 3 h, validation FIT par `garmin-fit-sdk`, analyseur de journal, historique des séances, raccourci de bureau `.desktop`, rampe de pente du trainer et outils d'entraînements `.zwo`, `.erg` et `.mrc`) et 424 côté compilateur (dont contrat des biomes (lot U1), traces FIT et TCX, mesures du monde ouvert et décodeur de tuiles vectorielles (lot W0), bibliothèque de parcours (fiches, tri, filtres, packs, lot O15), recettes de cols construites sur un graphe routier synthétique (lot O16), `list`, `build-all` avec ou sans core installé, couches OpenStreetMap `buildings`/`vegetation`/`poi`/`water` et validation et gestion des thèmes (`theme-check`, `theme-list`, `theme-install`, lot N10)) ; côté Godot, sans écran, 99 fichiers de tests unitaires lancés par découverte, 15 tests de rendu, les couches OSM, l'ERG, le rendu par tronçons et 8 scénarios IPC, plus le bout en bout, les tests graphiques et le banc simulé ([docs/OUTILS_DE_TEST.md](docs/OUTILS_DE_TEST.md)). Ils se lancent sur le PC cible (`python3 scripts/recette_pc.py`) ; la configuration GitHub Actions (Python 3.11 / 3.14 et Godot 4.3) reste dans le dépôt.
- **Tests :** 1611 tests automatiques côté core (dont conformité FTMS, cohérence documentation/code, robustesse IPC, validation de `config.toml`, catalogue des parcours, recherche BLE sans matériel, Bluetooth simulé (trainer, Click, ceinture), rejeu JSONL/FIT, endurance de 3 h, validation FIT par `garmin-fit-sdk`, analyseur de journal, historique des séances, raccourci de bureau `.desktop`, rampe de pente du trainer et outils d'entraînements `.zwo`, `.erg` et `.mrc`) et 424 côté compilateur (dont contrat des biomes (lot U1), traces FIT et TCX, mesures du monde ouvert et décodeur de tuiles vectorielles (lot W0), bibliothèque de parcours (fiches, tri, filtres, packs, lot O15), recettes de cols construites sur un graphe routier synthétique (lot O16), `list`, `build-all` avec ou sans core installé, couches OpenStreetMap `buildings`/`vegetation`/`poi`/`water` et validation et gestion des thèmes (`theme-check`, `theme-list`, `theme-install`, lot N10)) ; côté Godot, sans écran, 99 fichiers de tests unitaires lancés par découverte, 15 tests de rendu, les couches OSM, l'ERG, le rendu par tronçons et 8 scénarios IPC, plus le bout en bout, les tests graphiques et le banc simulé ([docs/OUTILS_DE_TEST.md](docs/OUTILS_DE_TEST.md)). Ils se lancent sur le PC cible (`python3 scripts/recette_pc.py`) ; la configuration GitHub Actions (Python 3.11 / 3.14 et Godot 4.3) reste dans le dépôt.

## Version

Le numéro de version unique est dans le fichier `VERSION` (lot O2) ; les notes de chaque version sont dans `CHANGELOG.md`. Pour le lire : `openride --version`, `openride-core --version` ou `openride-compiler --version`, ou la première ligne du journal du lanceur (`[openride] OpenRide 0.9.0`). Pour le changer : `scripts/bump-version.sh X.Y.Z` (met à jour `VERSION`, les deux `pyproject.toml`, `engine/project.godot` et le titre de la première section du `CHANGELOG.md`, sans commit ni étiquette), puis réinstaller les paquets ; `core/tests/test_version.py` vérifie que tout concorde.

Installation manuelle, pour le développement :

```bash
sudo apt install python3-venv python3-pip bluez
cd Open_ride_linux/core
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Les versions de référence validées en Python 3.14 sont figées dans `constraints.txt` (`pip install -c ../constraints.txt -e ".[dev]"` ; mettre ce fichier à jour après une montée de version testée).

Compilateur de parcours (GPX vers `.world`, couches route, terrain, bâtiments, végétation (dont prés et champs, lot P22), points d'intérêt, eau et routes voisines) : `cd Open_ride_linux/compiler && pip install -e ".[dev]" -e ../core && pytest -q`, puis `openride-compiler build trace.gpx` (ou directement l'export Garmin Connect : `build sortie.fit`, `build sortie.tcx`, lot M7, ou l'archive telle que Garmin la livre, `.fit.gz`, `.tcx.gz` ou `.zip`, lot O5 ; `verify`, `info`, `list` et `build-all` pour contrôler ou compiler tout `~/OpenRide/GPX/` ; `--layers route,terrain,buildings,vegetation,poi,water,roads,segments` pour inclure les couches OpenStreetMap ; la couche `segments`, montées et sprints de la série T, est produite par défaut quand le core est installé, avec le fichier facultatif `<trace>.segments.toml` posé à côté de la trace, lot T3). Le premier `build` télécharge les tuiles d'altitude Copernicus dans `~/.cache/openride/dem/` et les réponses Overpass dans `~/.cache/openride/osm/` ; ensuite `--offline` suffit, et `add-layer <dossier.world> terrain|buildings|vegetation|poi|water|roads|segments` régénère une couche seule.

**Déposer une sortie Garmin (lot O5) :** il suffit de copier le fichier exporté de Garmin Connect, tel quel, dans `~/OpenRide/GPX/` : `.gpx`, `.fit`, `.tcx`, `.fit.gz`, `.tcx.gz` ou `.zip` (la première trace `.fit`, `.tcx` ou `.gpx` de l'archive, par ordre alphabétique, est lue). Au lancement suivant, OpenRide la compile et elle apparaît dans la liste des parcours. Deux fichiers qui donnent le même nom de parcours (`col.gpx` et `col.fit`) : seul le premier dans l'ordre `.gpx`, `.fit`, `.fit.gz`, `.tcx`, `.tcx.gz`, `.zip` est pris, l'autre est signalé par `list` et `build-all`. Une archive vide, abîmée ou de plus de 50 Mo une fois décompressée est refusée avec un message, sans empêcher la compilation des autres traces.

**Bibliothèque de parcours (lot O15) :** chaque parcours a une fiche calculée à la compilation (distance, dénivelé positif et négatif, pente maximale sur 100 m, montée principale et sa catégorie de 4 à HC, durée estimée, difficulté de 1 à 5), recalculée à la lecture pour un `.world` plus ancien. Une fiche saisie facultative se pose à côté de la trace, sous le même nom : `col.toml` à côté de `col.gpx`, avec `name`, `description`, `region` (texte libre, jamais de coordonnées), `tags` (`["col", "classique"]`) et `credits`. `openride-compiler list --tag col --sort deniv --reverse --min-km 10 --max-km 40` trie et filtre (aussi `--region`, `--status`, `--max-difficulty`, `--ftp` pour la durée estimée, défaut la FTP de `config.toml`, et `--json` pour les fiches complètes). `openride-compiler route-pack-install pack.zip` installe un pack de parcours (dossier ou `.zip` de traces, de leurs fiches `.toml` et d'un `pack.toml` facultatif : `name`, `description`, `license`, `credits`) dans `~/OpenRide/GPX/<pack>/` après contrôle (chemins sûrs, pas de lien, 200 Mo au plus, fiches valides, aucun autre fichier) ; `build-all` le compile ensuite et `route-pack-list` liste les packs installés.

**Pack de départ « Cols célèbres » (lot O16) :** le dépôt ne contient aucune trace, seulement 16 recettes (`compiler/src/openride_compiler/route_packs/cols_celebres/`) : Alpe d'Huez, Mont Ventoux, Galibier, Tourmalet, Teide, Stelvio, Zoncolan, Angliru, Grand Colombier, Madeleine, Grand Ballon, Planche des Belles Filles, Ballon d'Alsace, Fuji Subaru Line, Norikura Echo Line et Irohazaka. `openride-compiler route-pack-build cols_celebres --install` télécharge une fois les routes OpenStreetMap autour de chaque col (cache `~/.cache/openride/osm/`, ensuite `--offline` suffit), relie départ et sommet par la plus courte route ouverte aux vélos (sens uniques respectés, chemins non revêtus exclus), prend l'altitude Copernicus, refuse un col dont la longueur ou le dénivelé s'écarte de plus de 5 % de la référence, puis installe le pack ; `build-all` le compile. `--only alpe_d_huez,grand_ballon` limite la construction. Crédits : © contributeurs OpenStreetMap, ODbL ; altitude Copernicus GLO-30.

Raccourcis de bureau et icône utilisateur (sans `sudo`, depuis `Open_ride_linux/`, appelé par `install.sh`) : `scripts/install-desktop.sh` installe `~/.local/share/applications/openride.desktop`, `openride-release.desktop` (`openride --release-trainer`), `openride-update.desktop` et l'icône `scripts/desktop/openride.svg` (`scripts/install-desktop.sh --uninstall` pour les retirer).

Godot 4.3 (version standard, pas .NET) :

```bash
mkdir -p ~/Applications/godot && cd ~/Applications/godot
wget https://github.com/godotengine/godot/releases/download/4.3-stable/Godot_v4.3-stable_linux.x86_64.zip
unzip Godot_v4.3-stable_linux.x86_64.zip && chmod +x Godot_v4.3-stable_linux.x86_64
```

Tests côté Godot, sans écran (depuis `Open_ride_linux/`) :

```bash
GODOT=~/Applications/godot/Godot_v4.3-stable_linux.x86_64 engine/tests/run_engine_tests.sh
GODOT=~/Applications/godot/Godot_v4.3-stable_linux.x86_64 engine/tests/run_e2e.sh
GODOT=~/Applications/godot/Godot_v4.3-stable_linux.x86_64 engine/tests/run_visual_tests.sh --open
```

Le premier script lance les tests unitaires de `engine/tests/unit/` (vecteurs de route, thèmes…), le rendu par tronçons, l'ERG, puis joue 8 scénarios IPC face à un faux core (`engine/tests/README.md`). Le second fait un essai de bout en bout avec le vrai core (trainer simulé) et le vrai engine, dans un dossier personnel temporaire, en une dizaine de secondes. Le troisième fait les tests graphiques de la scène principale, sans rien à faire (deux minutes environ) : l'engine est rendu sous Xvfb en 1280×720, 1920×1080 et 1024×600, ses captures d'écran sont analysées (textes et mise en page du HUD, bandeau, ciel et sol, caméra qui avance puis se fige) et comparées aux images de référence, et `--open` ouvre le rapport (`~/OpenRide/visual_tests/<date>/rapport.html`) ; paquets : `xvfb`, `xauth`, `libgl1-mesa-dri` (détail : `engine/tests/README.md`).

**Arguments de l'engine** (après `--`, hors contrat IPC) :

| Argument | Défaut | Rôle |
| --- | --- | --- |
| `--ipc-state-port=N` | 5005 | Port d'écoute des trames du core ; s'il est occupé, l'engine quitte avec le code 1 |
| `--ipc-cmd-port=N` | 5006 | Port de commandes du core |
| `--routes-dir=CHEMIN` | `~/.local/share/openride/routes` | Dossier des parcours `<route_id>.world` (repli sur la démo embarquée pour `demo`) |
| `--visual-grade=K` | 1.0 | Facteur d'exagération visuelle du relief (borné entre 1.0 et 2.0, lot Q2) |
| `--test-mode` | absent | Journal `[test]` pour les tests sans écran |

Exemple : `godot --path engine -- --ipc-state-port=5005 --ipc-cmd-port=5006`. `scripts/openride-dev.sh` passe les ports de `config.toml`.

## Lancer une séance

Depuis `Open_ride_linux/`, un seul terminal suffit :

```bash
scripts/openride-dev.sh                                          # HomeTrainer + Click, démarrage immédiat
scripts/openride-dev.sh --trainer ftms --input click --gear 6 --autostart
scripts/openride-dev.sh --trainer mock --input keyboard --autostart   # sans vélo
scripts/openride-dev.sh --trainer sim --input sim --hr sim --autostart   # sans matériel, Bluetooth simulé
scripts/openride-dev.sh --trainer ftms --input click --autostart --workout sweet_spot_3x10   # entraînement ERG
scripts/openride-dev.sh --trainer ftms --input click --autostart --route <parcours>          # parcours compilé
```

- Le script lance le core en arrière-plan, puis la fenêtre Godot.
- **Sans matériel :** `--trainer sim`, `--input sim` et `--hr sim` font tourner les vrais pilotes contre un HomeTrainer, une paire de Zwift Click et une ceinture cardio simulés ; `--sim-scenario` rejoue les pannes vues aux essais (réveil tardif, erreur 0x80, connexions lentes, coupures). Voir [docs/SIMULATION_BLE.md](docs/SIMULATION_BLE.md).
- Avec `--autostart`, `--route ID` choisit le parcours `~/.local/share/openride/routes/<ID>.world` (défaut : `demo`) et `--workout ID` l'entraînement ERG `~/OpenRide/Workouts/<ID>.zwo` (ou `.erg`, `.mrc`) (sans lui : mode SIM). Un parcours ou un entraînement refusé arrête le core aussitôt, avec un message dans le journal (code 1) ; sans `--autostart`, ces deux options sont refusées.
- Nouveau lanceur équivalent, installé avec le core (lot K6) : `openride [options de openride-core run] [--no-compile] [--compile-only] [--compile-timeout SECONDES]`, par exemple `openride --trainer mock --input keyboard --autostart`. Sans option, il démarre sans `--autostart` (lot N6) et ouvre d'abord l'écran « Connexion des appareils » (lot N13) : il passe seul au menu quand tout est relié, ou « Passer » (par exemple avec un seul boîtier du Click) ; Réglages → « Appareils » recherche et enregistre le matériel dans `~/OpenRide/config.toml`, puis « Relancer OpenRide » redémarre tout avec les nouveaux appareils. Le menu principal (lot N15) propose « Parcours : … », « Session libre », « Session ERG » (sous-menu du lot N16 : choisir un entraînement, en créer un par intervalles ou importer un fichier `.zwo`, `.erg` ou `.mrc` des Téléchargements, du Bureau ou de `~/OpenRide/Import`), « Session simulée » (OpenRide redémarre sur le HomeTrainer, le Click et la ceinture simulés, puis « Revenir au matériel réel »), « Réglages » (lots O3 et O4 : FTP, poids, difficulté en curseur, braquet de départ, qualité et thème, écrits dans `~/OpenRide/config.toml` ; le même curseur de difficulté est sur l'écran de pause ; aussi `openride-core settings [set CLÉ VALEUR]`) et « Quitter ». Ensuite parcours, entraînement, pause, fin et bilan se choisissent dans les menus de Godot, au Click (+ / − pour choisir, appui long + pour valider, appui long − pour revenir, bouton Y du boîtier droit pour la pause) ou au clavier (flèches, Entrée, Échap ; P, Espace ou Échap pendant la séance pour la pause). Il compile au démarrage les nouvelles traces GPX de `~/OpenRide/GPX/` avec notification de bureau (lot N11) et, en plus, relance Godot s'il plante (3 fois en 2 minutes au plus, la séance passe en pause si Godot reste absent plus de 2 s). Si le core plante pendant une séance, il relâche le trainer et relance le core avec `--resume` sans fermer Godot : la séance reprend en pause au même endroit, dans le même journal (lot N8, 3 relances en 10 minutes au plus, puis `openride-core recover`).
- Fermer la fenêtre, Ctrl+C ou fermer le terminal arrête le core proprement : la consigne (pente ou ERG) est annulée, le contrôle FTMS est rendu au trainer (Reset), le Bluetooth est déconnecté et le FIT écrit. Une autre application peut alors utiliser le HomeTrainer.
- Si le HomeTrainer reste réservé après un arrêt brutal (processus tué, PC éteint en pleine séance) : `openride-core release-trainer` annule la consigne, rend le contrôle et déconnecte le trainer. À défaut : `bluetoothctl disconnect <adresse>`.
- **Journal :** `~/run_trainer.log` (trace détaillée des commandes FTMS et accusés activable par `[trainer] trace_ftms = true` ou `--trace-ftms`, lot Q3 ; avec `openride`, lien vers le dernier journal du lanceur, `~/OpenRide/Logs/openride_AAAA-MM-JJ_HH-MM-SS.log` : sortie du core, de Godot préfixée `[engine]` et messages du lanceur `[openride]` ; 20 derniers lancements et 200 Mo gardés ; `OPENRIDE_LOG=fichier` remplace ce journal tournant) ; **FIT :** `~/OpenRide/Activities/`.
- **Si Godot est installé ailleurs :** `GODOT=/chemin/vers/godot scripts/openride-dev.sh …`.

**Commandes pendant la séance :**

| Action | Click |
| --- | --- |
| Braquet + 1 / − 1 | Appui court + / − (ou B) |
| Braquet + 10 / − 10 (bornés de 1 à 24) | Appui long (≥ 0,9 s) + / − (ou B) |
| Pause et reprise de la séance | Y (boîtier droit) |
| ERG : intensité ± 2 % ; ± 10 % | Appui court + / − (ou B) ; appui long |
| ERG : bloc suivant | Z |

Chaque type d'appui a son bip. Les menus suivent le même plan de boutons (+ / − pour choisir, A long pour valider, Y pour revenir ; [spécification générale](docs/SPECIFICATION_GENERALE.md) §7.1). Le clavier double le Click touche pour touche, avec les mêmes durées d'appui (lot O17) : `+` (ou `=`), `-`, `A`, `Y`, `Z` et les flèches ; `Page haut`, `Page bas`, `Maj+A`, `Entrée` et `Maj+Z` font l'appui long d'un coup, `Échap` vaut Y ([guide](docs/GUIDE_UTILISATION.md) §6).

**Difficulté du trainer :**
Le paramètre `[trainer] difficulty_pct` (de 0 à 100 %, défaut 50 %) réduit proportionnellement la pente envoyée au trainer, à l'image du réglage de difficulté de Zwift, sans altérer la vitesse virtuelle calculée par la physique. La difficulté est modifiable pendant la séance par la commande IPC `set_difficulty` (`{"pct": nombre}`) et son pourcentage se lit dans le menu Réglages et sur l'écran de pause ; il n'est pas affiché en permanence dans le HUD (décision du 27 octobre).

### Sons du parcours et sons personnalisés (Lot E4)

L'engine synthétise ses sons procéduraux au démarrage (vent qui suit la vitesse, roue libre en coupant l'effort, cloches d'église, rivières, bétail, village). Un fichier audio OGG déposé dans `~/OpenRide/Sounds/<nom>.ogg` (par exemple `wind.ogg`, `freewheel.ogg`, `church_bell.ogg`, `river.ogg`, `livestock.ogg`, `village.ogg`) remplace automatiquement le son généré correspondant, y compris les jingles du mode classique (sommet, sprint, arche, fin de séance, lot T17 : `jingle_summit.ogg`, `jingle_arch.ogg`, etc.).

**Commandes utiles du core :**

```bash
openride-core run --trainer ftms|mock|sim --input click|keyboard|none|sim [--hr none|ble|sim] [--sim-scenario NOM] [--gear N] [--replay CHEMIN] [--trace-ftms] [--autostart [--route ID] [--workout ID]] [--resume JOURNAL]
openride-core recover            # transforme le dernier journal en FIT après un plantage
openride-core release-trainer    # libère le HomeTrainer resté réservé (consigne annulée, contrôle FTMS rendu, déconnexion)
openride-core summary [CHEMIN] [--ftp W] [--json]   # bilan : NP, IF, TSS, zones, meilleures puissances
openride-core history [--dir DOSSIER] [--weeks N] [--ftp W] [--json]   # historique et cumul par semaine ISO
openride-core xp [--dir DOSSIER] [--json]   # progression (série V) : niveau, expérience, défis, depuis le journal
python -m openride_core.tools.log_report [~/run_trainer.log] [--json] [--all]   # analyse le journal de séance (connexions, Click, commandes FTMS et délais)
python -m openride_core.tools.estimate_cp [--dir DOSSIER] [--days N] [--ftp W] [--json]   # estime CP et W' depuis les séances passées (série R, lot R16) ; n'écrit rien dans la configuration
python -m openride_core.tools.rogue_sim [--objective threshold] [--duration 45] [--runs 200] [--all-objectives] [--sensitivity] [--json FICHIER]   # runs Cyber-Rogue simulées avec des cyclistes types : rapport d'équilibrage (série R, lot R7)
python -m openride_core.tools.workouts install                   # copie les 7 entraînements de référence (5 .zwo, un .erg, un .mrc)
python -m openride_core.tools.workouts install --erg-relative    # idem, .erg convertis en .mrc (% de la FTP de leur en-tête)
python -m openride_core.tools.workouts list                      # liste les entraînements de ~/OpenRide/Workouts/
python -m openride_core.tools.workouts check FICHIER.zwo --ftp 250   # vérifie un fichier .zwo, .erg ou .mrc et estime NP/IF/TSS
```

### Plans d'entraînement (lot O11)

Un plan range des entraînements de la bibliothèque `~/OpenRide/Workouts/` par semaine et par jour, dans `~/OpenRide/Plans/<id>.toml` (format : [docs/contracts/plan_format_v1.md](docs/contracts/plan_format_v1.md)). `openride-core plan install` copie les deux plans de référence (« Reprise 4 semaines » et « FTP 6 semaines ») et les entraînements qu'ils utilisent, sans rien écraser ; `plan list` les montre (un plan invalide apparaît avec son erreur), `plan show ID` donne la durée et le TSS de chaque semaine, `plan start ID [--date AAAA-MM-JJ]` le démarre et `plan stop` l'arrête. `plan today` dit quelle séance faire aujourd'hui, celles en retard (rattrapables pendant 3 jours) et le pourcentage fait : une séance compte si une séance enregistrée porte le même entraînement et a duré au moins 80 % du temps prévu. `plan import DOSSIER --name NOM --days mardi,jeudi,samedi` transforme un dossier d'entraînements numérotés (`w1d1`, `w1d2`, …) en plan. Le choix d'un plan depuis le menu viendra au lot O12.

### Test de FTP (lot O10)

Deux tests se roulent comme un entraînement, de préférence sur une boucle (un parcours avec arrivée termine la séance) : `openride-core run --autostart --route ID --ftp-test ramp` (paliers d'une minute, +20 W à partir de 100 W, jusqu'à ne plus tenir ; FTP = 75 % de la meilleure minute) ou `--ftp-test 20min` (échauffement guidé de 20 min, puis 20 min à fond sans cible ; FTP = 95 % de la moyenne). La rampe s'arrête d'elle-même quand la cadence reste sous 50 tr/min pendant 5 s ou la puissance sous 80 % de la cible pendant 10 s, ou sur Z, le geste du bloc suivant (abandon) : la séance passe alors au retour au calme, 5 min à 100 W. Le résultat est écrit à la fin du journal et affiché par `openride-core summary`. Dans un plan, les journées `ftp_test:ramp` et `ftp_test:20min` lancent ces tests.

```bash
openride-core ftp-test             # dernier test : FTP proposée, FTP actuelle, écart et avertissements
openride-core ftp-test --accept    # écrit la nouvelle FTP dans ~/OpenRide/config.toml (copie config.toml.bak)
openride-core ftp-test --history   # tous les tests trouvés dans les journaux
```

Un résultat douteux (test trop court, pause ou coupure du trainer pendant l'effort) n'est enregistré qu'avec `--accept --force`. Le choix du test et l'acceptation depuis le menu viendront au lot O12.

## Diagnostic matériel

HomeTrainer et Click doivent être déconnectés de Zwift et du téléphone.

Le Zwift Click récent est une paire de boîtiers (« + » et « − ») de même nom : OpenRide se connecte aux deux, et ignore les appuis du « + » que le « − » relaie en double. Avec un seul boîtier, le second est simplement cherché en arrière-plan. Le bouton B du boîtier droit fait aussi « − » : sans passage récent par l'appli Zwift (moins de 24 h), le boîtier gauche cesse d'envoyer ses boutons environ une minute après la connexion, et seul le droit reste utilisable.

Pour remplir `trainer_address`, `click_address` et `hr_address` de `config.toml`, `openride-core devices` recherche les appareils (8 s), les classe (trainer, boîtiers du Click, ceinture ou montre), signale ceux que BlueZ garde connectés et affiche le bloc `[drivers]` à recopier, avec les différences par rapport à la configuration (`--json`, `--all`, `--sim-scenario demo` pour un essai sans matériel). Avec `--save` (lot N12), il demande un appui sur le bouton « + » du Click pour reconnaître ce boîtier, montre les changements, demande confirmation (sauf `--yes`) et écrit le nom et l'adresse du trainer, les deux boîtiers (`click_address` pour le « + », `click_minus_address` pour le « − ») et la ceinture dans `~/OpenRide/config.toml` (ou `--config`), en gardant les commentaires et les autres réglages, avec une copie `config.toml.bak`. Ces valeurs réelles restent sur le PC, jamais dans le dépôt.

```bash
openride-core devices
openride-ble-diag scan
openride-ble-diag trainer --name "HomeTrainer" --duration 30
openride-ble-diag trainer --name "HomeTrainer" --control --sim-grade 4 --erg 150
openride-ble-diag click --duration 60
openride-ble-diag trace ~/run_trainer.log   # analyse d'une trace brute du Click
```

Diagnostic du Zwift Click V2 : `[drivers] click_trace_raw = true` (trace brute par notification), `click_mute_after_s = 60` (détection de boîtier muet) et `click_rehandshake_s = 30` (tentatives de reprise échelonnées : renvoi de RideOn, réabonnement, reconnexion). Voir `docs/DIAG_CLICK_GAUCHE.md` et la recherche publique `docs/RECHERCHE_CLICK_GAUCHE.md` (verrou du boîtier gauche par Zwift).

Les rapports sont écrits dans `spike_reports/`.

**Si le Click ne répond plus :** `bluetoothctl disconnect <adresse du Click>`, puis appuyer sur un bouton.
