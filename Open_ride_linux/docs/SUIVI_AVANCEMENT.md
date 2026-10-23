# OpenRide Linux – Bilan et suivi d'avancement

Mise à jour : 23 octobre 2026
Références : SRS v1.1, Contrat IPC v1, Format `.world` v1, audit du 23 octobre (`docs/AUDIT_2026-10-23.md`)

---

## 1. Ce qui a été fait

### Spécifications et architecture
- [x] Spécification [SRS v1.1](SRS_v1.1.md).
- [x] [Contrat IPC v1](contracts/ipc_v1.md) core ↔ engine, avec les schémas JSON `state` et `cmd`.
- [x] [Format `.world` v1](contracts/world_format_v1.md), en couches.
- [x] [Audit du 23 octobre](AUDIT_2026-10-23.md) et [cahiers des charges des lots sous-traitables](lots/00_INDEX.md).

### Module core (`openride-core`, Python)
- [x] **Paquet :** Python 3.11 minimum, essais réels en 3.14 ; installation en mode éditable.
- [x] **Configuration** (`config.py`) : valeurs par défaut complètes, lecture tolérante de `~/OpenRide/config.toml`, section `[drivers]` (trainer réel ou simulé, Click ou clavier).
- [x] **Physique** (`physics.py`) : bilan d'énergie cinétique à 50 Hz, stable à l'arrêt, sans recul en côte, vitesse plafonnée.
- [x] **Braquets** (`gearing.py`) : 24 vitesses de 0,50 à 2,25, pente effective bornée de −10 à +16 %, saut de plusieurs vitesses (appui long).
- [x] **Protocoles BLE purs :**
  - `ftms.py` : Indoor Bike Data, capacités, plage de puissance, cardio, commandes SIM et ERG ;
  - `zwift_click.py` : formats `0x37` (ancien Click) et `0x23` (Click récent), appui court sous 0,5 s, appui long à partir de 0,9 s.
- [x] **Pilotes réels :**
  - `ftms_driver.py` : Victory, avec reconnexion à délai croissant, prise de contrôle, lissage de la puissance, FC à 0 traitée comme absente, résistance relâchée à l'arrêt ;
  - `input_providers.py` : Click avec recherche continue, clavier en parallèle ;
  - `ble_util.py` : une seule opération Bluetooth à la fois, repli sur les appareils connus de BlueZ.
- [x] **Boucle de séance** (`session.py`, `openride-core run`) : physique à 50 Hz, IPC à 30 Hz, journal à 1 Hz, FIT en fin de séance, pente anticipée et lissée, mesures de performance toutes les 60 s.
- [x] **Journal** (`journal.py`) : JSONL à 1 Hz, `flush` à chaque ligne, `fsync` toutes les 5 s, tolérant aux plantages.
- [x] **Export FIT** (`fit_export.py`) et récupération (`openride-core recover`).
- [x] **Diagnostic BLE** (`openride-ble-diag`) : `scan`, `trainer`, `click`.
- [x] **Simulateur** (`mock_driver.py`) : SIM, ERG, cadence, cardio, déconnexion.

### Module engine (`openride-engine`, Godot 4.3)
- [x] Client IPC (`ipc_client.gd`) : `hello` répété jusqu'à la réponse, heartbeat dans un fil séparé, commandes vers le core.
- [x] Scène de démonstration (`main.gd`) : polyligne du parcours, caméra subjective, HUD (puissance, vitesse, braquet, cadence, pente réelle et envoyée, distance, état de la séance).
- [x] Touches `+` / `−` / flèches (appuis courts), `Page haut` / `Page bas` (appuis longs) ; un bip distinct par type d'appui.
- [x] Scripts chargés par `preload` : le projet se lance sans passer par l'éditeur.

### Outils
- [x] `scripts/openride-dev.sh` : lance le core et Godot depuis un seul terminal, et arrête proprement le core à la fermeture de la fenêtre.

---

## 2. Ce qui a été testé

