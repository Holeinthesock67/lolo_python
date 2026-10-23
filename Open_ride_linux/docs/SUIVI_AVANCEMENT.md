# OpenRide Linux – Bilan et suivi d'avancement

Mise à jour : 23 octobre 2026 (fusions A2, B2, F et H1 à H8 ; audit du soir et cahiers I1 à I6)
Références : SRS v1.1, Contrat IPC v1, Format `.world` v1, audit du 23 octobre (`docs/AUDIT_2026-10-23.md`)

---

## 1. Ce qui a été fait

### Spécifications et architecture
- [x] Spécification [SRS v1.1](SRS_v1.1.md).
- [x] [Contrat IPC v1](contracts/ipc_v1.md) core ↔ engine, avec les schémas JSON `state` et `cmd`.
- [x] [Format `.world` v1](contracts/world_format_v1.md), en couches.
- [x] [Audit du 23 octobre](AUDIT_2026-10-23.md) et [cahiers des charges des lots sous-traitables](lots/00_INDEX.md).
- [x] Schémas JSON de tous les messages IPC (`docs/contracts/ipc/`) et du `.world` (`docs/contracts/world/`, avec vecteurs de test de la route).

### Module core (`openride-core`, Python)
- [x] **Paquet :** Python 3.11 minimum, essais réels en 3.14 ; installation en mode éditable.
- [x] **Configuration** (`config.py`) : valeurs par défaut complètes, lecture tolérante de `~/OpenRide/config.toml`, section `[drivers]` (trainer réel ou simulé, Click ou clavier, `mock_replay`).
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
- [x] **Conformité au contrat IPC** (lot C, 23 octobre) : commandes acceptées après un redémarrage de Godot, panne d'écriture du journal sans arrêt de la boucle (`recorder.py` : séance en mémoire, nouveau journal à la reprise), résumé de fin conforme, refus du contrôle FTMS remonté (`ERROR`), consigne ERG bornée, `hello_ack` et coefficient de difficulté tirés de la configuration.
- [x] **Lecture des parcours** (lot A, 23 octobre) : `route.py` charge et valide un `.world`, interpole la route (Catmull-Rom centripète) et gère les boucles ; la séance charge le parcours demandé par son nom ; parcours de démonstration unique (`demo_world.py`).
- [x] **Entraînements ERG** (lot F, 23 octobre) : `workout.py` lit les `.zwo` de `~/OpenRide/Workouts/` (intervalles dépliés, fichiers invalides listés avec leur erreur) ; la séance envoie la cible ERG lissée sur 2 s, biais ± 2 % et saut de bloc au Click, pause ERG à pente 0 %, roue libre en SIM avec les braquets, objet `erg` des trames `state` et `mode` / `block` dans le journal.
- [x] **Simulateur** (`mock_driver.py`, `replay.py`) : SIM, ERG, cadence, cardio, déconnexion, rejeu d'une séance enregistrée (`.jsonl` ou `.fit`, lot H3).

### Module engine (`openride-engine`, Godot 4.3)
- [x] Client IPC (`ipc_client.gd`) : `hello` répété jusqu'à la réponse, heartbeat dans un fil séparé, commandes vers le core.
- [x] Scène de démonstration (`main.gd`) : polyligne du parcours, caméra subjective, HUD (puissance, vitesse, braquet, cadence, pente réelle et envoyée, distance, état de la séance).
- [x] Touches `+` / `−` / flèches (appuis courts), `Page haut` / `Page bas` (appuis longs) ; un bip distinct par type d'appui.
- [x] Scripts chargés par `preload` : le projet se lance sans passer par l'éditeur.
- [x] `route_data.gd` : même lecture et même interpolation que le core, vérifiées par 42 vecteurs de test partagés (`engine/tests/test_route_vectors.gd`).
- [x] `theme_loader.gd` : lecture, validation et fusion des thèmes visuels avec repli sur `res://themes/default/theme.json` et chargement des textures utilisateur (`engine/tests/test_theme_loader.gd`, lot I5).

