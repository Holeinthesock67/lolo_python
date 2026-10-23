# OpenRide Linux

Simulateur de cyclisme indoor 3D à usage personnel, natif Linux, plus léger que Zwift.
Matériel de référence : home trainer HomeTrainer (FTMS), Zwift Cog, Zwift Click, PC Ubuntu.

## Documents de référence (à fournir à l'IA au début de chaque session)

Avec Claude Code, lancer `claude` depuis `Open_ride_linux/` : le fichier `CLAUDE.md` est lu automatiquement, et les commandes `/tests`, `/seance` et `/lot` sont disponibles.

- `docs/SRS_v1.1.md` : spécification logicielle
- `docs/contracts/ipc_v1.md` : contrat de messages core ↔ engine
- `docs/contracts/world_format_v1.md` : format des parcours compilés `.world`
- `docs/SUIVI_AVANCEMENT.md` : état d'avancement, tests effectués et tests restants
- `docs/AUDIT_2026-10-23.md` : audit du projet (constats et recommandations)
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

## État (23 octobre 2026, après les lots A, A2, B1, B2, C, D et F)

- **Sprint 0 terminé :** HomeTrainer, Click et FIT validés sur le matériel.
- **Sprint 1 presque terminé :**
  - pilotes réels du HomeTrainer et du Click ;
  - boucle de séance (`openride-core run`) ;
  - Godot relié au core ;
  - conformité au contrat IPC (lot C) ;
  - lecture des parcours `.world`, commune au core et à Godot (lot A) ;
  - Godot conforme au contrat : renvoi des commandes, extrapolation de la caméra, core injoignable (lot D) ;
  - 75 tests automatiques côté core ; côté Godot, 42 vecteurs de route et 8 scénarios IPC sans écran.
  - **Reste :** séance de 10 minutes et stabilité du Click.
- **Sprint 2 terminé côté code :** compilateur GPX vers `.world`, couches route (lot B1) et terrain avec le MNT Copernicus (lot B2). Reste la comparaison avec Garmin Connect sur une vraie trace.
- **Pas encore commencés :** rendu 3D (sprint 3, lot E1) et entraînements ERG (lot F).
  - Le parcours utilisé est le parcours de démonstration `demo`, créé automatiquement dans `~/.local/share/openride/routes/`.

## Installation (PC Ubuntu)

```bash
sudo apt install python3-venv python3-pip bluez
cd Open_ride_linux/core
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Compilateur de parcours (GPX vers `.world`, couches route et terrain) : `cd Open_ride_linux/compiler && pip install -e ".[dev]" -e ../core && pytest -q`, puis `openride-compiler build trace.gpx` (`verify` et `info` pour contrôler). Le premier `build` télécharge les tuiles d'altitude Copernicus (environ 42 Mo par degré carré) dans `~/.cache/openride/dem/` ; ensuite `--offline` suffit, et `add-layer <dossier.world> terrain` régénère le terrain seul.

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
scripts/openride-dev.sh                                          # HomeTrainer + Click, démarrage immédiat
scripts/openride-dev.sh --trainer ftms --input click --gear 6 --autostart
scripts/openride-dev.sh --trainer mock --input keyboard --autostart   # sans vélo
```

- Le script lance le core en arrière-plan, puis la fenêtre Godot.
- Fermer la fenêtre (ou Ctrl+C) arrête le core proprement : la résistance est relâchée et le FIT écrit.
- **Journal :** `~/run_trainer.log` ; **FIT :** `~/OpenRide/Activities/`.
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
```

## Diagnostic matériel

HomeTrainer et Click doivent être déconnectés de Zwift et du téléphone.

```bash
openride-ble-diag scan
openride-ble-diag trainer --name "HomeTrainer" --duration 30
openride-ble-diag trainer --name "HomeTrainer" --control --sim-grade 4 --erg 150
openride-ble-diag click --duration 60
```

Les rapports sont écrits dans `spike_reports/`.

**Si le Click ne répond plus :** `bluetoothctl disconnect <adresse du Click>`, puis appuyer sur un bouton.