### Tests automatiques
**42 tests `pytest` passent** (physique, braquets, FTMS, Click, journal, FIT, IPC, pilotes avec faux client Bluetooth, boucle de séance). Couverture globale : 64 % ; modules de calcul de 89 à 100 % (détail dans l'audit, §4).

### Essais sur le PC cible, 22 octobre 2026
PC de bureau MSI sous Ubuntu, GTX 1060, Python 3.14.4, bleak 3.0.2, Godot 4.3.

- **Victory (BLE) :** détection, FTMS, SIM, ERG, plage de 0 à 1 000 W, cardio (0 bpm = pas de mesure). Connexion stable pendant plusieurs minutes avec le pilote réel.
- **Click (BLE) :** handshake sans chiffrement, format `0x23` (bit 12 = +, bit 8 = −), appuis courts et longs dans le bon sens, bips validés à l'oreille.
- **FIT :** séance de démonstration et séance réelle importées sans erreur (contrôle fait par le propriétaire le 22 octobre).
- **Godot :** HUD et caméra mis à jour par le core, touches transmises au core.
- **Performance du core :** pas de physique p50 0,2 ms, retard de boucle max 3 à 19 ms, CPU 3 à 4 %. Aucun seuil Rust approché.

### Défauts trouvés et corrigés pendant les essais

| Défaut | Cause | Correction |
| --- | --- | --- |
| `org.bluez.Error.InProgress` | Trainer et Click scannaient en même temps (BlueZ n'accepte qu'une opération à la fois) | Verrou commun, trainer prioritaire |
| Trainer « introuvable » | Nom cherché « JetBlack Victory », annoncé « Victory 9908 » | Nom par défaut « Victory » |
| Pas de physique p99 à 7 ms | `fsync` du journal à chaque ligne | `fsync` toutes les 5 s (`flush` à chaque ligne conservé) |
| Lag perçu sur les changements de braquet | Pente envoyée limitée à 2 points/s, même pour un changement de braquet | Le braquet saute à la cible ; la limite ne vaut que pour le relief |
| Export FIT en échec | Vitesse moyenne hors plage avec un chrono aberrant | Vitesse moyenne bornée par la vitesse max |
| HUD vide dans Godot | `class_name` inconnus quand le projet n'est pas importé par l'éditeur | Chargement explicite des scripts |
| Moteur « perdu » toutes les 4 s | Heartbeat lié au rendu | Heartbeat dans un fil séparé |
| Séance en pause sans reprise | Aucun bouton de reprise à l'écran | `--autostart` reprend seul après `engine_lost` / `trainer_lost` |
| Click intermittent | Recherche par fenêtres de 6 s puis attente jusqu'à 10 s ; le Click ne s'annonce qu'après un appui | Recherche continue (5 s, pause de 0,5 à 2 s) |
| Click invisible au scan | Resté « connecté » côté BlueZ après une coupure | Repli sur les appareils connus de BlueZ |

### Défauts relevés par l'audit du 23 octobre (non corrigés, confiés au lot C)
- Commandes ignorées après un redémarrage de Godot.
- Panne d'écriture du journal qui arrête la boucle.
- Résumé de fin de séance non conforme au schéma.

Détail et autres écarts dans l'[audit](AUDIT_2026-10-23.md), §3.

---

## 3. Ce qui reste à tester (matériel, en interne)

- [ ] Séance réelle de 10 minutes ou plus avec braquets perceptibles, puis relecture des mesures `Perf` du log.
- [ ] Délai entre un appui et l'écriture de la commande au Victory.
- [ ] Click : cause des déconnexions spontanées (environ 2 en 3 minutes le 22 octobre, reconnexion en 4 s environ).
- [ ] Images par seconde de Godot, à relever quand le décor sera chargé (lot E1).

---

## 4. Ce qui reste à faire

Les travaux confiables à une autre IA sont décrits dans [`docs/lots/`](lots/00_INDEX.md).

### Sprint 1 : fin
- [ ] Séance de 10 minutes (§3).
- [ ] Braquet de départ réglable dans `config.toml` (aujourd'hui `--gear N` en ligne de commande).
- [ ] Corrections de conformité du core (lot C).

### Lecture des parcours (lot A)
- [ ] Lecteur `.world` commun au core et à Godot, interpolation de Catmull-Rom, vecteurs de test partagés, parcours en boucle.

### Sprint 2 : compilateur (lots B1 et B2)
- [ ] GPX vers couche route (ré-échantillonnage à 10 m, lissage de Savitzky-Golay, pente, cap, projection UTM).
- [ ] Couche terrain (MNT Copernicus GLO-30, tuiles proches et lointaines, cache sans réseau à la relance).

### Sprint 3 : rendu 3D (lots D, E1, puis E2 et E3 à rédiger)
- [ ] Godot conforme au contrat (renvoi des commandes, extrapolation, core injoignable).
- [ ] Ruban de route et terrain par tronçons.
- [ ] Shader triplanaire et thèmes, arbres, HUD final avec profil d'altitude.

### Lanceur et menus (lot G, à rédiger)
- [ ] Lanceur unique `openride` (commande et icône de bureau), qui arrête tout à la fermeture de la fenêtre.
- [ ] Supervision : relance du core ou de l'engine sans perdre la séance.
- [ ] Menu piloté au Click et au clavier (parcours, démarrage, pause, fin), à la place de `--autostart`. Le contrat IPC devra gagner des messages pour lister parcours et entraînements.
- [ ] Écran d'état des appareils (trainer, Click, batterie du Click).

### Sprint 4 et suivants
- [ ] Entraînements ERG `.zwo` (lot F).
- [ ] Couches OpenStreetMap (bâtiments, forêts).
- [ ] Thèmes avec packs de textures.
