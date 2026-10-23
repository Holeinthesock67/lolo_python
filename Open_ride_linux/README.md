# OpenRide Linux

Simulateur de cyclisme indoor 3D à usage personnel, natif Linux, plus léger que Zwift.
Matériel de référence : home trainer JetBlack Victory (FTMS), Zwift Cog, Zwift Click, PC Ubuntu.

## Documents de référence (à fournir à l'IA au début de chaque session)

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
  compiler/    openride-compiler (Python) : GPX vers .world, à venir (lots B1 et B2)
```

## État (23 octobre 2026)

- **Sprint 0 terminé :** Victory, Click et FIT validés sur le matériel.
- **Sprint 1 presque terminé :**
  - pilotes réels du Victory et du Click ;
  - boucle de séance (`openride-core run`) ;
  - Godot relié au core ;
  - 42 tests automatiques.
  - **Reste :** séance de 10 minutes, stabilité du Click et corrections de conformité (lot C).
- **Pas encore commencés :**
  - lecture des vrais parcours (lot A) ;
  - compilateur GPX (sprint 2) ;
  - rendu 3D (sprint 3).
  - Le parcours utilisé est pour l'instant un parcours de démonstration.

## Installation (PC Ubuntu)

```bash
sudo apt install python3-venv python3-pip bluez
cd Open_ride_linux/core
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Godot 4.3 (version standard, pas .NET) :

```bash
mkdir -p ~/Applications/godot && cd ~/Applications/godot
wget https://github.com/godotengine/godot/releases/download/4.3-stable/Godot_v4.3-stable_linux.x86_64.zip
unzip Godot_v4.3-stable_linux.x86_64.zip && chmod +x Godot_v4.3-stable_linux.x86_64
```

## Lancer une séance

Depuis `Open_ride_linux/`, un seul terminal suffit :

```bash
scripts/openride-dev.sh                                          # Victory + Click, démarrage immédiat
scripts/openride-dev.sh --trainer ftms --input click --gear 6 --autostart
scripts/openride-dev.sh --trainer mock --input keyboard --autostart   # sans vélo
```

- Le script lance le core en arrière-plan, puis la fenêtre Godot.
- Fermer la fenêtre (ou Ctrl+C) arrête le core proprement : la résistance est relâchée et le FIT écrit.
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
openride-core run --trainer ftms|mock --input click|keyboard|none [--gear N] [--autostart]
openride-core recover            # transforme le dernier journal en FIT après un plantage
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
