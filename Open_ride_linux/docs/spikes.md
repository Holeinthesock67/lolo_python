# OpenRide Linux - Journal des Spikes (Sprint 0)

## Objectif
Valider les hypothèses techniques critiques avant le développement des modules finaux :
1. Diagnostic FTMS BLE (JetBlack Victory) : lecture des caractéristiques, fréquences réelles, support SIM (0x11), ERG (0x05) et pont cardio.
2. Protocole Zwift Click : connexion sans chiffrement, handshake `RideOn`, capture des boutons +/- (protobuf sur caractéristique ASYNC), seuils appuis court (<500ms) et long (≥1200ms).
3. Export FIT minimal : génération de fichiers `.fit` valides conformes pour GoldenCheetah et Garmin Connect.
4. Rendu Polyligne Godot : chargement de `route.json` et affichage d'une polyligne 3D.

---

## 1. Export FIT & Journal de Session (Validé)
- **Outil** : [fit_demo.py](file:///d:/Sauvegarde/Documents/Laurent/lolo_python/Open_ride_linux/core/src/openride_core/tools/fit_demo.py) et [fit_export.py](file:///d:/Sauvegarde/Documents/Laurent/lolo_python/Open_ride_linux/core/src/openride_core/fit_export.py)
- **Résultats** :
  - Simulation complète 10 minutes avec variations de puissance, pente, cadence, FC et une pause de 30 secondes.
  - Génération continue du journal JSONL (avec `fsync` à chaque écriture pour résister aux crashs).
  - Conversion automatique en `.fit` valide via `fit-tool` (contenant `file_id`, `event`, `record` à 1 Hz, `lap`, `session`, `activity`).
  - Tolérance aux lignes tronquées vérifiée par tests unitaires.
  - Commande de récupération `openride-core recover [journal]` testée et fonctionnelle.

---

## 2. Outils de Diagnostic BLE (Prêts pour exécution matérielle)
- **Outil** : [ble_diag.py](file:///d:/Sauvegarde/Documents/Laurent/lolo_python/Open_ride_linux/core/src/openride_core/tools/ble_diag.py) (`openride-ble-diag`)
- **Commandes à lancer sur le PC Linux connecté au Home Trainer / Click** :
  ```bash
  # Scanner l'environnement Bluetooth
  openride-ble-diag scan

  # Diagnostiquer le JetBlack Victory (écoute notifications 30s)
  openride-ble-diag trainer --name "Victory" --duration 30

  # Tester les commandes FTMS (contrôle, sim grade 4%, erg 150W, relâchement automatique à 0%)
  openride-ble-diag trainer --name "Victory" --control --sim-grade 4 --erg 150

  # Tester le Zwift Click (handshake RideOn, appuis courts/longs)
  openride-ble-diag click --duration 60
  ```
- Les rapports d'exécution détaillés sont automatiquement enregistrés au format JSON sous `./spike_reports/`.

---

## 3. Générateur de Monde Synthétique (Sprint 0 / Godot MVP)
- **Outil** : [fake_world.py](file:///d:/Sauvegarde/Documents/Laurent/lolo_python/Open_ride_linux/core/src/openride_core/tools/fake_world.py)
- Produit un dossier `.world` conforme au contrat [world_format_v1.md](file:///d:/Sauvegarde/Documents/Laurent/lolo_python/Open_ride_linux/docs/contracts/world_format_v1.md) (`manifest.json` + `route.json`) pour tester l'affichage de la route dans Godot.

---

## 4. Résultats sur le matériel (22 octobre 2026, PC Linux cible, Python 3.14.4, bleak 3.0.2)

### JetBlack Victory (« Victory 9908 »)
- Services présents : FTMS (0x1826), Cycling Power (0x1818), Cycling Speed and Cadence (0x1816), Heart Rate (0x180D), plus des services propriétaires.
- Capacités annoncées : vitesse moyenne, cadence, distance, niveau de résistance, fréquence cardiaque, puissance. Consignes possibles : niveau de résistance, puissance cible, simulation de piste (0x11), circonférence de roue, spin-down. Plage de puissance : 0 à 1 000 W, pas de 1 W.
- Fréquence d'Indoor Bike Data : environ 1 Hz au repos et en mode puissance (écart 0,81 à 1,17 s) ; environ 8 Hz après une commande de simulation de piste (notifications en rafale).
- Cardio : la fréquence cardiaque arrive dans Indoor Bike Data **et** par le service 0x180D ; 0 bpm au départ signifie « pas de mesure ».
- Contrôle : `request_control` (0x00), `start_resume` (0x07), simulation 4 % (0x11), puissance cible 150 W (0x05) et retour à 0 % : toutes les réponses `SUCCESS`.
- Mode puissance : 150 W atteint en 1 à 4 s, tenu entre 147 et 154 W alors que la cadence passe de 43 à 39 tr/min.
- Mode pente : la vitesse affichée par le trainer baisse de 24,7 à environ 19 km/h en 7 à 8 s après la commande ; léger retard ressenti. `latency_tau_s` (0,8 s) à ajuster à l'usage.
- La cadence arrive 2 à 3 s après la puissance au démarrage d'un coup de pédale.

### Zwift Click
- Deux Click à portée (`F4:C4:59:15:E1:E7` et `F4:C4:59:1F:E3:6A`) ; test fait sur le premier.
- Handshake `RideOn` sans chiffrement ; la réponse est `RideOn`.
- Format récent : message `0x23` en continu (~10 Hz), champ 1 = tableau de bits, 0 = appuyé ; bit 12 = +, bit 8 = −. Batterie : message `0x19` toutes les 5 s. Message `0x2a` de statut (non exploité).
- Validé : appuis courts, appuis longs et sens des boutons corrects.
- Durées mesurées : appuis courts de 0,1 à 0,3 s ; des appuis « longs » naturels de 0,7 à 1,1 s tombent dans la zone ignorée (0,5 à 1,2 s) ; résolution de mesure 0,1 s.

## 5. Restant au sprint 0
- Ouvrir un FIT généré (`python -m openride_core.tools.fit_demo`) dans GoldenCheetah et Garmin Connect.
- Lancer `run_mock_session` et la scène Godot (`engine/scenes/main.tscn`) : mouvement de la caméra, HUD, images par seconde.
