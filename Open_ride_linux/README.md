# OpenRide Linux

[![Tests OpenRide](https://github.com/Holeinthesock67/lolo_python/actions/workflows/openride.yml/badge.svg)](https://github.com/Holeinthesock67/lolo_python/actions/workflows/openride.yml)

Simulateur de cyclisme indoor 3D à usage personnel, natif Linux, plus léger que Zwift.
Matériel de référence : home trainer JetBlack Victory (FTMS), Zwift Cog, Zwift Click, PC Ubuntu.

## Documents de référence (à fournir à l'IA au début de chaque session)

Avec Claude Code, lancer `claude` depuis `Open_ride_linux/` : le fichier `CLAUDE.md` est lu automatiquement, et les commandes `/tests`, `/seance` et `/lot` sont disponibles.

- `docs/SRS_v1.1.md` : spécification logicielle
- `docs/contracts/ipc_v1.md` : contrat de messages core ↔ engine
- `docs/contracts/world_format_v1.md` : format des parcours compilés `.world`
- `docs/SUIVI_AVANCEMENT.md` : état d'avancement, tests effectués et tests restants
- `docs/AUDIT_2026-10-23.md` : audit du projet (constats et recommandations, complété le soir : §8 et §9)
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

- **Sprint 0 terminé :** Victory, Click et FIT validés sur le matériel.
- **Sprint 1 presque terminé :**
  - pilotes réels du Victory et du Click ;
  - boucle de séance (`openride-core run`) ;
  - Godot relié au core ;
  - conformité au contrat IPC (lot C) ;
  - lecture des parcours `.world`, commune au core et à Godot (lot A) ;
  - Godot conforme au contrat : renvoi des commandes, extrapolation de la caméra, core injoignable (lot D) ;
  - 222 tests automatiques côté core (dont cohérence documentation/code, robustesse IPC, validation de `config.toml`, catalogue des parcours, recherche BLE sans matériel, rejeu JSONL/FIT, endurance de 3 h, validation FIT par `garmin-fit-sdk`, analyseur de journal et outils d'entraînements `.zwo`) et 123 côté compilateur (dont `list`, `build-all`, couches OpenStreetMap `buildings`/`vegetation`/`poi`/`water` et validation des thèmes `theme-check`) ; côté Godot, 42 vecteurs de route, 40 vérifications de thèmes, 54 vérifications ERG et 8 scénarios IPC sans écran, exécutés en intégration continue GitHub Actions (Python 3.11 / 3.14 et Godot 4.3).
  - **Reste :** séance de 10 minutes et stabilité du Click.
- **Sprint 2 terminé côté code :** compilateur GPX vers `.world`, couches route (lot B1) et terrain avec le MNT Copernicus (lot B2). Reste la comparaison avec Garmin Connect sur une vraie trace.
- **Sprint 3 en cours :** ruban de route et terrain par tronçons (lot E1, PR #7, en attente de l'essai sur la GTX 1060) ; chargeur de thèmes et logique du bandeau ERG côté Godot prêts (lots I5 et I6), à brancher sur l'affichage (E2, F2).
- **Entraînements ERG** (lot F) livrés côté core ; essai sur le Victory à faire.
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

Compilateur de parcours (GPX vers `.world`, couches route, terrain, bâtiments, végétation, points d'intérêt et eau) : `cd Open_ride_linux/compiler && pip install -e ".[dev]" -e ../core && pytest -q`, puis `openride-compiler build trace.gpx` (`verify`, `info`, `list` et `build-all` pour contrôler ou compiler tout `~/OpenRide/GPX/` ; `--layers route,terrain,buildings,vegetation,poi,water` pour inclure les couches OpenStreetMap). Le premier `build` télécharge les tuiles d'altitude Copernicus dans `~/.cache/openride/dem/` et les réponses Overpass dans `~/.cache/openride/osm/` ; ensuite `--offline` suffit, et `add-layer <dossier.world> terrain|buildings|vegetation|poi|water` régénère une couche seule.

Godot 4.3 (version standard, pas .NET) :

```bash
mkdir -p ~/Applications/godot && cd ~/Applications/godot
wget https://github.com/godotengine/godot/releases/download/4.3-stable/Godot_v4.3-stable_linux.x86_64.zip
unzip Godot_v4.3-stable_linux.x86_64.zip && chmod +x Godot_v4.3-stable_linux.x86_64
```

Tests côté Godot, sans écran (depuis `Open_ride_linux/`) :

```bash
GODOT=~/Applications/godot/Godot_v4.3-stable_linux.x86_64 engine/tests/run_engine_tests.sh
```

Le script vérifie les vecteurs de route, puis joue 8 scénarios IPC face à un faux core (`engine/tests/README.md`).

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
scripts/openride-dev.sh                                          # Victory + Click, démarrage immédiat
scripts/openride-dev.sh --trainer ftms --input click --gear 6 --autostart
scripts/openride-dev.sh --trainer mock --input keyboard --autostart   # sans vélo
```

- Le script lance le core en arrière-plan, puis la fenêtre Godot.
- Nouveau lanceur équivalent, installé avec le core (lot K6) : `openride [options de openride-core run]`, par exemple `openride --trainer mock --input keyboard --autostart`. Il fait la même chose et, en plus, relance Godot s'il plante (3 fois en 2 minutes au plus, la séance reste en pause pendant ce temps). Si le core plante, il ferme Godot et rappelle `openride-core recover`.
- Fermer la fenêtre, Ctrl+C ou fermer le terminal arrête le core proprement : la consigne (pente ou ERG) est annulée, le contrôle FTMS est rendu au trainer (Reset), le Bluetooth est déconnecté et le FIT écrit. Une autre application peut alors utiliser le Victory.
- Si le Victory reste réservé après un arrêt brutal (processus tué, PC éteint en pleine séance) : `openride-core release-trainer` annule la consigne, rend le contrôle et déconnecte le trainer. À défaut : `bluetoothctl disconnect <adresse>`.
- **Journal :** `~/run_victory.log` ; **FIT :** `~/OpenRide/Activities/`.
- **Si Godot est installé ailleurs :** `GODOT=/chemin/vers/godot scripts/openride-dev.sh …`.

**Commandes pendant la séance :**

| Action | Click | Clavier (fenêtre Godot) |
| --- | --- | --- |
| Braquet + 1 / − 1 | Appui court + / − | `+` / `−` ou flèches haut / bas |
| Braquet + 3 / − 3 | Appui long (≥ 0,9 s) + / − | `Page haut` / `Page bas` |

Chaque type d'appui a son bip.

**Commandes utiles du core :**

```bash
openride-core run --trainer ftms|mock --input click|keyboard|none [--gear N] [--replay CHEMIN] [--autostart]
openride-core recover            # transforme le dernier journal en FIT après un plantage
python -m openride_core.tools.log_report [~/run_victory.log] [--json] [--all]   # analyse le journal de séance
python -m openride_core.tools.workouts install                   # copie les 5 entraînements .zwo de référence
python -m openride_core.tools.workouts list                      # liste les entraînements de ~/OpenRide/Workouts/
python -m openride_core.tools.workouts check FICHIER.zwo --ftp 250   # vérifie un fichier .zwo et estime NP/IF/TSS
```

## Diagnostic matériel

Victory et Click doivent être déconnectés de Zwift et du téléphone.

```bash
openride-ble-diag scan
openride-ble-diag trainer --name "Victory" --duration 30
openride-ble-diag trainer --name "Victory" --control --sim-grade 4 --erg 150
openride-ble-diag click --duration 60
```

Les rapports sont écrits dans `spike_reports/`.

**Si le Click ne répond plus :** `bluetoothctl disconnect <adresse du Click>`, puis appuyer sur un bouton.
