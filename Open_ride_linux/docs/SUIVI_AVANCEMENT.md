# OpenRide Linux – Bilan et suivi d'avancement

Mise à jour : 24 octobre 2026 (fusions E1, K1 à K5, K8, braquets réactifs et deux boîtiers du Click ; libération du trainer validée sur le HomeTrainer) ; précédente : 24 octobre au matin (vérification et correctifs R1, R2, S1, PR #44)
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
  - `zwift_click.py` : formats `0x37` (ancien Click) et `0x23` (Click récent), appui court sous 0,5 s, appui long à partir de 0,9 s.
- [x] **Pilotes réels :**
  - `ftms_driver.py` : HomeTrainer, avec reconnexion à délai croissant, prise de contrôle, lissage de la puissance, FC à 0 traitée comme absente, à l'arrêt : pente 0 %, Reset (contrôle FTMS rendu) et déconnexion, y compris sur SIGHUP ; dépannage `openride-core release-trainer` ;
  - `input_providers.py` : Click avec recherche continue, clavier en parallèle ;
  - `ble_util.py` : une seule opération Bluetooth à la fois, repli sur les appareils connus de BlueZ.
- [x] **Boucle de séance** (`session.py`, `openride-core run`) : physique à 50 Hz, IPC à 30 Hz, journal à 1 Hz, FIT en fin de séance, pente anticipée et lissée, mesures de performance toutes les 60 s.
- [x] **Journal** (`journal.py`) : JSONL à 1 Hz, `flush` à chaque ligne, `fsync` toutes les 5 s, tolérant aux plantages.
- [x] **Export FIT** (`fit_export.py`) et récupération (`openride-core recover`).
- [x] **Diagnostic BLE** (`openride-ble-diag`) : `scan`, `trainer`, `click`.
- [x] **Robustesse IPC** (lot J2, 23 octobre) : un message JSON non conforme (liste, `cmd_id` non entier, `args` invalide) est ignoré et compté au lieu d'arrêter la boucle ; une erreur dans une commande est journalisée sans arrêter la séance.
- [x] **Conformité au contrat IPC** (lot C, 23 octobre) : commandes acceptées après un redémarrage de Godot, panne d'écriture du journal sans arrêt de la boucle (`recorder.py` : séance en mémoire, nouveau journal à la reprise), résumé de fin conforme, refus du contrôle FTMS remonté (`ERROR`), consigne ERG bornée, `hello_ack` et coefficient de difficulté tirés de la configuration.
- [x] **Lecture des parcours** (lot A, 23 octobre) : `route.py` charge et valide un `.world`, interpole la route (Catmull-Rom centripète) et gère les boucles ; la séance charge le parcours demandé par son nom ; parcours de démonstration unique (`demo_world.py`).
- [x] **Entraînements ERG** (lot F, 23 octobre) : `workout.py` lit les `.zwo` de `~/OpenRide/Workouts/` (intervalles dépliés, fichiers invalides listés avec leur erreur) ; la séance envoie la cible ERG lissée sur 2 s, biais ± 2 % et saut de bloc au Click, pause ERG à pente 0 %, roue libre en SIM avec les braquets, objet `erg` des trames `state` et `mode` / `block` dans le journal.
- [x] **Simulateur** (`mock_driver.py`, `replay.py`) : SIM, ERG, cadence, cardio, déconnexion, rejeu d'une séance enregistrée (`.jsonl` ou `.fit`, lot H3).

### Module engine (`openride-engine`, Godot 4.3)
- [x] Client IPC (`ipc_client.gd`) : `hello` répété jusqu'à la réponse, heartbeat dans un fil séparé, commandes vers le core.
- [x] Scène de démonstration (`main.gd`) : polyligne du parcours, caméra subjective, HUD (puissance, vitesse, braquet, cadence, pente réelle et envoyée, distance, état de la séance).
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

### Outils
- [x] `scripts/openride-dev.sh` : lance le core et Godot depuis un seul terminal, et arrête proprement le core à la fermeture de la fenêtre.
- [x] Lanceur unique `openride` (`launcher.py`, lot K6) et raccourci de bureau (`scripts/desktop/openride.desktop.in`, `scripts/desktop/openride.svg`, `scripts/install-desktop.sh`, lot L8) : même rôle que `scripts/openride-dev.sh`, plus la supervision : Godot relancé s'il plante (3 fois en 2 min au plus), arrêt forcé du core au bout de 10 s puis `release-trainer`, arrêt de Godot et rappel de `recover` si le core plante, arrêt propre sur SIGINT, SIGTERM et SIGHUP, et installation utilisateur du fichier `.desktop` et de l'icône SVG dans `~/.local/share`. Reste l'essai réel avec le HomeTrainer et Godot.
- [x] **Bout en bout sans écran** (lot J8, 23 octobre) : `engine/tests/run_e2e.sh` lance le vrai core (trainer simulé) et le vrai engine dans un dossier personnel temporaire et vérifie hello, cadence des trames, parcours, entrées, perte de l'engine, fin de séance et FIT, en une dizaine de secondes ; exécuté en intégration continue. Il a trouvé que le core n'envoyait que 25 trames `state` par seconde au lieu de 30 (corrigé à part, PR #33).
- [x] Intégration continue GitHub Actions (`.github/workflows/openride.yml`, lot H1) : suites du core, du compilateur et des vecteurs de route en Python 3.11 et 3.14 (`constraints.txt`), et tests de l'engine Godot 4.3 sans écran. Depuis J5 (en partie) : chaque envoi sur `main` testé jusqu'au bout, exécution hebdomadaire, `pip check`.
- [x] Analyseur de journal de séance (`python -m openride_core.tools.log_report`, lot H6) : résumé texte et `--json` de `~/run_trainer.log` (trainer, Click, pauses, seuils Rust SRS §14.1).
- [x] Diagnostic des coupures du Click (lot K8) : connexion (adresse, durée de recherche, tentatives), coupure (durée de connexion, dernière notification, dernier appui, dernière écriture au trainer, raison), cadence des notifications toutes les 60 s ; section Click de `log_report` enrichie (durées min/médiane/max, reconnexions, coupures à moins de 2 s du trainer). Reste l'essai de 20 min avec le Click.
- [x] Schéma et validateur de thèmes (`docs/contracts/world/theme.schema.json`, `engine/themes/default/theme.json`, `openride-compiler theme-check`, lot H7).
- [x] Outils et bibliothèque d'entraînements ERG (`python -m openride_core.tools.workouts list|check|install` et 5 fichiers `.zwo` de référence dans `core/workouts/`, lot H8).
- [x] Bilan de séance (`openride-core summary [FICHIER] [--ftp W] [--json]`, lot K7) : durée hors pauses, distance, dénivelé, puissance moyenne et normalisée, IF, TSS, zones de Coggan, meilleures puissances 5 s à 20 min, cadence et FC, puissance par bloc ERG (cible absente du journal v1 : écart signalé indisponible) ; `.jsonl` et `.fit` donnent les mêmes chiffres.
- [x] Cible ERG dans le journal et bilan par bloc (`target_w` dans `Record`, `session.py` et `session_summary.py`, lot L6) : cible envoyée au trainer (lissage 2 s et biais compris) enregistrée à 1 Hz en mode ERG (`null` en SIM, roue libre et pause), moyenne `target_w` et écart `delta_w` par bloc dans `openride-core summary` avec rétrocompatibilité des anciens journaux et des `.fit`.
- [x] Historique des séances (`openride-core history [--dir DOSSIER] [--weeks N] [--ftp W] [--json]`, `history.py`, lot L7) : liste des séances de `~/OpenRide/Activities/` dédoublonnées entre `.fit` et `.jsonl` (± 60 s), journaux orphelins signalés « à récupérer », cumul par semaine ISO (nombre, durée, distance, TSS) et cache `~/.cache/openride/history.json`.
- [x] Vérification du 24 octobre (`docs/VERIFICATION_2026-10-24.md`) : `Repeat` des `.zwo` borné à 100 (R1), FTP nulle, négative ou non finie refusée par `workouts check` (R2), cahiers des lots K6 et K7 rédigés et inscrits à l'index, et contrôle des lots cités dans la documentation (S1).
- [x] Revue de code du 24 octobre (`docs/REVUE_CODE_2026-10-24.md`), après la fusion d'E1 et des lots K : `log_report` compte les connexions et coupures par boîtier (Click à deux boîtiers ; la ligne de coupure porte l'adresse), le lanceur n'annonce plus une pause qu'il ne fait pas, pente NaN ramenée à 0 %, analyseur du core partagé avec le test de cohérence, lint propre.
- [x] Couches OpenStreetMap `buildings` et `vegetation` du compilateur (`osm.py`, `osm_layers.py`, cache brut `~/.cache/openride/osm/`, schémas `buildings.schema.json` et `vegetation.schema.json`, lot I3).
- [x] Couches OpenStreetMap `poi` et `water` du compilateur (points d'intérêt sonores/visuels, cours d'eau découpés par tronçon de 1 km et plans d'eau avec îles, schémas `poi.schema.json` et `water.schema.json`, lot I4).

---

## 2. Ce qui a été testé

### Tests automatiques
**320 tests pytest passent dans le core et 154 dans le compilateur** (physique, braquets, FTMS et conformité à la spécification FTMS v1.0 (audit du 24 octobre, `docs/AUDIT_FTMS_2026-10-24.md`), Click, recherche Bluetooth et repli BlueZ sans matériel (lot H2), rejeu JSONL/FIT dans le simulateur (lot H3), endurance simulée de 3 h (lot H4), validation FIT indépendante par `garmin-fit-sdk` (lot H5), analyseur de journal `log_report` (lot H6), schéma et validateur de thèmes `theme-check` (lot H7), outils et bibliothèque d'entraînements `.zwo` (lot H8), cohérence documentation/code (lots I1 et J7 : caractères, liens, nombres de tests, chemins cités), catalogue des parcours `list` et `build-all` (lot I2) et parité de son repli sans core (lot J6), robustesse IPC aux messages malformés (lot J2), validation de `config.toml` (lot J3), choix du parcours et de l'entraînement au lancement (lot J1), libération du trainer à l'arrêt (PR #28), couches OpenStreetMap (lots I3 et I4), journal, FIT, IPC, pilotes avec faux client Bluetooth, boucle de séance, tests de contrat, lecture des parcours). Couverture globale du core : 76 % (`ble_util.py` à 100 %). Côté Godot, sans écran (`engine/tests/run_engine_tests.sh`) : tests unitaires lancés par découverte (lot K1) : 42 vecteurs de route, 40 vérifications de thèmes (lot I5), 60 du modèle de HUD (K2), 19 du placement de la végétation (K3), 19 de la navigation des menus (K5) ; 27 vérifications des couches OSM (K4), 54 vérifications ERG (lot I6), rendu par tronçons (E1) et 8 scénarios IPC. Revérifié le 23 octobre au soir (audit J, `docs/AUDIT_2026-10-23.md` §9) ; `build-all` corrigé à cette occasion.

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
- [ ] Délai entre un appui et l'écriture de la commande au HomeTrainer.
- [ ] Click : cause des déconnexions spontanées (environ 2 en 3 minutes le 22 octobre, reconnexion en 4 s environ).
- [ ] Images par seconde de Godot, à relever quand le décor sera chargé (lot E1).
- [ ] ERG (lot F) : un `.zwo` standard exécuté en entier sur le HomeTrainer, cibles tenues (critère 11 du lot F). Débloqué par le lot J1 (24 octobre) : `scripts/openride-dev.sh --trainer ftms --input click --autostart --workout sweet_spot_3x10`, après `python -m openride_core.tools.workouts install`.

---

## 4. Ce qui reste à faire

Les travaux confiables à une autre IA sont décrits dans [`docs/lots/`](lots/00_INDEX.md). Les lots H1 à H8 et I1 à I6 ont tous été livrés et fusionnés le 23 octobre (tests de cohérence documentation/code, catalogue de parcours, couches OSM bâtiments/végétation/points d'intérêt/eau, chargeur de thèmes GDScript et logique ERG Godot testée sans écran). Série J (audit J du 23 octobre au soir) : J1 (parcours et entraînement au lancement, `run --autostart --route ID --workout ID`, 24 octobre), J2 (robustesse IPC), J3 (configuration validée), J6 (catalogue unique), J7 (cohérence de la documentation) et J8 (bout en bout sans écran) faits directement, J4 et J5 en partie ; restent à confier la fin de J4 et J5. Série L (24 octobre) : les huit lots délégables L1 à L8 ont tous été livrés et fusionnés le 24 octobre (maillage bâtiments/eau, paramètres de rendu du thème, préréglages de qualité, modèle sonore, cible ERG au journal, historique des séances, raccourci de bureau). Chaque lot ouvert a son issue GitHub, regroupée dans l'issue de suivi [#48](https://github.com/Holeinthesock67/lolo_python/issues/48) (procédure : [`docs/lots/00_INDEX.md`](lots/00_INDEX.md) §5).


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
- [ ] Ruban de route et terrain par tronçons (lot E1 fusionné le 24 octobre, PR #7, tests sans écran verts) : reste l'essai sur la GTX 1060 (images par seconde, à-coups, trous).
- [ ] Shader triplanaire et thèmes (E2, après le chargeur de thèmes GDScript du lot I5), arbres, HUD final avec profil d'altitude (E3).

### Lanceur et menus (lot G, à rédiger)
- [x] Lanceur unique `openride` (`launcher.py`, lot K6) et raccourci de bureau (`scripts/desktop/openride.desktop.in`, `scripts/desktop/openride.svg`, `scripts/install-desktop.sh`, lot L8).
- [ ] Améliorer la journalisation du lanceur sans terminal (`Terminal=false`) : rediriger la sortie de `launcher.py` et de Godot vers un journal (signalé lors du lot L8).
- [ ] Supervision : relance du core ou de l'engine sans perdre la séance.
- [ ] Menu piloté au Click et au clavier (parcours, démarrage, pause, fin), à la place de `--autostart`. Le contrat IPC devra gagner des messages pour lister parcours et entraînements.
- [ ] Écran d'état des appareils (trainer, Click, batterie du Click).

### Sprint 4 et suivants
- [x] Entraînements ERG `.zwo` (lot F, fusionné le 23 octobre ; essai sur le HomeTrainer à faire).
- [x] Couches OpenStreetMap côté compilateur (lots I3 bâtiments et végétation, I4 points d'intérêt et eau) ; reste le rendu dans l'engine (à rédiger).
- [ ] Thèmes avec packs de textures.
