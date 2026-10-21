# OpenRide Linux

Simulateur de cyclisme indoor 3D à usage personnel, natif Linux, plus léger que Zwift.

## Documents de référence (à fournir à l'IA au début de chaque session)

- `docs/SRS_v1.1.md` : spécification logicielle
- `docs/contracts/ipc_v1.md` : contrat de messages core ↔ engine
- `docs/contracts/world_format_v1.md` : format des parcours compilés `.world`
- `docs/SUIVI_AVANCEMENT.md` : état d'avancement, tests effectués et tests restants

## Structure prévue

```text
openride/
  docs/            spécifications et contrats
  core/            openride-core (Python) : BLE, physique, ERG, FIT
  compiler/        openride-compiler (Python) : GPX vers .world
  engine/          openride-engine (Godot) : rendu, HUD
```

## État du projet (Sprint 0 - Spikes en cours)

- [x] Spécifications et contrats v1 validés (`docs/`)
- [x] Package Python `openride-core` initialisé et installé en mode éditable
- [x] Modèle physique par bilan d'énergie cinétique (50 Hz, stable à l'arrêt, anti-recul)
- [x] Modèle d'étagement des braquets virtuels 24 vitesses
- [x] Décodeur / encodeur de protocole FTMS (0x2ACC, 0x2AD2, 0x2AD8, 0x2AD9, commandes 0x11 et 0x05)
- [x] Décodeur Zwift Click (handshake b"RideOn", parsing protobuf varints, classification appuis court/long)
- [x] Outil de diagnostic BLE complet : `openride-ble-diag`
- [x] Export FIT minimal (`fit-tool`) et journal continu JSONL résistant aux pannes
- [x] Outil de récupération post-crash : `openride-core recover`
- [x] Générateur synthétique de `.world` factice : `openride_core.tools.fake_world`
- [x] 29 tests unitaires passants

## Diagnostic Matériel BLE (Sprint 0)

Sur la machine connectée au matériel (Bluetooth actif) :
```bash
# 1. Scanner les périphériques
python -m openride_core.tools.ble_diag scan

# 2. Diagnostiquer le trainer HomeTrainer
python -m openride_core.tools.ble_diag trainer --name "HomeTrainer" --duration 30

# 3. Tester le contrôle de pente (SIM) et puissance cible (ERG)
python -m openride_core.tools.ble_diag trainer --name "HomeTrainer" --control --sim-grade 4 --erg 150

# 4. Diagnostiquer le Zwift Click
python -m openride_core.tools.ble_diag click --duration 60
```
Les rapports sont sauvegardés dans `spike_reports/`.
