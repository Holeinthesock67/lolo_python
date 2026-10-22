# OpenRide Linux - Bilan et Suivi d'Avancement

Date : 22 octobre 2026 (mise à jour en fin de journée)  
Version de référence : SRS v1.1 / Contrats IPC v1 & World v1

---

## 1. Ce qui a été fait

### Spécifications & Architecture
- [x] Spécification SRS v1.1 consolidée ([docs/SRS_v1.1.md](file:///d:/Sauvegarde/Documents/utilisateur/lolo_python/Open_ride_linux/docs/SRS_v1.1.md))
- [x] Contrat IPC core ↔ engine v1 fixé ([docs/contracts/ipc_v1.md](file:///d:/Sauvegarde/Documents/utilisateur/lolo_python/Open_ride_linux/docs/contracts/ipc_v1.md)) avec ses schémas JSON officiels (`state.schema.json` et `cmd.schema.json`)
- [x] Format de monde en couches `.world` v1 documenté ([docs/contracts/world_format_v1.md](file:///d:/Sauvegarde/Documents/utilisateur/lolo_python/Open_ride_linux/docs/contracts/world_format_v1.md))

### Module Core (`openride-core`)
- [x] **Structure & packaging** : package Python 3.11+ avec `pyproject.toml`, installé en mode éditable (`pip install -e .`).
- [x] **Configuration** : module `config.py` avec valeurs par défaut complètes et chargement tolérant de `~/OpenRide/config.toml`.
- [x] **Modèle Physique** (`physics.py`) : intégration par bilan d'énergie cinétique à 50 Hz, stabilité à l'arrêt, anti-recul en côte, plafonnement de sécurité à 80 m/s.
- [x] **Braquets virtuels** (`gearing.py`) : étagement géométrique 24 vitesses (0,50 à 2,25), calcul de la pente effective bornée (-10 % / +16 %).
- [x] **Protocoles BLE purs** (sans dépendance I/O) :
  - `ftms.py` : décodeur Indoor Bike Data (0x2AD2), Machine Features (0x2ACC), Power Range (0x2AD8), Cardio (0x2A37) et encodeur des commandes Control Point (0x11 SIM, 0x05 ERG).
  - `zwift_click.py` : décodage varints protobuf, capture des boutons +/- (type 0x37), classificateur des durées d'appui (court < 500 ms, long ≥ 1 200 ms).
- [x] **Journalisation atomique** (`journal.py`) : écriture continue JSONL à 1 Hz (`flush` à chaque ligne, `fsync` toutes les 5 s), tolérante aux crashs et lignes incomplètes.
- [x] **Export FIT minimal** (`fit_export.py`) : génération de fichiers `.fit` valides via `fit-tool` (`file_id`, `event` avec gestion des pauses, `record`, `lap`, `session`, `activity`).
- [x] **Outil de récupération** : commande CLI `openride-core recover [journal]` pour convertir tout journal orphelin en FIT.
- [x] **Outil de diagnostic BLE** (`openride-ble-diag` / `ble_diag.py`) : sous-commandes `scan`, `trainer` (avec tests de commandes et remise sécurisée à 0 %) et `click`.
- [x] **Simulateur MockDriver** (`mock_driver.py`) : simulation d'un home trainer (SIM & ERG, cadence, fréquence cardiaque, déconnexion/reconnexion).
- [x] **Serveur IPC UDP** (`ipc_server.py`) : gestion des flux UDP (ports 5005 et 5006), diffusion d'état à 30 Hz, acquittement de commandes avec `cmd_id` et contrôle du heartbeat engine.
- [x] **Boucle de session mock** (`run_mock_session.py`) : exécutable autonome faisant tourner la physique 50 Hz + le MockDriver + l'IPC 30 Hz.

- [x] **Pilotes et boucle de séance (sprint 1)** : `ftms_driver.py`, `input_providers.py`, `session.py`, `ble_util.py` ; lancement par `openride-core run`.

### Module Engine Godot (`openride-engine`)
- [x] Projet Godot 4 initialisé dans `engine/project.godot`.
- [x] Chargeur de tracé `RouteData` (`route_data.gd`) : lecture de `route.json` et interpolation de la position 3D et du cap.
- [x] Client IPC UDP (`ipc_client.gd`) : écoute sur le port 5005, heartbeat à 2 Hz et envoi de commandes sur le port 5006.
- [x] Scène 3D principale (`main.tscn` / `main.gd`) : rendu de la polyligne 3D, caméra subjective asservie à la coordonnée `s`, et HUD temps réel (W, km/h, rpm, %, km).
- [x] Parcours synthétique de test généré dans `engine/demo/demo.world/`.

---

## 2. Ce qui a été testé (sur poste de développement)

| Domaine | Test | Statut |
|---|---|:---:|
| **Physique** | Cas de référence 250 W à plat ≈ 10,2 m/s (± 3 %) | **Passé** |
| **Physique** | Stabilité totale à l'arrêt (0 W, 0 km/h) | **Passé** |
| **Physique** | Pas de recul en montée à 0 W (arrêt net, pas de déplacement arrière) | **Passé** |
| **Physique** | Accélération en descente à 0 W par gravité | **Passé** |
| **Physique** | Plafond de vitesse (anti-aberration) | **Passé** |
| **Braquets** | Rapports strictement croissants de k = 1 à 24 | **Passé** |
| **Braquets** | Braquet neutre R_12 ≈ 1,03 | **Passé** |
| **Braquets** | Pente effective bornée [-10 %, +16 %] | **Passé** |
| **FTMS** | Encodage commande SIM 0x11 et ERG 0x05 | **Passé** |
| **FTMS** | Décodage Indoor Bike Data (vitesse, cadence, puissance, FC) | **Passé** |
| **Zwift Click** | Décodage protobuf et classification des appuis (court / long / zone morte) | **Passé** |
| **Journal** | Écriture JSONL et tolérance à la coupure en cours d'écriture (ligne tronquée) | **Passé** |
| **FIT** | Relecture d'un FIT généré par bibliothèque, validation des messages et métriques | **Passé** |
| **FIT Demo** | Déroulement d'une séance simulée de 10 minutes avec pause de 30 s | **Passé** |
| **IPC UDP** | Dialogue complet `hello` -> `hello_ack`, `state` 30 Hz, commandes avec `cmd_id` | **Passé** |
| **MockDriver** | Comportement en mode SIM libre, consigne ERG et déconnexion | **Passé** |

**Total des tests unitaires automatisés (`pytest`)** : **31 passés avec succès**.

---

### Essais sur le PC Linux cible, 22 octobre 2026 (Python 3.14.4, bleak 3.0.2, Godot 4.3, GTX 1060)
- **Environnement** : dépôt cloné par git, branche de travail récupérée avec `git fetch origin <branche>`, 41 tests verts.
- **HomeTrainer (BLE)** : détection, FTMS, SIM, ERG, plage 0–1000 W, FC (0 bpm = pas de mesure). Connexion stable de plusieurs minutes avec le pilote réel.
- **Click (BLE)** : handshake sans chiffrement, format récent `0x23` (bit 12 = +, bit 8 = −), appuis courts et longs reconnus dans le bon sens.
- **FIT** : séance de démo et séance réelle importées sans erreur.
- **Moteur Godot** : fenêtre, HUD et caméra mis à jour par le core ; touches `+` / `−` et flèches envoyées au core.
- **Performance du core** : pas de physique p50 0,2 ms, retard de boucle max 3 à 19 ms, CPU 3 à 4 % : aucun seuil Rust approché (le pic de 7 ms venait du `fsync` du journal, corrigé).

### Défauts trouvés et corrigés pendant les essais
| Défaut | Cause | Correction |
| --- | --- | --- |
| `org.bluez.Error.InProgress` | Trainer et Click scannaient en même temps (BlueZ n'accepte qu'une opération à la fois) | Verrou commun, trainer prioritaire |
| Trainer « introuvable » | Nom cherché « HomeTrainer », annoncé « HomeTrainer 0000 » | Nom par défaut « HomeTrainer » |
| Pas de physique p99 à 7 ms | `fsync` du journal à chaque ligne | `fsync` toutes les 5 s (flush à chaque ligne conservé) |
| Lag perçu sur les commandes de braquet | Pente envoyée limitée à 2 points/s, même pour un changement de braquet | Le braquet saute à la cible ; la limite ne vaut que pour le relief |
| Export FIT en échec | Vitesse moyenne hors plage avec un chrono aberrant | Vitesse moyenne bornée par la vitesse max |
| HUD vide dans Godot | `class_name` inconnus quand le projet n'est pas importé par l'éditeur | Chargement explicite des scripts |
| Moteur « perdu » toutes les 4 s | Heartbeat lié au rendu | Heartbeat dans un fil séparé |
| Séance en pause sans reprise | Aucun bouton de reprise à l'écran | `--autostart` reprend seul après `engine_lost` / `trainer_lost` |
| Click intermittent | Recherche par fenêtres de 6 s puis attente jusqu'à 10 s ; le Click ne s'annonce qu'après un appui | Recherche continue (5 s, pause 0,5 à 2 s) |

## 3. Ce qui reste à tester

### A. Sur le PC Linux cible avec le matériel réel (Home Trainer & Click)

**Mise à jour du 22 octobre 2026 :** scan, diagnostic du HomeTrainer (lecture, cardio, commandes pente et puissance) et diagnostic du Zwift Click (appuis courts et longs, sens des boutons) sont validés. Détails dans `docs/spikes.md` §4. Restent : ouverture d'un FIT dans GoldenCheetah / Garmin Connect et l'affichage Godot avec le mock.

Ces tests doivent être exécutés avec le PC portable sous Ubuntu (Bluetooth activé, Zwift déconnecté du smartphone et du PC) :

1. **Scan BLE (`openride-ble-diag scan`)**
   - [ ] Vérifier la visibilité du HomeTrainer (nom et adresse MAC).
   - [ ] Vérifier la visibilité du Zwift Click (après appui sur un bouton, LED bleue clignotante).
2. **Diagnostic HomeTrainer (`openride-ble-diag trainer`)**
   - [ ] Confirmer les caractéristiques exposées (FTMS 0x1826, 0x2ACC, 0x2AD2).
   - [ ] Vérifier si le **pont cardio** du HomeTrainer expose la caractéristique 0x2A37 (service 0x180D).
   - [ ] Mesurer la fréquence réelle d'envoi d'Indoor Bike Data en pédalant (attendue entre 1 et 4 Hz).
   - [ ] Tester la prise de contrôle FTMS (`request_control` 0x00 puis `start_resume` 0x07).
   - [ ] Tester la commande SIM 0x11 (résistance ressentie sur une pente de 4 %) et retour à 0 %.
   - [ ] Tester la consigne ERG 0x05 (puissance cible à 150 W).
   - [ ] Vérifier la génération du rapport JSON sous `spike_reports/`.
3. **Diagnostic Zwift Click (`openride-ble-diag click`)**
   - [ ] Tester la connexion BLE et le handshake `b"RideOn"` sur la caractéristique SYNC_RX.
   - [ ] Tester les appuis courts (< 0,5 s) sur `+` et `-` et vérifier l'affichage des logs `PLUS_SHORT` / `MINUS_SHORT`.
   - [ ] Tester les appuis longs (≥ 1,2 s) et vérifier l'affichage des logs `PLUS_LONG` / `MINUS_LONG`.
   - [ ] Vérifier la bonne réception du niveau de batterie du Click.
4. **Validation des fichiers FIT exportés**
   - [ ] Transférer un fichier `.fit` généré (par `fit_demo` ou `recover`) et l'ouvrir dans **GoldenCheetah**.
   - [ ] Importer le fichier `.fit` dans **Garmin Connect** et vérifier l'absence d'erreur de parsing.

### B. Côté Engine (Godot 4)
- [ ] Lancer `run_mock_session.py` dans un terminal et exécuter la scène Godot `engine/scenes/main.tscn`.
- [ ] Vérifier visuellement le déplacement fluide de la caméra le long de la polyligne 3D.
- [ ] Vérifier l'actualisation dynamique du HUD (puissance, vitesse, cadence, distance).
- [ ] Valider le taux de rafraîchissement (30+ FPS) sur le GPU du PC Linux portable.

---

## 4. Ce qui reste à faire (Prochaines étapes de développement)

### Sprint 1 : Intégration Core finale (en grande partie fait, 22 octobre)
- [x] `FtmsDriver` réel (`ftms_driver.py`) : reconnexion à délai croissant, prise de contrôle, consigne SIM bornée, lissage temporel de la puissance, FC 0 → null, résistance relâchée à l'arrêt.
- [x] `ZwiftClickProvider` + clavier (`input_providers.py`) : le Click est cherché en continu, le clavier reste actif en parallèle.
- [x] Boucle principale officielle (`session.py`, `openride-core run`) : physique 50 Hz, IPC 30 Hz, journal 1 Hz, FIT en fin de séance, bascule réel/simulé par `--trainer` / `--input` ou `[drivers]` de `config.toml`.
- [x] Séance courte sur le HomeTrainer réel avec changements de braquet (essais du 22 octobre, voir §2).
- [ ] Séance réelle de 10 minutes ou plus avec braquets perceptibles, puis relecture des mesures de performance (`Perf` dans le log).
- [ ] Réévaluer le seuil d'appui long du Click (environ 0,9 s).
- [ ] Mesurer le délai entre un appui et l'écriture de la commande au HomeTrainer (lag ressenti au sprint 0).
- [x] Appuis longs en SIM : braquet ± 3 (`long_press_gears`), bips distincts par type d'appui dans l'engine (validé à l'oreille sur le vélo le 22 octobre, appuis courts et longs).
- [x] `scripts/openride-dev.sh` : lance core et Godot depuis un seul terminal (remplace les deux terminaux pour les essais).
- [ ] **Click : déconnexions spontanées** (22 octobre : environ 2 en 3 min d'usage, reconnexion en ~4 s, appuis perdus pendant ce délai). À instruire : cause de la coupure (veille, paramètres de connexion, messages d'entretien attendus par le Click), temps de reconnexion à réduire, réveil par un appui.
- [x] Click resté « connecté » côté BlueZ (donc invisible au scan) : repli sur les appareils connus de BlueZ, vérifié en conditions réelles.
- [ ] Rendre le braquet de départ réglable dans `config.toml` (aujourd'hui `--gear N` en ligne de commande).
- [ ] Remplacer le parcours factice par la lecture d'un vrai `.world` (dépend du sprint 2).

### Lanceur et menus (à planifier, après le sprint 2)
- [ ] Lanceur unique `openride` (commande et icône de bureau) : démarre le core selon `config.toml`, attend sa réponse, lance Godot en plein écran, arrête tout à la fermeture de la fenêtre (FIT écrit, résistance relâchée).
- [ ] Supervision : relance du core ou de l'engine en cas de plantage, sans perdre la séance (le journal existe déjà).
- [ ] Menu à l'écran piloté au Click et au clavier : choix du parcours, démarrage, pause, reprise, fin de séance (remplace `--autostart`).
- [ ] Écran d'état des appareils (trainer, Click, batterie du Click) et message d'aide quand le Click dort.

### Sprint 2 : Compilateur de parcours minimal (`openride-compiler`)
- [ ] Créer le package `openride-compiler` (CLI `openride-compiler build`).
- [ ] Parseur GPX avec ré-échantillonnage tous les 10 m.
- [ ] Lissage d'altitude par filtre de Savitzky-Golay (fenêtre 11 points, ordre 2).
- [ ] Intégration du MNT Copernicus GLO-30 / IGN RGE ALTI pour le relief du terrain.
- [ ] Découpage du terrain en tuiles binaires `float32` (`terrain/near/` à 10 m et `terrain/far/` à 50 m) avec adoucissement aux abords de la route.

### Sprint 3 : Moteur de rendu 3D complet (`openride-engine`)
- [ ] Remplacement de la polyligne par un ruban de route texturé (mesh 3D).
- [ ] Génération des maillages de terrain par tronçons de 1 km à partir des tuiles `.f32`.
- [ ] Shader triplanaire (herbe / roche selon la pente, neige au-dessus de 2 200 m).
- [ ] Ciel physique, soleil orienté, instanciation des arbres (`MultiMeshInstance3D`).
- [ ] HUD final avec profil altimétrique et position du coureur.
- [ ] Menus de sélection de parcours et d'entraînement.

### Sprint 4 & suivants : Entraînements ERG (`.zwo`), Couches OSM, Thèmes
- [ ] Lecteur XML `.zwo`, gestion des blocs (Warmup, SteadyState, IntervalsT, FreeRide).
- [ ] Couches OpenStreetMap (bâtiments extrudés 3D, forêts).
- [ ] Système de thèmes (`~/OpenRide/Themes/<nom>/`) avec packs de textures interchangeables.
