# OpenRide Linux – Bilan et suivi d'avancement

Mise à jour : 24 octobre 2026 (cahiers de la série N ; fusions E1, K1 à K5, K8, braquets réactifs et deux boîtiers du Click ; libération du trainer validée sur le HomeTrainer) ; précédente : 24 octobre au matin (vérification et correctifs R1, R2, S1, PR #44)
Références : SRS v1.1, Contrat IPC v1, Format `.world` v1, audit du 23 octobre (`docs/AUDIT_2026-10-23.md`)
Vérification du 24 octobre (`docs/VERIFICATION_2026-10-24.md`) : constats R1, R2 et S1 corrigés.
Revue de code du 24 octobre (`docs/REVUE_CODE_2026-10-24.md`) : diagnostic du Click à deux boîtiers, message du lanceur, pente NaN et lint corrigés.

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
- [x] **Configuration** (`config.py`) : valeurs par défaut complètes, clés absentes tolérées, types et bornes contrôlés avec un message qui cite la section et la clé (lot J3), clé inconnue signalée, section `[drivers]` (trainer réel ou simulé, Click ou clavier, `mock_replay`).
- [x] **Physique** (`physics.py`) : bilan d'énergie cinétique à 50 Hz, stable à l'arrêt, sans recul en côte, vitesse plafonnée.
- [x] **Braquets** (`gearing.py`) : 24 vitesses de 0,50 à 2,25, pente effective bornée de −10 à +16 %, saut de plusieurs vitesses (appui long).
- [x] **Protocoles BLE purs :**
  - `ftms.py` : Indoor Bike Data, capacités, plage de puissance, cardio, commandes SIM et ERG ;
  - `zwift_click.py` : formats `0x37` (ancien Click) et `0x23` (Click récent), appui court sous 0,5 s, appui long à partir de 0,9 s ; Click V2 : dix boutons relevés (`KEYPAD_BITS`), B du boîtier droit lu comme « − » car le boîtier gauche est bridé sans déblocage Zwift (PR #87, 24 octobre).
- [x] **Pilotes réels :**
  - `ftms_driver.py` : HomeTrainer, avec reconnexion à délai croissant, prise de contrôle, lissage de la puissance, FC à 0 traitée comme absente, à l'arrêt : pente 0 %, Reset (contrôle FTMS rendu) et déconnexion, y compris sur SIGHUP ; dépannage `openride-core release-trainer` ;
  - `input_providers.py` : Click avec recherche continue, clavier en parallèle ;
  - `ble_util.py` : une seule opération Bluetooth à la fois, repli sur les appareils connus de BlueZ.
- [x] **Boucle de séance** (`session.py`, `openride-core run`) : physique à 50 Hz, IPC à 30 Hz, journal à 1 Hz, FIT en fin de séance, pente anticipée et lissée, mesures de performance toutes les 60 s.
- [x] **Journal** (`journal.py`) : JSONL à 1 Hz, `flush` à chaque ligne, `fsync` toutes les 5 s, tolérant aux plantages.
- [x] **Export FIT** (`fit_export.py`) et récupération (`openride-core recover`).
- [x] **Diagnostic BLE** (`openride-ble-diag`) : `scan`, `trainer`, `click`.
- [x] **Inventaire des appareils** (`openride-core devices`, `tools/devices.py`, lot M3) : recherche sans connexion, rôles (trainer FTMS, boîtiers du Click, ceinture ou montre cardio), appareils connectés à BlueZ mais muets avec le conseil `release-trainer`, bloc `[drivers]` proposé et différences avec `config.toml`, sortie `--json`, essai sans matériel avec `--sim-scenario`. Appairage `devices --save` (lot N12, `pairing.py`) : identification du « + » par un appui, écriture dans la configuration locale avec commentaires gardés, copie `.bak` et validation, nouvelle clé `click_minus_address`, testé par `core/tests/test_pairing.py`.
- [x] **Robustesse IPC** (lot J2, 23 octobre) : un message JSON non conforme (liste, `cmd_id` non entier, `args` invalide) est ignoré et compté au lieu d'arrêter la boucle ; une erreur dans une commande est journalisée sans arrêter la séance.
- [x] **Conformité au contrat IPC** (lot C, 23 octobre) : commandes acceptées après un redémarrage de Godot, panne d'écriture du journal sans arrêt de la boucle (`recorder.py` : séance en mémoire, nouveau journal à la reprise), résumé de fin conforme, refus du contrôle FTMS remonté (`ERROR`), consigne ERG bornée, `hello_ack` et coefficient de difficulté tirés de la configuration.
- [x] **Lecture des parcours** (lot A, 23 octobre) : `route.py` charge et valide un `.world`, interpole la route (Catmull-Rom centripète) et gère les boucles ; la séance charge le parcours demandé par son nom ; parcours de démonstration unique (`demo_world.py`).
- [x] **Entraînements ERG** (lot F, 23 octobre) : `workout.py` lit les `.zwo` de `~/OpenRide/Workouts/` (intervalles dépliés, fichiers invalides listés avec leur erreur) ; la séance envoie la cible ERG lissée sur 2 s, biais ± 2 % et saut de bloc au Click, pause ERG à pente 0 %, roue libre en SIM avec les braquets, objet `erg` des trames `state` et `mode` / `block` dans le journal.
- [x] **Simulateur** (`mock_driver.py`, `replay.py`) : SIM, ERG, cadence, cardio, déconnexion, rejeu d'une séance enregistrée (`.jsonl` ou `.fit`, lot H3).
- [x] **Bluetooth simulé** (`ble_sim.py`, `sim_scenarios.py`, 24 octobre) : HomeTrainer, paire de Zwift Click et ceinture cardio simulés derrière les vrais pilotes (`--trainer sim --input sim --hr sim`), 7 scénarios de pannes tirés des essais. A trouvé un défaut de reprise de contrôle FTMS (refus 0x05 ou état 0xFF reçu pendant une écriture : la reprise n'avait jamais lieu), corrigé dans `ftms_driver.py`.
- [x] **Erreur ATT du Control Point** (lot M1, `ftms_driver.py`) : une écriture qui échoue avec une erreur ATT (0x80 vue le 24 octobre) est renvoyée jusqu'à 2 fois, 0,25 s plus tard, avec la consigne la plus récente (0xFE : après la réponse de la procédure en cours ; 0xFD : abonnement refait) ; la reconnexion ne reste que pour une liaison perdue ou trois erreurs de suite. Compteur `att_retries`, lignes « renvoi 1/2 » au journal.
- [x] **Ceinture cardio** (`hr_monitor.py`) : service Heart Rate standard, facultative (`hr = "ble"`), prioritaire sur la fréquence du trainer. Lot M2 : mesure décodée en entier (`ftms.parse_hr_measurement_full` : contact, énergie, intervalles RR), mesures ignorées quand le contact est absent (une ligne au journal par changement), 30 derniers RR gardés, liste des appareils 0x180D trouvés et choix explicite (`hr_name`, sinon meilleur RSSI hors montres Garmin), adresse retenue à recopier dans `hr_address`, batterie lue à la connexion (avertissement sous 15 %). À essayer avec une vraie ceinture.

### Module engine (`openride-engine`, Godot 4.3)
- [x] Client IPC (`ipc_client.gd`) : `hello` répété jusqu'à la réponse, heartbeat dans un fil séparé, commandes vers le core.
- [x] Scène de démonstration (`main.gd`) : polyligne du parcours, caméra subjective, HUD (puissance, vitesse, braquet, cadence, fréquence cardiaque, pente réelle et envoyée, distance, état de la séance ; en ERG : cible envoyée au trainer avec le biais, bloc, temps restant, et la ligne du braquet rappelle que ± règle l'intensité ; textes calculés par `hud_view_model.session_lines`, 24 octobre).
- [x] Touches `+` / `−` / flèches (appuis courts), `Page haut` / `Page bas` (appuis longs) ; un bip distinct par type d'appui.
- [x] Scripts chargés par `preload` : le projet se lance sans passer par l'éditeur.
- [x] `route_data.gd` : même lecture et même interpolation que le core, vérifiées par 42 vecteurs de test partagés (`engine/tests/unit/test_route_vectors.gd`).
- [x] `theme_loader.gd` : lecture, validation et fusion des thèmes visuels avec repli sur `res://themes/default/theme.json` et chargement des textures utilisateur (`engine/tests/unit/test_theme_loader.gd`, lot I5).
- [x] `erg_view_model.gd` : logique d'affichage du bandeau ERG, déclenchement unique du bip à T − 3 s et géométrie de l'histogramme `profile_bars`, testés sans écran face à `fake_core.py --erg-workout` (`engine/tests/test_erg_view_model.gd`, lot I6).
- [x] Tests unitaires GDScript lancés par découverte : chaque `engine/tests/unit/test_*.gd` est lancé par `run_engine_tests.sh`, avec résumé final et `UNIT=nom` pour un seul test (lot K1).
- [x] `menu_model.gd` : navigation des menus au Click et au clavier (accueil, parcours, entraînements, prêt, confirmation, pause), machine à états sans affichage qui renvoie les actions à exécuter, testée sans écran (`engine/tests/unit/test_menu_model.gd`, lot K5) ; l'affichage et les listes du contrat v1.1 restent à G.
- [x] `osm_layers.gd` : lecture et validation des couches `buildings`, `vegetation`, `poi` et `water` d'un `.world` et tronçons à charger pour une fenêtre de distance, testées sans écran contre un `.world` produit par le vrai compilateur (`engine/tests/test_osm_layers.gd`, `make_osm_world.py`, lot K4) ; le rendu reste à E4.
- [x] `vegetation_placer.gd` : placement déterministe des arbres d'une tuile (zones `vegetation` du `.world` ou bruit de densité sous la limite des arbres), exclusions de la route, de la pente et des trous, testé sans écran (`engine/tests/unit/test_vegetation_placer.gd`, lot K3) ; l'affichage reste à E3 et E4.
- [x] `hud_view_model.gd` : modèle de vue du HUD sans affichage (textes, profil d'altitude devant le cycliste, prochaine montée), testé sans écran (`engine/tests/unit/test_hud_view_model.gd`, lot K2) ; le dessin reste à E3.
- [x] `building_mesh.gd` : maillage 3D des bâtiments extrudés (murs, toit plat avec cours intérieures par couture de ponts, couleurs stables tirées de `id`), testé sans écran (`engine/tests/unit/test_building_mesh.gd`, lot L1) ; le rendu reste à E4.
- [x] `water_mesh.gd` : maillage 3D de la couche eau (cours d'eau en ruban à coudes bornés et plans d'eau avec îles), testé sans écran (`engine/tests/unit/test_water_mesh.gd`, lot L2).
- [x] `theme_render_params.gd` : paramètres de rendu tirés du thème (terrain, route, ciel) et fonction de référence du mélange triplanaire herbe / roche / neige, testés sans écran (`engine/tests/unit/test_theme_render_params.gd`, lot L3) ; le shader reste à E2.
- [x] `quality_presets.gd` : table des préréglages de qualité (`low`, `medium`, `high`) et transmission de `--quality` et `--theme` du lanceur `openride` à `engine_args.gd`, testées sans écran (`engine/tests/unit/test_quality_presets.gd`, lot L4).
- [x] `sound_model.gd` : modèle sonore sans affichage (vent proportionnel à la vitesse jusqu'à 60 km/h, roue libre après 0,5 s à 0 W, hystérésis 1,1× et plafond à 4 sources des points d'intérêt, lissage à 12 dB/s), testé sans écran (`engine/tests/unit/test_sound_model.gd`, lot L5).
- [x] `summary_view_model.gd` : modèle de l'écran de fin de séance sans affichage (10 lignes du bilan enrichi dans l'ordre fixé, 3 lignes en v1, blocs ERG avec déviations et couleurs, fichier FIT seul, écran de menu avec confirmation de quitter), testé sans écran (`engine/tests/unit/test_summary_view_model.gd`, lot N4) ; affiché dans les menus depuis N6 (`summary_view.gd`).
- [x] `devices_view_model.gd` : modèle de l'état des appareils sans affichage (lignes d'état en v1.1 et repli v1, alertes de perte/reconnexion et batterie sous 20 % / 10 %, `ready_to_ride`), testé sans écran (`engine/tests/unit/test_devices_view_model.gd`, lot N5) ; affiché dans les menus depuis N6 (`devices_view.gd`).
- [x] Core au contrat IPC v1.1 (lot N2, `ipc_lists.py`) : réponses `routes` et `workouts` en parties de 60 000 octets au plus (200 éléments, profils de 30 triplets), lues hors de la boucle à 50 Hz ; objet `devices` une trame sur 30 et à chaque changement ; bilan `summary` enrichi (NP, IF, TSS, dénivelé, blocs ERG), testés par `core/tests/test_ipc_v1_1.py`.
- [x] `catalog_model.gd` et client des listes v1.1 (`ipc_client.gd`) : commandes `list_routes` et `list_workouts` avec assemblage des parties par `request_cmd_id` et relance après 1 s, conversion en éléments de menu et scénario complet au Click, testés sans écran (`engine/tests/unit/test_catalog_model.gd`, `test_menu_ipc.gd`, lot N3) ; affiché dans les menus depuis N6.
- [x] `cue_model.gd` : consignes d'essai affichées dans le bandeau avec un bip quand la distance est atteinte, lues dans `~/OpenRide/Essais/<parcours>.consignes.json` (facultatif) et notées `[essai]` dans le journal du lanceur, testées sans écran (`engine/tests/unit/test_cue_model.gd`, essai sur le HomeTrainer du 25 octobre).

### Outils
- [x] `scripts/openride-dev.sh` : lance le core et Godot depuis un seul terminal, et arrête proprement le core à la fermeture de la fenêtre.
- [x] Lanceur unique `openride` (`launcher.py`, lot K6) et raccourci de bureau (`scripts/desktop/openride.desktop.in`, `scripts/desktop/openride.svg`, `scripts/install-desktop.sh`, lot L8) : même rôle que `scripts/openride-dev.sh`, plus la supervision : Godot relancé s'il plante (3 fois en 2 min au plus), arrêt forcé du core au bout de 10 s puis `release-trainer`, arrêt de Godot et rappel de `recover` si le core plante, arrêt propre sur SIGINT, SIGTERM et SIGHUP, et installation utilisateur du fichier `.desktop` et de l'icône SVG dans `~/.local/share`. Reste l'essai réel avec le HomeTrainer et Godot.
- [x] **Recette sans matériel** (lot M6, `core/tests/test_sim_matrix.py`) : les 7 scénarios du Bluetooth simulé joués chacun en séance complète, en ERG et en SIM (14 séances en parallèle, ~2 min 30), avec invariants (aucune erreur inattendue, état final, FIT validé par le SDK Garmin, relâche du trainer, bornes des consignes, `summary` et `log_report`) et attentes par scénario. Aucun défaut trouvé.
- [x] **Parcours depuis un FIT ou un TCX** (lot M7, `compiler/src/openride_compiler/track_formats.py`) : `openride-compiler build sortie.fit` ou `sortie.tcx` (activité ou parcours Garmin), format reconnu par l'extension ou par le contenu, points sans GPS ignorés, FIT sans aucune position refusé (« aucune position GPS dans ce FIT »). `list` et `build-all` ne voient toujours que les `.gpx`.
- [x] **Dette R3 et S2 de la vérification du 24 octobre** (lot M9) : `ErgController` refuse un pas de temps négatif, infini ou NaN et une FTP ≤ 0 ; `pip install -e "compiler[dev]"` seul donne une suite qui passe, les tests qui lisent le core étant sautés (en CI, leur absence est une erreur).
- [x] **Bout en bout sans écran** (lot J8, 23 octobre) : `engine/tests/run_e2e.sh` lance le vrai core (trainer simulé) et le vrai engine dans un dossier personnel temporaire et vérifie hello, cadence des trames, parcours, entrées, perte de l'engine, fin de séance et FIT, en une dizaine de secondes ; exécuté en intégration continue. Il a trouvé que le core n'envoyait que 25 trames `state` par seconde au lieu de 30 (corrigé à part, PR #33).
- [x] **Tests graphiques automatiques** (24 octobre) : `engine/tests/run_visual_tests.sh` rend la vraie scène principale sous Xvfb en trois résolutions et qualités face au faux core, analyse ses captures (textes et mise en page du HUD, bandeau, ciel et sol, caméra qui avance puis se fige, journal de Godot), les compare aux images de référence et écrit un rapport HTML ; une configuration est aussi jouée par `run_engine_tests.sh`, donc en intégration continue. Premier défaut trouvé et corrigé : le bandeau d'alerte recouvrait le HUD élargi (`banner.gd`, `layout_for`).
- [x] Intégration continue GitHub Actions (`.github/workflows/openride.yml`, lot H1) : suites du core, du compilateur et des vecteurs de route en Python 3.11 et 3.14 (`constraints.txt`), et tests de l'engine Godot 4.3 sans écran. Depuis J5 (en partie) : chaque envoi sur `main` testé jusqu'au bout, exécution hebdomadaire, `pip check`.
- [x] Analyseur de journal de séance (`python -m openride_core.tools.log_report`, lot H6) : résumé texte et `--json` de `~/run_trainer.log` (trainer, Click, pauses, seuils Rust SRS §14.1).
- [x] Scénario de simulation tiré d'un journal (`python -m openride_core.tools.log_scenario`, lot M5) : convertit une séance de `~/run_trainer.log` (ou une fenêtre `--from`/`--to`) en scénario du Bluetooth simulé (connexions, coupures par appareil et par boîtier du Click, silences, erreurs ATT, pertes de contrôle, appuis), rejouable par `--sim-scenario FICHIER`.
- [x] Diagnostic des coupures du Click (lot K8) : connexion (adresse, durée de recherche, tentatives), coupure (durée de connexion, dernière notification, dernier appui, dernière écriture au trainer, raison), cadence des notifications toutes les 60 s ; section Click de `log_report` enrichie (durées min/médiane/max, reconnexions, coupures à moins de 2 s du trainer). Reste l'essai de 20 min avec le Click.
- [x] Schéma et validateur de thèmes (`docs/contracts/world/theme.schema.json`, `engine/themes/default/theme.json`, `openride-compiler theme-check`, lot H7).
- [x] Outils et bibliothèque d'entraînements ERG (`python -m openride_core.tools.workouts list|check|install` et 5 fichiers `.zwo` de référence dans `core/workouts/`, lot H8).
- [x] Bilan de séance (`openride-core summary [FICHIER] [--ftp W] [--json]`, lot K7) : durée hors pauses, distance, dénivelé, puissance moyenne et normalisée, IF, TSS, zones de Coggan, meilleures puissances 5 s à 20 min, cadence et FC, puissance par bloc ERG (cible absente du journal v1 : écart signalé indisponible) ; `.jsonl` et `.fit` donnent les mêmes chiffres.
- [x] Cible ERG dans le journal et bilan par bloc (`target_w` dans `Record`, `session.py` et `session_summary.py`, lot L6) : cible envoyée au trainer (lissage 2 s et biais compris) enregistrée à 1 Hz en mode ERG (`null` en SIM, roue libre et pause), moyenne `target_w` et écart `delta_w` par bloc dans `openride-core summary` avec rétrocompatibilité des anciens journaux et des `.fit`.
- [x] Biais ERG et coupures dans le journal (lot M4, `journal.py`, `recorder.py`, `session.py`, `session_summary.py`) : champ `erg_bias_pct` (biais du Click à chaque relevé, `null` hors ERG actif), lignes `device` au changement d'état du trainer, des boîtiers du Click et de la ceinture ; `summary` donne par bloc ERG le biais moyen et l'écart à la cible sans biais, et une section `devices` (coupures et durée par appareil), sans rien changer pour un journal antérieur ni pour le FIT.
- [x] Historique des séances (`openride-core history [--dir DOSSIER] [--weeks N] [--ftp W] [--json]`, `history.py`, lot L7) : liste des séances de `~/OpenRide/Activities/` dédoublonnées entre `.fit` et `.jsonl` (± 60 s), journaux orphelins signalés « à récupérer », cumul par semaine ISO (nombre, durée, distance, TSS) et cache `~/.cache/openride/history.json`.
- [x] Vérification du 24 octobre (`docs/VERIFICATION_2026-10-24.md`) : `Repeat` des `.zwo` borné à 100 (R1), FTP nulle, négative ou non finie refusée par `workouts check` (R2), cahiers des lots K6 et K7 rédigés et inscrits à l'index, et contrôle des lots cités dans la documentation (S1).
- [x] Revue de code du 24 octobre (`docs/REVUE_CODE_2026-10-24.md`), après la fusion d'E1 et des lots K : `log_report` compte les connexions et coupures par boîtier (Click à deux boîtiers ; la ligne de coupure porte l'adresse), le lanceur n'annonce plus une pause qu'il ne fait pas, pente NaN ramenée à 0 %, analyseur du core partagé avec le test de cohérence, lint propre.
- [x] Couches OpenStreetMap `buildings` et `vegetation` du compilateur (`osm.py`, `osm_layers.py`, cache brut `~/.cache/openride/osm/`, schémas `buildings.schema.json` et `vegetation.schema.json`, lot I3).
- [x] Couches OpenStreetMap `poi` et `water` du compilateur (points d'intérêt sonores/visuels, cours d'eau découpés par tronçon de 1 km et plans d'eau avec îles, schémas `poi.schema.json` et `water.schema.json`, lot I4).
- [x] **Packs de thèmes** (`openride-compiler theme-list` et `theme-install`, lot N10, `theme_packs.py`) : liste avec statut, textures et taille, installation depuis dossier ou archive `.zip` avec contrôle d'intégrité (rejet des liens symboliques, chemins `..` et taille > 500 Mo) et validation complète avant copie atomique, testés par `compiler/tests/test_theme_packs.py`.

---

## 2. Ce qui a été testé

### Tests automatiques
**665 tests pytest passent dans le core et 183 dans le compilateur** (traces FIT et TCX (lot M7), physique, braquets, FTMS et conformité à la spécification FTMS v1.0 (audit du 24 octobre, `docs/AUDIT_FTMS_2026-10-24.md`), Click, recherche Bluetooth et repli BlueZ sans matériel (lot H2), rejeu JSONL/FIT dans le simulateur (lot H3), endurance simulée de 3 h (lot H4), validation FIT indépendante par `garmin-fit-sdk` (lot H5), analyseur de journal `log_report` (lot H6), schéma et validateur de thèmes `theme-check` (lot H7), outils et bibliothèque d'entraînements `.zwo` (lot H8), cohérence documentation/code (lots I1 et J7 : caractères, liens, nombres de tests, chemins cités), catalogue des parcours `list` et `build-all` (lot I2) et parité de son repli sans core (lot J6), robustesse IPC aux messages malformés (lot J2), validation de `config.toml` (lot J3), choix du parcours et de l'entraînement au lancement (lot J1), libération du trainer à l'arrêt (PR #28), couches OpenStreetMap (lots I3 et I4), journal, FIT, IPC, pilotes avec faux client Bluetooth, boucle de séance, tests de contrat, lecture des parcours). Couverture globale du core : 76 % (`ble_util.py` à 100 %). Côté Godot, sans écran (`engine/tests/run_engine_tests.sh`) : tests unitaires lancés par découverte (lot K1) : 42 vecteurs de route, 42 vérifications de thèmes (lot I5), 76 du modèle de HUD (K2), 19 du placement de la végétation (K3), 19 de la navigation des menus (K5) ; 27 vérifications des couches OSM (K4), 54 vérifications ERG (lot I6), rendu par tronçons (E1) et 8 scénarios IPC. Revérifié le 23 octobre au soir (audit J, `docs/AUDIT_2026-10-23.md` §9) ; `build-all` corrigé à cette occasion.

### Essais sur le PC cible, 22 octobre 2026
PC de bureau MSI sous Ubuntu, GTX 1060, Python 3.14.4, bleak 3.0.2, Godot 4.3.

- **HomeTrainer (BLE) :** détection, FTMS, SIM, ERG, plage de 0 à 1 000 W, cardio (0 bpm = pas de mesure). Connexion stable pendant plusieurs minutes avec le pilote réel.
- **Click (BLE) :** handshake sans chiffrement, format `0x23` (bit 12 = +, bit 8 = −), appuis courts et longs dans le bon sens, bips validés à l'oreille.
- **FIT :** séance de démonstration et séance réelle importées sans erreur (contrôle fait par le propriétaire le 22 octobre).
- **Godot :** HUD et caméra mis à jour par le core, touches transmises au core.
- **Performance du core :** pas de physique p50 0,2 ms, retard de boucle max 3 à 19 ms, CPU 3 à 4 %. Aucun seuil Rust approché.

### Défauts trouvés et corrigés pendant les essais

| Défaut | Cause | Correction |
| --- | --- | --- |
| `org.bluez.Error.InProgress` | Trainer et Click scannaient en même temps (BlueZ n'accepte qu'une opération à la fois) | Verrou commun, trainer prioritaire |
| Trainer « introuvable » | Nom cherché « HomeTrainer », annoncé « HomeTrainer 0000 » | Nom par défaut « HomeTrainer » |
| Pas de physique p99 à 7 ms | `fsync` du journal à chaque ligne | `fsync` toutes les 5 s (`flush` à chaque ligne conservé) |
| Lag perçu sur les changements de braquet | Pente envoyée limitée à 2 points/s, même pour un changement de braquet | Le braquet saute à la cible ; la limite ne vaut que pour le relief |
| Export FIT en échec | Vitesse moyenne hors plage avec un chrono aberrant | Vitesse moyenne bornée par la vitesse max |
| HUD vide dans Godot | `class_name` inconnus quand le projet n'est pas importé par l'éditeur | Chargement explicite des scripts |
| Moteur « perdu » toutes les 4 s | Heartbeat lié au rendu | Heartbeat dans un fil séparé |
| Séance en pause sans reprise | Aucun bouton de reprise à l'écran | `--autostart` reprend seul après `engine_lost` / `trainer_lost` |
| Click intermittent | Recherche par fenêtres de 6 s puis attente jusqu'à 10 s ; le Click ne s'annonce qu'après un appui | Recherche continue (5 s, pause de 0,5 à 2 s) |
| Click invisible au scan | Resté « connecté » côté BlueZ après une coupure | Repli sur les appareils connus de BlueZ |
| HomeTrainer réservé après une séance (23 octobre) : une autre application ne pouvait plus le piloter | Le contrôle FTMS n'était jamais rendu (pas de Reset) ; fermer le terminal (SIGHUP) tuait le core sans relâcher le trainer, BlueZ gardant la liaison | Pente 0 %, Reset puis déconnexion à l'arrêt, SIGHUP géré, commande `openride-core release-trainer` (PR #28) |

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

- [ ] Raccourci de bureau (lot L8) : tester `scripts/install-desktop.sh` sur le PC Ubuntu et vérifier la classe de fenêtre Godot (`xprop WM_CLASS` : `"OpenRide Engine"`).
- [ ] Historique (lot L7) : tester `openride-core history --weeks 8` sur `~/OpenRide/Activities/` avec les séances réelles.
- [ ] Cible ERG (lot L6) : vérifier lors d'une séance ERG réelle que la cible est bien écrite dans le `.jsonl` et que `openride-core summary` affiche l'écart à la cible par bloc.
- [ ] Modules graphiques et sonores (lots L1 à L5) : valider le rendu visuel et sonore (bâtiments, eau, thème triplanaire, qualité graphique, vent, roue libre et bips) une fois raccordés à la scène principale (E2, E3, E4).
- [ ] Séance réelle de 10 minutes ou plus avec braquets perceptibles, puis relecture des mesures `Perf` du log.
- [x] Après une séance ERG, quitter OpenRide puis piloter le HomeTrainer depuis une autre application (PR #28 et #45) : validé par le propriétaire le 24 octobre, le trainer est libéré et une autre application s'y reconnecte.
- [ ] Erreur ATT 0x80 (lot M1) : après une séance ERG, relire `~/run_trainer.log` ; une éventuelle erreur 0x80 doit être suivie de « renvoi 1/2 » et non de « Reconnexion au trainer ».
- [ ] Ceinture cardio (lot M2) : une séance avec la ceinture réelle et la montre allumée ; vérifier au journal la liste des appareils trouvés, l'appareil choisi et la batterie (`grep -i cardio ~/run_trainer.log`).
- [ ] Journal (lot M4) : après une séance ERG avec quelques appuis au Click, `openride-core summary` doit afficher le biais par bloc et, s'il y a eu des coupures, la section « Coupures des appareils ».
- [ ] Inventaire et appairage (lots M3 et N12) : `openride-core devices --save` avec le HomeTrainer, les deux boîtiers du Click réveillés et la ceinture ; appuyer sur « + » quand demandé, vérifier `~/OpenRide/config.toml`, puis rouler une séance avec les deux boîtiers.
- [ ] Panne rejouée (lot M5) : après la prochaine coupure réelle, `python -m openride_core.tools.log_scenario -o ~/panne.json` puis `scripts/openride-dev.sh --trainer sim --input sim --hr sim --sim-scenario ~/panne.json --autostart`.
- [ ] Parcours FIT (lot M7) : exporter de Garmin Connect le FIT d'origine d'une vraie sortie, `openride-compiler build sortie.fit`, puis rouler le parcours ; signaler si Garmin Connect livre un `.fit.gz` ou un `.zip` (non lus).
- [ ] Journal du lanceur (lot M8) : lancer par l'icône du bureau, quitter, puis `python -m openride_core.tools.log_report` sans argument ; vérifier que `~/run_trainer.log` pointe vers `~/OpenRide/Logs/openride_…log`, que l'ancien journal est devenu `run_trainer.log.ancien` et que les lignes `[engine]` de Godot y sont.
- [ ] Délai entre un appui et l'écriture de la commande au HomeTrainer.
- [ ] Click : cause des déconnexions spontanées (environ 2 en 3 minutes le 22 octobre, reconnexion en 4 s environ).
- [ ] Images par seconde de Godot, à relever quand le décor sera chargé (lot E1).
- [ ] ERG (lot F) : un `.zwo` standard exécuté en entier sur le HomeTrainer, cibles tenues (critère 11 du lot F). Débloqué par le lot J1 (24 octobre) : `scripts/openride-dev.sh --trainer ftms --input click --autostart --workout sweet_spot_3x10`, après `python -m openride_core.tools.workouts install`.

---

## 4. Ce qui reste à faire

Les travaux confiables à une autre IA sont décrits dans [`docs/lots/`](lots/00_INDEX.md). Les lots H1 à H8 et I1 à I6 ont tous été livrés et fusionnés le 23 octobre (tests de cohérence documentation/code, catalogue de parcours, couches OSM bâtiments/végétation/points d'intérêt/eau, chargeur de thèmes GDScript et logique ERG Godot testée sans écran). Série J (audit J du 23 octobre au soir) : J1 (parcours et entraînement au lancement, `run --autostart --route ID --workout ID`, 24 octobre), J2 (robustesse IPC), J3 (configuration validée), J6 (catalogue unique), J7 (cohérence de la documentation) et J8 (bout en bout sans écran) faits directement, J4 et J5 en partie ; restent à confier la fin de J4 et J5. Série L (24 octobre) : les huit lots délégables L1 à L8 ont tous été livrés et fusionnés le 24 octobre (maillage bâtiments/eau, paramètres de rendu du thème, préréglages de qualité, modèle sonore, cible ERG au journal, historique des séances, raccourci de bureau). Série M (24 octobre, cahiers rédigés) : neuf lots Python délégables M1 à M9, testés avec le Bluetooth simulé (renvoi après l'erreur ATT 0x80, ceinture cardio réelle, inventaire des appareils, biais ERG et coupures au journal, scénario tiré d'un journal réel, matrice des scénarios simulés, compilateur FIT et TCX, journal du lanceur, dette R3 et S2). Série N (24 octobre au soir, cahiers rédigés) : suite du chemin du MVP après E3 et E4, onze lots N1 à N11 (contrat IPC v1.1, core et client des listes, modèles de l'écran de fin et de l'état des appareils, affichage des menus, ERG à l'écran, reprise après un plantage du core, bots, packs de thèmes, compilation au lancement) ; les quatorze lots N1 à N14 sont tous livrés et fusionnés (N1 le 24 octobre, N13 le 26 octobre, les autres le 25) ; restent les essais sur le PC listés ci-dessous. Chaque lot ouvert a son issue GitHub, regroupée dans l'issue de suivi [#48](https://github.com/Holeinthesock67/lolo_python/issues/48) (procédure : [`docs/lots/00_INDEX.md`](lots/00_INDEX.md) §5).


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

### Sprint 3 : rendu 3D (lots D, E1, E2, puis E3 à rédiger)
- [x] Godot conforme au contrat (renvoi des commandes, extrapolation, core injoignable), lot D.
- [ ] Cahiers E3 (ciel, arbres par bruit, HUD final) et E4 (bâtiments, forêts OSM, eau, sons) rédigés le 24 octobre, avec la revue du lot E2 (`docs/REVUE_E2_2026-10-24.md`) : à faire après la fusion d'E2 corrigé.
- [ ] Ruban de route et terrain par tronçons (lot E1 fusionné le 24 octobre, PR #7, tests sans écran verts) : reste l'essai sur la GTX 1060 (images par seconde, à-coups, trous).
- [x] Shader triplanaire et application du thème (lot E2, PR #75 et #97, 24 octobre) : projection en mètres, mélange herbe/roche/neige selon pente et altitude (constantes du lot L3 transmises au shader), route et soleil pilotés par le thème ; vrai rendu vérifié sous Xvfb (`engine/tests/render/test_terrain_render.gd`). Essai sur la GTX 1060 le 24 octobre (`docs/ESSAI_GRAPHIQUE_E2.md`, démo avec terrain synthétique, préréglage `low`) : 633 images/s en couleurs unies, 609 avec trois textures 2 048² (perte 3,7 %), aucune erreur Godot, aspect validé à l'écran par le propriétaire. Reste la neige sur un vrai parcours au-dessus de 2 200 m.
- [ ] **Ciel, arbres par bruit et HUD final** (lot E3, 24 octobre) : ciel physique PhysicalSkyMaterial, brouillard de limite à 12 km, arbres instanciés en LOD0/LOD1 avec respect du budget d'instances, HUD avec profil d'altitude et prochaine montée, mesure périodique `[perf-rendu]`. Reste la recette sur la GTX 1060 (`docs/RECETTE_E3_E4.md`).
- [ ] **Bâtiments, forêts OSM, eau et sons du parcours** (lot E4, 24 octobre) : streaming des tronçons OSM (`osm_streamer.gd`), bâtiments avec jupe de 3 m sous `base_y`, rivières et plans d'eau (`water_mesh.gd`), modèle sonore spatialisé (`sound_player.gd`). Reste la recette sur la GTX 1060 (`docs/RECETTE_E3_E4.md`).

### Lanceur et menus (ancien lot G, série N rédigée le 24 octobre)
- [x] Lanceur unique `openride` (`launcher.py`, lot K6) et raccourci de bureau (`scripts/desktop/openride.desktop.in`, `scripts/desktop/openride.svg`, `scripts/install-desktop.sh`, lot L8).
- [x] Améliorer la journalisation du lanceur sans terminal (`Terminal=false`) : lot M8, un journal par lancement dans `~/OpenRide/Logs/` (core, Godot préfixé `[engine]`, lanceur `[openride]`), lien `~/run_trainer.log` vers le dernier, rotation 20 journaux / 200 Mo ; sans terminal, les messages ne vont qu'au journal.
- [x] Supervision : relance du core ou de l'engine sans perdre la séance (relance de Godot faite par K6 ; reprise après un plantage du core par `openride-core run --resume JOURNAL`, relancé par le lanceur au plus 3 fois en 10 minutes, séance en pause `core_restarted` dans le même journal et un seul FIT, lot N8, testé par `core/tests/test_resume.py` et `test_launcher.py`) ; reste l'essai sur le PC (`pkill -9 -f openride-core` pendant une séance).
- [ ] Menu piloté au Click et au clavier (parcours, démarrage, pause, fin), à la place de `--autostart` : contrat IPC v1.1 (lot N1), core (N2), client des listes (N3), écran de fin (N4), affichage (N6, livré le 25 octobre : `menu_flow.gd`, `menu_view.gd`, `devices_view.gd`, `summary_view.gd`, lanceur sans `--autostart`, bouton Y du Click = pause, écrans de menu dans les tests graphiques) ; reste la recette sur le PC (critères 2, 4 et 5 du cahier N6, lisibilité à 2 m) et `run_visual_tests.sh --update-golden` une fois les nouvelles images vérifiées.
- [x] Section « Appareils » du menu : rechercher le trainer, les boîtiers du Click et la ceinture, puis garder leur nom et leur adresse dans `~/OpenRide/config.toml`, jamais dans le dépôt (demande du 25 octobre) : enregistrement côté core (lot N12), écran du menu et écran « Connexion des appareils » au lancement avec « Passer » (N13, 26 octobre ; testé au banc des menus `engine/tests/menu_bench.py`). Reste l'essai avec le vrai Click sur le PC.
- [ ] Lancer et utiliser OpenRide sans ligne de commande après une installation en une commande (demande du 25 octobre) : icône (L8, livré), menus (N6), compilation au lancement (N11), appareils (N12, N13), premier démarrage, erreurs dans une fenêtre et mise à jour depuis le bureau (N14, livré le 25 octobre : `scripts/install.sh`, `scripts/update.sh`, `scripts/config.example.toml`, entrées « Libérer le trainer » et « Mettre à jour », testés par `core/tests/test_launch_no_terminal.py` ; reste l'essai depuis l'icône sur le PC).
- [x] Compiler les nouvelles traces GPX au lancement (lot N11).
- [ ] Écran d'état des appareils (trainer, Click, batterie du Click) : modèle (lot N5), affichage dans l'accueil et l'écran « Prêt » (N6, livré le 25 octobre) ; reste l'essai d'un boîtier débranché pendant le menu sur le PC.

### Version 1.0 (série O rédigée le 25 octobre)
- [ ] Arbres : préparation d'une tuile sous 150 ms, 210 ms mesurés sur le PC cible (lot O1).
- [ ] Numéro de version unique et notes de version (lot O2).
- [ ] Réglages FTP, thème et qualité depuis le menu : core fait (lot O3, 26 octobre : `settings.py`, `config_writer.py` commun avec l'appairage, `openride-core settings [set CLÉ VALEUR]`), écran (lot O4).
- [ ] Traces FIT, TCX et archives Garmin déposées dans `~/OpenRide/GPX/` (lot O5).
- [ ] Guide d'utilisation sans terminal et README de la 1.0 (lot O6).
- [ ] Bots à l'écran, facultatif pour la 1.0 (lot O7).
- [x] Entraînements GoldenCheetah `.erg` et `.mrc` (lot O9, 25 octobre) : lecture dans `workout_formats.py`, cibles en watts absolues pour les `.erg` (`--erg-relative` pour les ramener à la FTP), `list`, `check` et `install` ; reste l'essai d'un `.erg` exporté de GoldenCheetah sur le PC cible.
- [ ] Test de FTP par rampe ou sur 20 minutes, nouvelle FTP enregistrée après accord (lot O10).
- [ ] Plans d'entraînement sur plusieurs semaines et séance du jour (lot O11).
- [ ] Courbes de la séance façon GoldenCheetah (cible, puissance, FC, cadence) : modèle (lot O13), écran (lot O14).
- [ ] Bibliothèque de parcours : fiches, tri, filtres, packs (lot O15).
- [ ] Pack de départ de cols célèbres (Alpe d'Huez, Ventoux, Vosges, Teide, Japon…) construit depuis OpenStreetMap (lot O16).
- [ ] Menu des plans, du test de FTP et de la bibliothèque (lot O12).
- [ ] Recette sur le matériel et publication de `v1.0.0` (lot O8, liste unique des essais du §3).

### Retours de l'essai du 25 octobre sur le HomeTrainer (série Q rédigée le 25 octobre)
- [x] Difficulté du trainer à 50 % par défaut, réglable pendant la séance par un curseur du menu, affichée dans le HUD (lot Q1, contrat IPC v1.2 accepté ; curseur dans O4).
- [ ] Pentes plus lisibles à l'écran : caméra inclinée, relief exagéré à l'affichage seulement (lot Q2).
- [x] Journal des commandes FTMS et des accusés, délais dans `log_report` (lot Q3, `ftms_driver.py`, option `--trace-ftms`, clé `[trainer] trace_ftms`, analyse des délais et statuts dans `log_report`, testé par `test_ftms_trace.py`).
- [ ] Rampe de pente plus rapide, surtout à la descente (lot Q4).
- [ ] FC relayée par le trainer figée : écrite comme absente (lot Q5).
- [ ] Boîtier gauche du Click muet après la connexion : trace, détection, reprise (lot Q6).

### Performances du rendu (série S rédigée le 25 octobre)
- [ ] Ne pas dessiner ce que le cycliste ne voit pas : étude mesurée au banc simulé, puis réductions sans changement visible (lot S1).

### Après la 1.0 : décor vivant, vent et aspiration (série P rédigée le 25 octobre)
- [x] Contrat : vent et aspiration dans `state` (IPC révision 1.3), configuration `[wind]`, thème 1.2, points d'intérêt `wind_turbine` et `flag` (lot P1, décisions du propriétaire du 25 octobre).
- [x] Vent physique côté core : vent calme, fixe, en rafales ou du thème, composante de face sur la physique (cycliste et bots), supplément de pente en SIM borné à 4 points ou champ vent FTMS, ERG vitesse seulement, champ `wind` 2 fois par seconde, journal (lot P2, `core/tests/test_wind.py`).
- [x] Aspiration derrière les bots à puissance constante (courbe mesurée, effet de file, vent de travers, poussée du bot suivi), lissée à 1 s, sur la vitesse et la pente envoyée en SIM, champs `draft` et `draft_bot`, temps à l'abri dans le bilan (lot P3, `core/tests/test_draft.py`).
- [ ] Vent physique et aspiration derrière les bots, côté core (lots P2 et P3).
- [x] Engine : modèle du vent lissé pour tout le décor, modèle de l'indicateur du vent (favorable ou non, intensité) et de l'abri, budgets du décor vivant par préréglage (lot P4, sans affichage).
- [x] Arbres qui se balancent au vent (shader `tree_sway.gdshader`, paramètres globaux du vent) et touffes d'herbe en bord de route au vent apparent en qualité moyenne et haute (lot P5, branchement dans `main.gd` par P16).
- [x] Nuages qui défilent au vent (shader de ciel `sky_clouds.gdshader`, une couche en `low` et `medium`, deux en `high`) et ombre des nuages sur le terrain en `high` (lot P6, branchement dans `main.gd` par P16).
- [x] Météo légère du thème 1.2 : brume de vallée, pluie fine et neige légère poussées par le vent, autour de la caméra, au budget de `living(preset)` (lot P8 ; brume appliquée et branchement dans `main.gd` par P17).
- [x] Fonds sonores d'ambiance selon le décor (oiseaux en forêt, insectes au champ, eau, rumeur du village, vent d'altitude, pluie), au plus `ambience_voices` à la fois, et cloches de l'heure pleine (lot P9 ; voisinage et heure fournis par P16).
- [x] Son du vent selon la vitesse dans l'air (vent de face ou de dos, rafales) et roue libre réaliste : déclenchée à cadence nulle, cliquetis qui suit la vitesse de la roue, « clac » à la reprise (lot P10 ; branchement par P16).
- [x] Vent branché dans la scène : indicateur du HUD sous la colonne de gauche (flèche, « 18 km/h face », niveau, pastille verte, rouge ou grise), arbres et herbe au vent, nuages qui défilent, fonds sonores selon le décor ; réglages du vent ajoutés à la liste du menu, `[render] living` pour tout couper (lot P16 ; recette sur le PC : `docs/RECETTE_P16.md`).
- [x] Animaux : bandes d'oiseaux au-dessus des forêts, troupeaux près des points `livestock`, chevreuil en lisière qui s'enfuit, dans le budget de `living(preset)` (lot P11 ; branchement par P17).
- [ ] Indicateur du vent et de l'abri, arbres et herbe au vent, nuages, sons d'ambiance, sons du vent et de la roue libre (lots P4, P5, P6, P9, P10 ; intégration P16).
- [ ] Météo légère, animaux, éoliennes et drapeaux, véhicules, bord de route, spectateurs, passants (lots P8, P11 à P15, P21 ; intégration P17).
- [ ] Version 2.0 : jour et nuit, saisons (lots P7, P18 ; intégration P19) ; packs de textures selon les performances (lot P20).

### Sprint 4 et suivants
- [x] Entraînements ERG `.zwo` (lot F, fusionné le 23 octobre ; essai sur le HomeTrainer à faire).
- [x] Couches OpenStreetMap côté compilateur (lots I3 bâtiments et végétation, I4 points d'intérêt et eau) ; reste le rendu dans l'engine (à rédiger).
- [x] Thèmes avec packs de textures : liste et installation (lot N10).
- [ ] Bandeau ERG, histogramme et bip à T − 3 s à l'écran (lot N7, ancien F2) : code et tests sans écran et graphiques livrés le 25 octobre (`erg_view.gd`) ; histogramme aux vraies durées depuis N6 (liste `workouts` du contrat v1.1) ; reste l'essai de `sweet_spot_3x10` sur le HomeTrainer.
- [x] Bots à puissance constante et fantôme d'une séance passée, côté core (lot N9) ; affichage à rédiger.
