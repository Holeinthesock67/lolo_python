# OpenRide Linux - Journal des Spikes (Sprint 0)

## Objectif
Valider les hypothèses techniques critiques avant le développement des modules finaux :
1. Diagnostic FTMS BLE (HomeTrainer) : lecture des caractéristiques, fréquences réelles, support SIM (0x11), ERG (0x05) et pont cardio.
2. Protocole Zwift Click : connexion sans chiffrement, handshake `RideOn`, capture des boutons +/- (protobuf sur caractéristique ASYNC), seuils appuis court (<500ms) et long (≥1200ms).
3. Export FIT minimal : génération de fichiers `.fit` valides conformes pour GoldenCheetah et Garmin Connect.
4. Rendu Polyligne Godot : chargement de `route.json` et affichage d'une polyligne 3D.

---

## 1. Export FIT & Journal de Session (Validé)
- **Outil** : [fit_demo.py](file:///d:/Sauvegarde/Documents/utilisateur/lolo_python/Open_ride_linux/core/src/openride_core/tools/fit_demo.py) et [fit_export.py](file:///d:/Sauvegarde/Documents/utilisateur/lolo_python/Open_ride_linux/core/src/openride_core/fit_export.py)
- **Résultats** :
  - Simulation complète 10 minutes avec variations de puissance, pente, cadence, FC et une pause de 30 secondes.
  - Génération continue du journal JSONL (avec `fsync` à chaque écriture pour résister aux crashs).
  - Conversion automatique en `.fit` valide via `fit-tool` (contenant `file_id`, `event`, `record` à 1 Hz, `lap`, `session`, `activity`).
  - Tolérance aux lignes tronquées vérifiée par tests unitaires.
  - Commande de récupération `openride-core recover [journal]` testée et fonctionnelle.

---

## 2. Outils de Diagnostic BLE (Prêts pour exécution matérielle)
- **Outil** : [ble_diag.py](file:///d:/Sauvegarde/Documents/utilisateur/lolo_python/Open_ride_linux/core/src/openride_core/tools/ble_diag.py) (`openride-ble-diag`)
- **Commandes à lancer sur le PC Linux connecté au Home Trainer / Click** :
  ```bash
  # Scanner l'environnement Bluetooth
  openride-ble-diag scan

  # Diagnostiquer le HomeTrainer (écoute notifications 30s)
  openride-ble-diag trainer --name "HomeTrainer" --duration 30

  # Tester les commandes FTMS (contrôle, sim grade 4%, erg 150W, relâchement automatique à 0%)
  openride-ble-diag trainer --name "HomeTrainer" --control --sim-grade 4 --erg 150

  # Tester le Zwift Click (handshake RideOn, appuis courts/longs)
  openride-ble-diag click --duration 60
  ```
- Les rapports d'exécution détaillés sont automatiquement enregistrés au format JSON sous `./spike_reports/`.

---

## 3. Générateur de Monde Synthétique (Sprint 0 / Godot MVP)
- **Outil** : [fake_world.py](file:///d:/Sauvegarde/Documents/utilisateur/lolo_python/Open_ride_linux/core/src/openride_core/tools/fake_world.py)
- Produit un dossier `.world` conforme au contrat [world_format_v1.md](file:///d:/Sauvegarde/Documents/utilisateur/lolo_python/Open_ride_linux/docs/contracts/world_format_v1.md) (`manifest.json` + `route.json`) pour tester l'affichage de la route dans Godot.
