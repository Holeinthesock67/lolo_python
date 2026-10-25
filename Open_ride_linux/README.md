# OpenRide Linux

[![Tests OpenRide](https://github.com/Holeinthesock67/lolo_python/actions/workflows/openride.yml/badge.svg)](https://github.com/Holeinthesock67/lolo_python/actions/workflows/openride.yml)

Simulateur de cyclisme indoor 3D à usage personnel, natif Linux, plus léger que Zwift.
Matériel de référence : home trainer HomeTrainer (FTMS), Zwift Cog, Zwift Click, PC Ubuntu.

## Documents de référence (à fournir à l'IA au début de chaque session)

Avec Claude Code, lancer `claude` depuis `Open_ride_linux/` : le fichier `CLAUDE.md` est lu automatiquement, et les commandes `/tests`, `/seance` et `/lot` sont disponibles.

- `docs/SRS_v1.1.md` : spécification logicielle
- `docs/contracts/ipc_v1.md` : contrat de messages core ↔ engine
- `docs/contracts/world_format_v1.md` : format des parcours compilés `.world`
- `docs/SUIVI_AVANCEMENT.md` : état d'avancement, tests effectués et tests restants
- `docs/AUDIT_2026-10-23.md` : audit du projet (constats et recommandations, complété le soir : §8 et §9)
- `docs/VERIFICATION_2026-10-24.md`, `docs/AUDIT_FTMS_2026-10-24.md` et `docs/REVUE_CODE_2026-10-24.md` : vérification, audit FTMS et revue de code du 24 octobre
- `docs/lots/` : cahiers des charges des lots confiables à une autre IA (commencer par `00_INDEX.md`)
- `docs/spikes.md` : faits mesurés sur le matériel (sprint 0)

## Structure

```text
Open_ride_linux/
  docs/        spécifications, contrats, audit, lots
  core/        openride-core (Python) : BLE, physique, braquets, journal, FIT, IPC
  engine/      openride-engine (Godot 4.3) : rendu, HUD
  scripts/     outils de lancement (openride-dev.sh)
  compiler/    openride-compiler (Python) : GPX vers .world, couches route et terrain (lots B1 et B2)
```

## État (23 octobre 2026 au soir, après les lots A, A2, B1, B2, C, D, F, H1 à H8, I1 à I6, J2 et J3)

- **Sprint 0 terminé :** HomeTrainer, Click et FIT validés sur le matériel.
- **Sprint 1 presque terminé :**
  - pilotes réels du HomeTrainer et du Click ;
  - boucle de séance (`openride-core run`) ;
  - Godot relié au core ;
  - conformité au contrat IPC (lot C) ;
  - lecture des parcours `.world`, commune au core et à Godot (lot A) ;
  - Godot conforme au contrat : renvoi des commandes, extrapolation de la caméra, core injoignable (lot D) ;
  - 502 tests automatiques côté core (dont conformité FTMS, cohérence documentation/code, robustesse IPC, validation de `config.toml`, catalogue des parcours, recherche BLE sans matériel, Bluetooth simulé (trainer, Click, ceinture), rejeu JSONL/FIT, endurance de 3 h, validation FIT par `garmin-fit-sdk`, analyseur de journal, historique des séances, raccourci de bureau `.desktop` et outils d'entraînements `.zwo`) et 183 côté compilateur (dont traces FIT et TCX, `list`, `build-all` avec ou sans core installé, couches OpenStreetMap `buildings`/`vegetation`/`poi`/`water` et validation et gestion des thèmes (`theme-check`, `theme-list`, `theme-install`, lot N10)) ; côté Godot, sans écran, des tests unitaires lancés par découverte (42 vecteurs de route, 40 vérifications de thèmes, 76 du modèle de HUD, 19 de la végétation, 19 des menus), 27 vérifications des couches OSM, 54 vérifications ERG, le rendu par tronçons et 8 scénarios IPC, exécutés en intégration continue GitHub Actions (Python 3.11 / 3.14 et Godot 4.3).
  - **Reste :** séance de 10 minutes et stabilité du Click.
- **Sprint 2 terminé côté code :** compilateur GPX vers `.world`, couches route (lot B1) et terrain avec le MNT Copernicus (lot B2). Reste la comparaison avec Garmin Connect sur une vraie trace.
- **Sprint 3 en cours :** ruban de route et terrain par tronçons (lot E1, fusionné le 24 octobre ; reste l'essai sur la GTX 1060) ; chargeur de thèmes et logique du bandeau ERG côté Godot prêts (lots I5 et I6), à brancher sur l'affichage (E2, F2).
- **Entraînements ERG** (lot F) livrés côté core ; essai sur le HomeTrainer à faire.
  - Le parcours utilisé est le parcours de démonstration `demo`, créé automatiquement dans `~/.local/share/openride/routes/` (le choix d'un autre parcours ou d'un entraînement au lancement est prévu par le lot J1).

## Installation (PC Ubuntu)

```bash
sudo apt install python3-venv python3-pip bluez
cd Open_ride_linux/core
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Les versions de référence validées en Python 3.14 sont figées dans `constraints.txt` (`pip install -c ../constraints.txt -e ".[dev]"` ; mettre ce fichier à jour après une montée de version testée).

Compilateur de parcours (GPX vers `.world`, couches route, terrain, bâtiments, végétation, points d'intérêt et eau) : `cd Open_ride_linux/compiler && pip install -e ".[dev]" -e ../core && pytest -q`, puis `openride-compiler build trace.gpx` (ou directement l'export Garmin Connect : `build sortie.fit`, `build sortie.tcx`, lot M7 ; `verify`, `info`, `list` et `build-all` pour contrôler ou compiler tout `~/OpenRide/GPX/` ; `--layers route,terrain,buildings,vegetation,poi,water` pour inclure les couches OpenStreetMap). Le premier `build` télécharge les tuiles d'altitude Copernicus dans `~/.cache/openride/dem/` et les réponses Overpass dans `~/.cache/openride/osm/` ; ensuite `--offline` suffit, et `add-layer <dossier.world> terrain|buildings|vegetation|poi|water` régénère une couche seule.

Raccourci de bureau et icône utilisateur (sans `sudo`, depuis `Open_ride_linux/`) : `scripts/install-desktop.sh` installe `~/.local/share/applications/openride.desktop` et l'icône `scripts/desktop/openride.svg` (`scripts/install-desktop.sh --uninstall` pour les retirer).

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
- Avec `--autostart`, `--route ID` choisit le parcours `~/.local/share/openride/routes/<ID>.world` (défaut : `demo`) et `--workout ID` l'entraînement ERG `~/OpenRide/Workouts/<ID>.zwo` (sans lui : mode SIM). Un parcours ou un entraînement refusé arrête le core aussitôt, avec un message dans le journal (code 1) ; sans `--autostart`, ces deux options sont refusées.
- Nouveau lanceur équivalent, installé avec le core (lot K6) : `openride [options de openride-core run] [--no-compile] [--compile-only] [--compile-timeout SECONDES]`, par exemple `openride --trainer mock --input keyboard --autostart`. Il compile au démarrage les nouvelles traces GPX de `~/OpenRide/GPX/` avec notification de bureau (lot N11) et, en plus, relance Godot s'il plante (3 fois en 2 minutes au plus, la séance passe en pause si Godot reste absent plus de 2 s). Si le core plante, il ferme Godot et rappelle `openride-core recover`.
- Fermer la fenêtre, Ctrl+C ou fermer le terminal arrête le core proprement : la consigne (pente ou ERG) est annulée, le contrôle FTMS est rendu au trainer (Reset), le Bluetooth est déconnecté et le FIT écrit. Une autre application peut alors utiliser le HomeTrainer.
- Si le HomeTrainer reste réservé après un arrêt brutal (processus tué, PC éteint en pleine séance) : `openride-core release-trainer` annule la consigne, rend le contrôle et déconnecte le trainer. À défaut : `bluetoothctl disconnect <adresse>`.
- **Journal :** `~/run_trainer.log` (avec `openride`, lien vers le dernier journal du lanceur, `~/OpenRide/Logs/openride_AAAA-MM-JJ_HH-MM-SS.log` : sortie du core, de Godot préfixée `[engine]` et messages du lanceur `[openride]` ; 20 derniers lancements et 200 Mo gardés ; `OPENRIDE_LOG=fichier` remplace ce journal tournant) ; **FIT :** `~/OpenRide/Activities/`.
- **Si Godot est installé ailleurs :** `GODOT=/chemin/vers/godot scripts/openride-dev.sh …`.

**Commandes pendant la séance :**

| Action | Click | Clavier (fenêtre Godot) |
| --- | --- | --- |
| Braquet + 1 / − 1 | Appui court + / − (ou B) | `+` / `−` ou flèches haut / bas |
| Braquet + 10 / − 10 (bornés de 1 à 24) | Appui long (≥ 0,9 s) + / − (ou B) | `Page haut` / `Page bas` |

Chaque type d'appui a son bip.

### Sons du parcours et sons personnalisés (Lot E4)

L'engine synthétise ses sons procéduraux au démarrage (vent qui suit la vitesse, roue libre en coupant l'effort, cloches d'église, rivières, bétail, village). Un fichier audio OGG déposé dans `~/OpenRide/Sounds/<nom>.ogg` (par exemple `wind.ogg`, `freewheel.ogg`, `church_bell.ogg`, `river.ogg`, `livestock.ogg`, `village.ogg`) remplace automatiquement le son généré correspondant.

**Commandes utiles du core :**

```bash
openride-core run --trainer ftms|mock|sim --input click|keyboard|none|sim [--hr none|ble|sim] [--sim-scenario NOM] [--gear N] [--replay CHEMIN] [--autostart [--route ID] [--workout ID]]
openride-core recover            # transforme le dernier journal en FIT après un plantage
openride-core release-trainer    # libère le HomeTrainer resté réservé (consigne annulée, contrôle FTMS rendu, déconnexion)
openride-core summary [CHEMIN] [--ftp W] [--json]   # bilan : NP, IF, TSS, zones, meilleures puissances
openride-core history [--dir DOSSIER] [--weeks N] [--ftp W] [--json]   # historique et cumul par semaine ISO
python -m openride_core.tools.log_report [~/run_trainer.log] [--json] [--all]   # analyse le journal de séance
python -m openride_core.tools.workouts install                   # copie les 5 entraînements .zwo de référence
python -m openride_core.tools.workouts list                      # liste les entraînements de ~/OpenRide/Workouts/
python -m openride_core.tools.workouts check FICHIER.zwo --ftp 250   # vérifie un fichier .zwo et estime NP/IF/TSS
```

## Diagnostic matériel

HomeTrainer et Click doivent être déconnectés de Zwift et du téléphone.

Le Zwift Click récent est une paire de boîtiers (« + » et « − ») de même nom : OpenRide se connecte aux deux, et ignore les appuis du « + » que le « − » relaie en double. Avec un seul boîtier, le second est simplement cherché en arrière-plan. Le bouton B du boîtier droit fait aussi « − » : sans passage récent par l'appli Zwift (moins de 24 h), le boîtier gauche cesse d'envoyer ses boutons environ une minute après la connexion, et seul le droit reste utilisable.

Pour remplir `trainer_address`, `click_address` et `hr_address` de `config.toml`, `openride-core devices` recherche les appareils (8 s), les classe (trainer, boîtiers du Click, ceinture ou montre), signale ceux que BlueZ garde connectés et affiche le bloc `[drivers]` à recopier, avec les différences par rapport à la configuration (`--json`, `--all`, `--sim-scenario demo` pour un essai sans matériel).

```bash
openride-core devices
openride-ble-diag scan
openride-ble-diag trainer --name "HomeTrainer" --duration 30
openride-ble-diag trainer --name "HomeTrainer" --control --sim-grade 4 --erg 150
openride-ble-diag click --duration 60
```

Les rapports sont écrits dans `spike_reports/`.

**Si le Click ne répond plus :** `bluetoothctl disconnect <adresse du Click>`, puis appuyer sur un bouton.