### Outils
- [x] `scripts/openride-dev.sh` : lance le core et Godot depuis un seul terminal, et arrête proprement le core à la fermeture de la fenêtre.
- [x] Intégration continue GitHub Actions (`.github/workflows/openride.yml`, lot H1) : suites du core, du compilateur et des vecteurs de route en Python 3.11 et 3.14 (`constraints.txt`), et tests de l'engine Godot 4.3 sans écran.
- [x] Analyseur de journal de séance (`python -m openride_core.tools.log_report`, lot H6) : résumé texte et `--json` de `~/run_victory.log` (trainer, Click, pauses, seuils Rust SRS §14.1).
- [x] Schéma et validateur de thèmes (`docs/contracts/world/theme.schema.json`, `engine/themes/default/theme.json`, `openride-compiler theme-check`, lot H7).
- [x] Outils et bibliothèque d'entraînements ERG (`python -m openride_core.tools.workouts list|check|install` et 5 fichiers `.zwo` de référence dans `core/workouts/`, lot H8).
- [x] Couches OpenStreetMap `buildings` et `vegetation` du compilateur (`osm.py`, `osm_layers.py`, cache brut `~/.cache/openride/osm/`, schémas `buildings.schema.json` et `vegetation.schema.json`, lot I3).
- [x] Couches OpenStreetMap `poi` et `water` du compilateur (points d'intérêt sonores/visuels, cours d'eau découpés par tronçon de 1 km et plans d'eau avec îles, schémas `poi.schema.json` et `water.schema.json`, lot I4).

---

## 2. Ce qui a été testé

### Tests automatiques
**153 tests pytest passent dans le core et 115 dans le compilateur** (physique, braquets, FTMS, Click, recherche Bluetooth et repli BlueZ sans matériel (lot H2), rejeu JSONL/FIT dans le simulateur (lot H3), endurance simulée de 3 h (lot H4), validation FIT indépendante par garmin-fit-sdk (lot H5), analyseur de journal log_report (lot H6), schéma et validateur de thèmes 	heme-check (lot H7), outils et bibliothèque d'entraînements .zwo (lot H8), cohérence documentation/code (lot I1), catalogue des parcours list et uild-all (lot I2), journal, FIT, IPC, pilotes avec faux client Bluetooth, boucle de séance, tests de contrat, lecture des parcours). Couverture globale du core : 76 % (le_util.py à 100 %). Côté Godot : 42 vecteurs de route et 8 scénarios IPC vérifiés sans écran (engine/tests/run_engine_tests.sh).

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

### Défauts relevés par l'audit du 23 octobre
Corrigés le jour même par les lots C, A, D et H1 à H4 :
- commandes ignorées après un redémarrage de Godot ;
- panne d'écriture du journal qui arrêtait la boucle ;
- résumé de fin non conforme ;
- core et Godot sur deux parcours différents ;
- conformité de Godot au contrat IPC et scénarios sans écran (lot D) ;
- intégration continue GitHub Actions et fichier `constraints.txt` (F6, lot H1) ;
- tests unitaires de `ble_util` sans matériel (F8, lot H2) ;
- endurance simulée de 3 h et taille de la trame `state` en ERG (F7, lot H4).

Un défaut de contrat a aussi été trouvé et clarifié : `v` désigne la vitesse dans la trame `state`.

Reste ouvert : la stabilité du Click (interne). Détail dans l'[audit](AUDIT_2026-10-23.md), §3 et §7.

---

## 3. Ce qui reste à tester (matériel, en interne)

- [ ] Séance réelle de 10 minutes ou plus avec braquets perceptibles, puis relecture des mesures `Perf` du log.
- [ ] Délai entre un appui et l'écriture de la commande au Victory.
- [ ] Click : cause des déconnexions spontanées (environ 2 en 3 minutes le 22 octobre, reconnexion en 4 s environ).
- [ ] Images par seconde de Godot, à relever quand le décor sera chargé (lot E1).
- [ ] ERG (lot F) : un `.zwo` standard exécuté en entier sur le Victory, cibles tenues (critère 11 du lot F).

---

## 4. Ce qui reste à faire

Les travaux confiables à une autre IA sont décrits dans [`docs/lots/`](lots/00_INDEX.md). Les lots H1 à H8 ont tous été livrés et fusionnés le 23 octobre. Les lots I1 à I6 (même jour, au soir) sont prêts à confier : tests de cohérence documentation/code, catalogue de parcours, couches OSM (bâtiments, végétation, points d'intérêt, eau) et logique Godot testée sans écran (thèmes, ERG).

### Sprint 1 : fin
- [ ] Séance de 10 minutes (§3).
- [x] Braquet de départ réglable : `[gearing] start_gear` dans `config.toml` (vérifié le 23 octobre), `--gear N` le remplace en ligne de commande.
- [x] Corrections de conformité du core (lot C).

### Lecture des parcours (lot A)
- [x] Lecteur `.world` commun au core et à Godot, interpolation de Catmull-Rom, vecteurs de test partagés, parcours en boucle.

### Sprint 2 : compilateur (lots B1 et B2)
- [x] GPX vers couche route (ré-échantillonnage à 10 m, lissage de Savitzky-Golay, pente, cap, projection UTM).
- [x] Couche terrain (MNT Copernicus GLO-30, tuiles proches et lointaines, cache sans réseau à la relance), lot B2. Essai réel : trace de 30 km dans l'Oisans, 4 tuiles (165 Mo) téléchargées en 17 s, recompilation hors ligne en 6 s.
- [ ] Comparer la pente maximale d'une vraie trace de col avec Garmin Connect (à ± 1 point) et relever les écarts GPX / MNT affichés par `build`, pour ajuster le seuil d'altitude aberrante.

### Sprint 3 : rendu 3D (lots D, E1, puis E2 et E3 à rédiger)
- [x] Godot conforme au contrat (renvoi des commandes, extrapolation, core injoignable), lot D.
- [ ] Ruban de route et terrain par tronçons (lot E1 fait, PR #7 : attend l'essai sur la GTX 1060).
- [ ] Shader triplanaire et thèmes (E2, après le chargeur de thèmes GDScript du lot I5), arbres, HUD final avec profil d'altitude (E3).

### Lanceur et menus (lot G, à rédiger)
- [ ] Lanceur unique `openride` (commande et icône de bureau), qui arrête tout à la fermeture de la fenêtre.
- [ ] Supervision : relance du core ou de l'engine sans perdre la séance.
- [ ] Menu piloté au Click et au clavier (parcours, démarrage, pause, fin), à la place de `--autostart`. Le contrat IPC devra gagner des messages pour lister parcours et entraînements.
- [ ] Écran d'état des appareils (trainer, Click, batterie du Click).

### Sprint 4 et suivants
- [x] Entraînements ERG `.zwo` (lot F, fusionné le 23 octobre ; essai sur le Victory à faire).
- [ ] Couches OpenStreetMap : compilateur (lots I3 bâtiments et végétation, I4 points d'intérêt et eau), puis rendu dans l'engine (à rédiger).
- [ ] Thèmes avec packs de textures.
