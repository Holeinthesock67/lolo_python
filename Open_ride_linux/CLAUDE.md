# OpenRide Linux – consignes pour Claude Code

Simulateur de cyclisme indoor 3D à usage personnel, natif Linux, plus léger que Zwift.
Propriétaire : Holeinthesock67 (francophone). **Réponds toujours en français**, de façon concise.

## Matériel et machine cible

- **Matériel :**
  - home trainer HomeTrainer (FTMS), annoncé en Bluetooth sous le nom « HomeTrainer 0000 » ;
  - Zwift Cog ;
  - Zwift Click V2, paire de boîtiers : gauche `C1:1C:00:00:00:01` (−, flèches), droit `C1:1C:00:00:00:03` (+, A, B, Y, Z), messages de type `0x23` (table `KEYPAD_BITS`). Le gauche est bridé une minute après la connexion sans passage récent par l'appli Zwift : B du droit fait aussi « − ».
- **PC cible :** PC de bureau MSI (`pc-cible`), Ubuntu, GTX 1060, Python 3.14, Godot 4.7 dans `~/Applications/godot/`.
  - Utilisateur `utilisateur` ; dépôt dans `/home/utilisateur/Games/lolo_python`.
  - Un lien `~/Games/Open_ride_linux` pointe vers le dossier du projet.
- **Dépôt GitHub :** `Holeinthesock67/lolo_python`. C'est un dépôt commun à d'autres projets : **ne jamais modifier quoi que ce soit hors de `Open_ride_linux/`**.

## Documents qui font loi (à lire avant de coder)

- `docs/SRS_v1.1.md` : spécification.
- `docs/GUIDE_UTILISATION.md` : guide d'utilisation sans terminal (installation, appairage, parcours, ERG, commandes du Click et du clavier, dépannage) ; ses raccourcis sont vérifiés par `core/tests/test_docs_coherence.py`, à mettre à jour avec toute commande modifiée.
- `docs/contracts/ipc_v1.md` et schémas `docs/contracts/ipc/*.schema.json` : messages core ↔ engine.
- `docs/contracts/world_format_v1.md` et `docs/contracts/world/` : format des parcours `.world`, schémas et vecteurs de test de la route.
- `docs/SUIVI_AVANCEMENT.md` : état, tests faits, reste à faire.
- `docs/lots/00_INDEX.md` : règles communes des lots de travail (cahiers des charges autonomes) ; le tableau des lots et de leur statut se calcule avec `python3 scripts/index_lots.py` (lot X54) ; les séries H, I, J et K sont faites pour être confiées à une autre IA.
- `docs/AUDIT_2026-10-23.md` : audit et suivi des constats (complété le soir du 23 octobre, §8 et §9).
- `docs/VERIFICATION_2026-10-24.md`, `docs/AUDIT_FTMS_2026-10-24.md`, `docs/REVUE_CODE_2026-10-24.md` : vérification, audit FTMS et revue de code du 24 octobre (constats ouverts : §5 de la revue).
- `docs/spikes.md` : faits mesurés sur le matériel.
- `docs/OUTILS_DE_TEST.md` : liste des outils de test (suites, matériel simulé, banc d'essai simulé, parcours d'essai, diagnostic).
- `docs/PLAN_DE_TESTS.md` : plan de tests (niveaux, périmètre, scénarios, lancement, résultat attendu, lieu : CI, PC ou vélo), tests des changements récents, PR en revue, mesures de performance et écriture d'un nouveau test.

**Règle :** un contrat ne se modifie que par ajout compatible, avec une ligne au journal des changements du document. Si un contrat paraît faux, le signaler au lieu de l'interpréter.

## Architecture

Trois programmes. Le core est le maître : il détient l'état de la séance, et l'engine n'affiche que ce qu'il reçoit.

| Dossier | Programme | Rôle |
| --- | --- | --- |
| `core/` | `openride-core` (Python, asyncio, bleak) | BLE (HomeTrainer, Click), physique à 50 Hz, braquets, journal, FIT, serveur IPC UDP (état à 30 Hz sur le port 5005, commandes sur le port 5006) |
| `compiler/` | `openride-compiler` (Python, numpy, scipy, pyproj, rasterio) | GPX vers dossier `.world` : couche route, couche terrain (MNT Copernicus GLO-30 mis en cache dans `~/.cache/openride/dem/`) et couche biome (ESA WorldCover 2021 en cache dans `~/.cache/openride/landcover/`, lot U2) |
| `engine/` | Godot 4.7 (GDScript) | Rendu, HUD, caméra interpolée et extrapolée, bips des appuis |

**Modules clés du core** (`core/src/openride_core/`) :
- `session.py` : boucle principale ; `jitter.py` : gigue de la boucle à 50 Hz et des trames `state` (lot X17, ligne `Gigue` par minute) ;
- `launcher.py`, `launch_compile.py` : lanceur unique `openride` (core + Godot, compilation au lancement des traces GPX, relance de Godot s'il plante, relance du core avec reprise de la séance en pause s'il plante (lot N8, `resume.py`, qui liste aussi les séances interrompues d'un lancement précédent, lot O34), arrêt propre sur fermeture et signaux ; un journal par lancement dans `~/OpenRide/Logs/`, lien `~/run_trainer.log` vers le dernier, lots M8 et N11) ;
- `ftms_driver.py` : pilote du HomeTrainer ; `brake_watch.py` : frein lâché, règle unique du pilote et du rapport des décrochages (lot FR1, module pur : chute, puis pédales qui tournent encore 2 s, la cadence annoncée étant en retard d'environ 1 s) ;
- `input_providers.py` : Click et clavier ;
- `ble_util.py` : verrou BLE, repli BlueZ ;
- `recorder.py` : journal, mémoire, FIT ;
- `route.py`, `catalog.py` : lecture des `.world`, interpolation et catalogue des parcours (`.world` et `.gpx`) ;
- `route_stats.py` : fiches des parcours (dénivelé, montée principale, durée, difficulté, fiche `.toml`), tri et filtres du catalogue (lot O15) ; copie exacte dans le compilateur ;
- `demo_world.py` : parcours de démonstration (`demo`, « Col du lacet » au menu) ; ceux des biomes viennent du compilateur (`openride_compiler.demo_biomes`, lot O37 : noms de parcours du jeu de base, variante `--recette` aux noms techniques pour les bancs) ;
- `synthetic_terrain.py` : couche terrain synthétique (démonstration et parcours d'essai) ; `road_ground.py` : règle unique sol / route (21 novembre), jumelle en bibliothèque standard de celle du compilateur : route telle que l'engine la dessine, sol sous la chaussée, talus appuyés ;
- `synthetic_biome.py` : couche biome synthétique du « Col du lacet » (forêt tempérée loin de la route, alpages `alpine`) ;
- `workout.py`, `workout_formats.py` : lecture des `.zwo`, des `.erg` et `.mrc` de GoldenCheetah (lot O9) et contrôleur ERG ; `workout_menu.py` : entraînements créés depuis le menu ERG, écrits par le core seul (sous-menu ERG, décision D4 de l'audit IPC ; import de fichiers retiré le 12 novembre, révision 1.15) ;
- `start_gate.py` : départ au pédalage (lot O36), module pur : après `start`, la séance attend en `READY` le décor du départ (commande `scene_ready` de l'engine, au plus `[depart] attente_decor_s`), le trainer, puis `[depart] duree_s` secondes à `[depart] cadence_rpm` tr/min ; objet `start_wait` de `state` ; `[depart] mode = "immediat"` ou `run --depart immediat` part tout de suite ;
- `warmup.py` : échauffement sur place en ERG avant une course (lot EL1, module pur) : une règle pour tous les modes de course (`RACE_MODES`, épreuves de piste sauf la séance libre), profil en watts (montée, palier, deux accélérations) passé par `ErgController`, étape `echauffement` de `start_gate.py`, Z court ou `skip_warmup` pour passer, réglage `[depart] echauffement_min` ;
- `seance_file.py` : séance verrouillée au lancement (lot EP1, essais physiques) : liste de commandes du menu (`select_route`, `start_run`, `start`…) lue dans `run --autostart --seance FICHIER` ou tirée de `--route`, `--workout` et `--mode`, jouée par `CoreSession._play_autostart` ; un refus arrête le core ;
- `route_import.py` : traces importées depuis le menu des parcours (lot O23) : traces des dossiers habituels, copie dans `~/OpenRide/GPX/` sans écrasement, puis `openride-compiler build` de cette trace dans un processus à part, sans relancer (commandes `list_route_imports` et `import_route`) ;
- `free_erg.py` : ERG d'une session libre choisi sur l'écran de pause (commande `set_ride_mode`, lot O18) : cible constante (`FreeErg`) ou cadence verrouillée dans une plage de ± 15 % (`CadenceLock`, puissance adaptée progressivement), module pur ;
- `mock_driver.py`, `replay.py` : simulateur de trainer et rejeu d'une séance enregistrée (`.jsonl` ou `.fit`) ;
- `ble_sim.py`, `sim_scenarios.py`, `sim_rider.py` : Bluetooth simulé (HomeTrainer, paire de Click, ceinture) derrière les vrais pilotes, cycliste virtuel et ses stratégies (lot X27), scénarios de pannes (`docs/SIMULATION_BLE.md`) ;
- `hr_monitor.py` : ceinture cardio Bluetooth facultative (service 0x180D) ;
- `journal.py`, `fit_export.py`, `ipc_server.py`, `ipc_lists.py`, `ipc_budget.py`, `config.py`, `config_edit.py`, `config_repair.py`, `pairing.py`, `settings.py` : journal JSONL, export FIT (totaux des tours et de la séance affichés par Garmin Connect et GoldenCheetah, lot X56), serveur IPC (messages non conformes ignorés et comptés), découpage des listes IPC v1.1, budget de taille des trames et allègement d'une trame `state` trop grande (lot X25), configuration (types et bornes contrôlés, `ConfigError`), modification ciblée de `config.toml` qui garde les commentaires, valeur invalide remise par défaut depuis une fenêtre du lanceur (lot O34), appairage (lots N12 et N14) et réglages du menu (lots O3 et O4) ;
- `latency_log.py` : journal de latence des appuis du Click, de la notification BLE au Control Point (lignes `[latence]`, `--latence` ou `[log] latence`, lot X7) ;
- `tools/` : `route_vectors.py` (vecteurs de route), `log_report.py` (analyse de `~/run_trainer.log`, `--gigue`), `gigue_charge.py` (gigue de la boucle sous charge, lot X17), `workouts.py` (entraînements `.zwo`), `session_summary.py` (bilan de séance), `fit_check.py` (contrôle local d'un FIT réel, lot X11), `history.py` (historique des séances et cumul hebdomadaire), `xp.py` (progression recalculée, lot V2), `collection.py` (cartes gagnées et à gagner, série BC, lot BC1), `estimate_cp.py` (CP et W' estimés depuis les séances passées, lot R16), `power_curve.py` (courbe de puissance du profil : 13 durées, 6 mois et 6 semaines, libre ou ERG, fenêtres jamais à cheval sur une pause, cache commun avec `estimate_cp`, série PP, lot PP1), `ftp_estimate.py` (FTP estimée du profil, source et confiance en mots, proposée sans jamais l'écrire seule, `--accept W`, lot PP2), `rogue_sim.py` (runs Cyber-Rogue simulées et rapport d'équilibrage, lot R7), `bots_race.py` (course des bots en temps accéléré, lot X27), `elo_campagne.py` (campagnes de Grand Prix simulées : la cote Elo suit la force du cycliste, lot BOT-elo), `campagne_profil.py` (campagne simulée accélérée sur le profil d'essai et empreinte du vrai profil, lot MJ3), `ble_diag.py`, `fake_world.py`, `fit_demo.py`, `run_mock_session.py`, `seance_guidee.py` (séances guidées sur le HomeTrainer : parcours, consignes et entraînement d'essai), `essai_physique.py` (essais physiques de la série EP : fiches `data/essais/*.toml`, jeu verrouillé, étapes déclenchées par le journal de séance, lot EP2), `gp_recette.py` (bilan des courses du Grand Prix des objets lu dans les journaux du profil, lot GP11) ;
- `physics.py`, `gearing.py`, `ftms.py`, `zwift_click.py` : modules purs, sans entrées-sorties ;
- `open_world.py`, `live_route.py`, `worldgen_client.py` : séance en monde ouvert (lot W9, 2.0) : `OpenWorld` pilote le générateur (`openride-worldgen`, dialogue en lignes JSON de `docs/contracts/worldgen_v1.md`), construit le champ `open_world` de `state` et applique les choix aux carrefours (Click ou `choose_branch`) jusqu'au verrouillage ; `LiveRoute` lit la route engagée par parties de 1 km dans un fil et la remplace d'un coup, la boucle à 50 Hz ne lit jamais le disque ; pause `world_data` quand la route connue ne suffit plus ;
- `contents.py` : contenus installables depuis « Réglages › Contenus » (lot O25, contrat IPC révision 1.5, `list_contents`, `install_content`, message `contents`) : contenus de départ (entraînements livrés, deux plans, « Tour des nouveaux paysages », lot DB1, « Route des Érables », biome Japon, lot DJ1, circuit en boucle « Circuit des Prés », lot O38, récif « Récif des tortues », lot SM1, boucle « Volcan en flammes », lot DB2, « Route du Sud » et boucle « Route du Grand Nord », lot DB3, « Route des Trois Forêts », lot V6-r4, « Boucle de la Corniche » et « Route des Vignes », parcours du Grand Prix, lot GP13b), installés sans rien écraser, une installation à la fois dans un fil, seuls au premier lancement (`run --first-run`) ; lot O29 : pack « Cols célèbres » (construit et compilé par le compilateur en sous-processus), archives `.zip` de thèmes, de biomes et de parcours trouvées dans Téléchargements, thèmes installés et place disque ; lot PK1 : pack des cols livré dans le paquet (`pack_bundle.py`, dossier `paquet/` hors git ou `OPENRIDE_PAQUET`, construit par `scripts/build_pack_base.sh`), installé sans réseau avec les contenus de départ ;
- `world_menu.py` : menu du monde ouvert (lot W11, 2.0) : réponses aux commandes `world_search` (liste embarquée `data/places.json`, puis bases locales, puis Nominatim si `[open_world] network`, à la demande et une requête par seconde au plus), `world_map`, `world_regions` et `world_pin` ; les requêtes sur les bases locales passent par `python -m openride_compiler.worldgen.menu_query` (sous-processus, le core ne dépend pas du compilateur) ; réponses en parties de 60 000 octets (`ipc_lists.build_world_messages`) ;
- `open_world_segments.py` : montées et sprints du monde ouvert repérés en roulant sur la route connue (règles de `segments.py`), retenus une fois finis, retirés si un choix de branche déplace la route, records communs sous `ow` et identifiants stables d'une balade à l'autre (`segments_monde_ouvert.json` du profil, lot W20) ;
- `open_world_save.py` : balade du monde ouvert enregistrée en GPX dans `~/OpenRide/GPX/` à la fin d'une séance de plus de 500 m, et commande `openride-core open-world-save <id>` (lot W14) ;
- `privacy_zone.py` : zone privée au départ (lot PZ1, réglage `privacy.hide_start`, coupé par défaut, module pur) : aucune position à moins de 500 m du départ dans les FIT (`mask_records`, totaux inchangés) et dans le GPX du monde ouvert (début et fin coupés, `trim_points`) ;
- `bots.py` : bots à puissance constante et fantôme d'une séance passée (.fit ou .jsonl) (lot N9) ; bots changés sur l'écran de pause (`merge_menu_bots`, commande `set_bots`, ligne `bots` du journal, lot N18) ;
- `bot_effort.py` : effort visé par les bots (lot BT1, module pur) : FTP × courbe de puissance sur la durée estimée de la course × objectif (`bots.objective`, Tempo par défaut) × niveau ; vélodrome par épreuve (`TRACK_EFFORT`) ;
- `bot_elo.py` : cote Elo du cycliste et des bots (lot BOT-elo, module pur hors `elo.json` du profil, à côté des records) : Elo à plusieurs après chaque course à classement (Grand Prix, Course, Dernier survivant, piste en groupe), identité d'un bot = profil et rang, niveau des plateaux composés × (1 + (cote du bot − 1 500) / 4 000), réglage `bots.elo` ; effort des bots en watts avant le départ : commande `bots_preview` (lot GP-niv, révision 1.22) ;
- `rivals.py` : rivaux reconnaissables (lot R4, module pur hors `rivaux.json` du profil) : un nom fictif, une équipe (nom écrit et couleur), un caractère et un tempérament fixes par identité Elo (`climber#1`), pour tous les bots à profil de tous les modes ; la ligue d'hiver les reprend et en change 3 par saison (`Roster.renew`) ;
- `bot_tactics.py` : tactique des bots à profil (lot Y10) : relais, attaques, réponses aux départs, fatigue de longue durée et forme du jour, comportements choisis par mode dans une table (prolongée par le vélodrome, lot VD7) ;
- `bot_tactics.py` : tactique des bots à profil (lot Y10) : relais, attaques, réponses aux départs, fatigue de longue durée et forme du jour, comportements choisis par mode dans une table (prolongée par le vélodrome, lot VD7, puis par le Grand Prix et le Dernier survivant, lot BR5 : gestes de base derrière ce qui est propre au mode, `ProfileBot.mode_speaks`) ;
- `traffic.py` : circulation de la route calculée par le core (lot AS6, 2.0, module pur) : portage de `traffic_model.gd` (même tirage, vecteurs partagés `engine/tests/data/traffic_slots_vectors.json`, `tools/traffic_vectors.py`), véhicule lent devant, abri derrière un véhicule et aspiration au dépassement, liste `vehicles` de `state` ;
- `progression.py` : expérience, niveaux et défis de la série V recalculés depuis le journal, tables dans `data/progression.toml` (lot V2) ;
- `league.py` : ligue d'hiver (série CH, lot CH1, plan `docs/6.0/PLAN_SERIE_CH.md`, module pur) : saison de 8 manches (une par semaine ISO, modes existants à tour de rôle, Cyber-Rogue exclu), 11 rivaux fixes aux identités de la cote Elo (`climber#1`…), barème 25 à 4, 6 meilleurs résultats, classique × 1,5 à date choisie, une seule tentative par manche, semaines non courues simulées pour les rivaux, pause de 4 semaines au plus, trophées ; saison dans `ligue.json` du profil, écriture sûre ; dureté (lot CH2) : rivaux étalés de 150 points et décalés manche par manche pour 10 % de chances de victoire (`round_ratings`), cote du cycliste tenue contre ces cotes (`rider_update`), banc `tools/ligue_campagne.py` ; manche de la semaine lancée par la séance (lot CH3, révision 1.30 : `league_status`, `league_new`, `start.league`, `summary.league`, `ligue.json` et `elo.json` du profil à l'arrivée) ;
- `collection.py` : cartes à collectionner de la série BC (lot BC1, 5.0, module pur) : catalogue `data/collection.toml` (accomplissements, saisons par année, anniversaires), cartes recalculées depuis les séances comptées par `progression.recompute`, cartes déjà montrées dans `collection_vue.json` du profil, annonce d'une seule carte nouvelle ;
- `profile.py` : profil local `~/OpenRide/profile.json` (équipement choisi, achats, vies, avatar), écriture sûre et migration (lot V4) ;
- `last_choices.py` : derniers choix du menu par profil (`derniers_choix.json` : parcours, entraînement, bots, départ du monde ouvert), publiés dans `hello_ack.config.last_choices` ; dernier parcours rechargé par le core (lot O32) ;
- `mode_routes.py` : parcours propres à un mode (lot GP13, module pur) : table unique mode → étiquette de la fiche (`track` → `velodrome`, `grandprix` → `grandprix`), publiée dans `hello_ack.config.mode_routes` ; un parcours de mode est une boucle étiquetée (lot GPL1) et n'est que dans ce mode (liste générale sans lui, dernier parcours du mode dans `last_choices.mode_routes`, séance conseillée sur les parcours libres), sauf avec l'étiquette `libre` (`FREE_TAG`, `hello_ack.config.free_route_tag`, révision 1.24) : dans son mode et dans la liste générale (Récif, Volcan, Grand Nord au Grand Prix) ;
- `profiles.py` : profils de joueurs (série MJ, lot MJ1) : `ProfileContext` (dossiers du joueur en cours : profil V4, records, plan actif, séances et journaux, caches), `current()` lu à l'appel par tous les modules, `--profil ID` sur toutes les sous-commandes et `OPENRIDE_PROFIL`, verrou `.verrou` d'une séance par profil ; sans profil, les chemins de `~/OpenRide/` d'avant ; configuration à deux couches (lot MJ4) : `config.load()` pose les clés joueur de `profil.toml` (`config.PROFILE_KEYS`) sur `config.toml` ; `config_edit.update_layers` écrit chaque clé dans le fichier de sa portée (`settings.Setting.scope`) ; réglages retirés du menu remis par défaut dans les fichiers du joueur au lancement (`migration_reglages.py`, lot NI2) ; migration du joueur d'avant les profils vers `Profils/principal/` au lancement (`migration_profils.py`, lot MJ5 : sauvegarde, séances simulées et rejouées vers `_essai`, contrôle de la progression, reprise après coupure), puis `principal` par défaut ; liste, choix sans relancer, création, renommage et corbeille des profils (lot MJ7 : commandes IPC de la révision 1.5, `[profils] dernier`, `.profil_actif` suivi par le lanceur) ; profil d'essai vidé et profil restauré depuis le menu (lot O33) ; statistiques d'un profil de joueur remises à zéro (date de départ `stats_since` lue par `progression.recompute`, séances gardées) avec sauvegarde datée et annulation (`reset_stats`, `undo_reset`, `Profils/.remises_a_zero/`, lot RZ1, révision 1.31) ;
- `equipment.py` : catalogue d'équipement, effets bornés sur `PhysicsParams`, conseil par terrain et temps gagné par l'équipement (lot V3) ;
- `garage.py` : progression branchée dans la séance (profil, équipement appliqué à la physique, commandes du Garage, bilan `xp_result`) (lot V11) ;
- `coins.py` : pièces (gains, solde recalculé, état des pièces, achats, vies du mode Cyber-Rogue) (lot V3b) ;
- `coach.py` : séance conseillée (série CO, lot CO1, plan `docs/5.0/PLAN_SERIE_CO.md`) : besoin du jour (aérobie léger, aérobie intense, anaérobie, récupération, test de FTP) et sa raison, depuis l'historique du profil (répartition sur 4 semaines, CTL/ATL, dernière séance dure, profil de puissance, âge de la FTP), règles RG (suggestion de la montre Garmin) et R0 à R7, seuils dans `data/coach.toml`, commande `openride-core coach` ; entraînements classés par besoin et choisis pour le conseil (lot CO2) ; suggestion de la montre gardée pour la journée dans `conseil.json` du profil (lot CO8)  ; contrat du conseil, commande IPC `get_coach` et prochaine course (lot CO3) ; courses disputées et cause de perte (lot CO6) ;
- `coach_game.py` : séance de jeu calibrée au besoin (série CO, lot CO9) : formats de `[game]` (`data/coach.toml`), parcours du catalogue simulés avec le cycliste virtuel, proposée si 70 % du temps de l'entraînement équivalent est dans les zones du besoin ;
- `segments.py` : détection des montées et des sprints d'un parcours, segments manuels (série T, lot T2, module pur).
- `segment_timing.py` : chronométrage des segments : franchissements interpolés, pauses, boucles, relecture du journal (série T, lot T4, module pur).
- `velodrome.py` : piste du vélodrome (série VD, lots VD2 et VD3, module pur) : `velodrome-250.world` écrit par le core (`openride-core velodromes`), ligne de mesure en droites, clothoïdes et arcs, relèvement continu (colonne `bank_deg`, 12° à 42°), bois (`wood`), couche `venue.json` ; règle de distance R / (R + h cos θ) selon la hauteur sur la piste, air de la salle (`[velodrome]`), vent coupé.
- `rogue/` : mode Cyber-Rogue de la 2.0, modules purs : W'bal de Skiba, postures de cadence avec hystérésis et table des valeurs `RogueBalance` (série R, lot R2), lue dans le fichier embarqué `balance.toml` avec surcharge facultative `~/OpenRide/rogue_balance.toml` (lot R7) ; châssis, statistiques de runs recalculées depuis le journal et vies (lot R9) ;
- `wtf/` : mode « What the fuck » (série WTF, lot WTF1), modules purs : catalogue des treize règles désactivables une à une et fichier `~/OpenRide/wtf.toml`, événements à durée limitée, surprise du chef, chef d'orchestre `WtfMode` qui tire les événements, fait vivre les règles permanentes et combine les effets sous des bornes sûres ;
- `powerups.py` : bonus légèreté, aérodynamique et puissance, arches, valeurs dans `~/OpenRide/powerups.toml` (série T, lot T6, module pur).
- `gaps.py` : écarts en temps de passage avec les bots, voisins devant et derrière (série T, lot T16, module pur) ;
- `records.py` : records personnels par segment dans `~/OpenRide/records.json`, avec et sans bonus, classement local, recalcul depuis les journaux (série T, lot T5, module pur) ;
- `jerseys.py` : points des sprints et des montées, maillots vert et à pois de la séance, bots compris (série T, lot T14, module pur) ;
- `classic.py` : mode classique de la séance, réunit segments, records, bonus et bouton Z, maillots et écarts, et remplit les champs de la révision 1.4 (série T, lot T7) ;
- `survivor.py` : mode « Dernier survivant » (série DS, lot DS1, module pur) : arches d'élimination (une par adversaire, calées sur un sprint ou un sommet proche), passages interpolés, élimination du dernier, égalités, plateau de bots, trame `survivor`, messages `elimination` et bilan ;
- `grandprix/` : mode « Grand Prix des objets » (série GP, lot GP1, modules purs) : catalogue des treize objets décrit par des données (cible, forme, effets) et fichier `~/OpenRide/grandprix.toml` borné, effets sur la vitesse virtuelle seulement, tous à durée depuis le lot GPO1 (plancher, plafond, invincibilité, vent virtuel ; table de réglage en tête du catalogue des objets), rangées de boîtes de famille par voie (gauche s'aider, centre tout, droite attaquer), tirage selon le retard sur le premier, `GrandPrixMode` (voies, projectiles, contacts, trame `gp`, messages `gp_hit`, bilan) ; aucune pente envoyée ne dépend des objets ; la même course sans objet est le mode « Course » de l'accueil (`mode` = `race`, réglages `[race]`, tous les parcours libres, mode classique gardé, lot CR1) ;
- `route_objects.py` : objets sur la route, génériques (lot GP1, module pur) : objets posés et projectiles repérés par `s` et une voie, durée de vie, portée, cible suivie, contacts balayés pendant le pas, 32 objets au plus ;
- `plans.py` : plans d'entraînement sur plusieurs semaines (`~/OpenRide/Plans/`, plan actif, séance du jour, suivi d'après l'historique, import d'un dossier, plan maison composé dans le menu par `create_from_library` (lot O30) ; `openride-core plan`, format `docs/contracts/plan_format_v1.md`, lot O11).
- `ftp_test.py` : test de FTP par rampe (entraînement `ftp_test:ramp`, le test de 20 min est retiré au lot O19, fin de la rampe, FTP proposée, ligne `ftp_test` du journal, `openride-core ftp-test`, lot O10).
- `surface_physics.py` : option « gravel », roulement multiplié des routes non revêtues (`[gravel]`, colonne `surface` du parcours ou surface imposée), supplément de pente en SIM sous la borne du vent, transition de 20 m, module pur (lot U21).
- `wind.py` : vent réglable (calme, fixe, en rafales, du thème ou météo du jour), composante de face et supplément de pente en SIM, module pur (lot P2).
- `local_weather.py` : vent de la météo du jour (lot P33) : le lanceur le lit chez Open-Meteo (délai 5 s, positions arrondies à 0,1°) dans un cache de 3 h que le core lit sans réseau ; repli sans vent.
- `draft.py` : aspiration derrière les bots (courbe exponentielle, effet de file, vent de travers, poussée du bot suivi), module pur (lot P3).
- `road_cyclists.py` : cyclistes du décor proches calculés par le core (portage de `road_cyclists_model.gd`, même graine), sources d'abri `rider:<id>` et liste `riders` de `state`, module pur (lot AS7).
- `road_space.py` : règle unique de la chaussée (lot AS11) : registre de tous les usagers de la route (cycliste, voitures d'équipe, bots, véhicules, cyclistes du décor) et garde finale qui écarte tout chevauchement par ordre de priorité, module pur ; règle commune de dépassement `draft.pass_window` (engine : `engine/scripts/road_rules.gd`).
- `route_mirror.py` : parcours lu à rebours (u = L − s, cap + 180°, pente opposée), jumeau de `route_mirror.gd` : circulation et cyclistes du décor y roulent après un demi-tour (lot N23), module pur.

**Modules clés du compilateur** (`compiler/src/openride_compiler/`) : `cli.py`, `gpx.py`, `pipeline.py` (route), `elevation.py` et `cache.py` (MNT et cache), `terrain.py`, `landcover.py` (WorldCover lu par fenêtres, cache par carré de 0,1°, lot U2), `biomes.py` (classification des biomes, numpy sans entrée-sortie, lot U2), `regional.py` et `data/regional_variants.toml` (variante régionale par tuile, table à grosse maille, lot U4 ; paysages canyons, fjords, îles volcaniques et rizières, lot U25), `osm.py` et `osm_layers.py` (client Overpass et couches `buildings`, `vegetation`, `poi`, `water`), `frame.py` (repère), `segments_layer.py` (couche `segments` et fichier `<trace>.segments.toml`, série T, lot T3), `river_surface.py` (grandes rivières en surface : découpe par carré de 1 km, niveau qui descend le long du cours, lot EA3), `road_ground.py` (règle unique sol / route, 21 novembre : route exacte de l'engine en Catmull-Rom, sol au moins 5 cm sous la chaussée et les bas-côtés, pied des talus appuyé ; parcours compilés, carrés du monde ouvert, jumelle du core pour les démonstrations), `worldgen/altitude_guard.py` (garde-fou d'altitude du monde ouvert, 21 novembre : trous et pics du relief réparés, profil des arêtes sous ± 15 % de pente et 4 % de changement de pente par 10 m, pente des nœuds), `worldgen/session_ground` (tuiles proches de la balade du monde ouvert réglées sur la route engagée, même règle, 21 novembre), `bridges.py` (couche `bridges`, ponts dessinés, profil en ligne droite et terrain non fondu sous un pont, parcours compilés et monde ouvert, lot EA4), `writer.py`, `verify.py`, `theme.py` (validation des thèmes).

## Commandes

```bash
# Environnement du core (une fois)
cd core && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
# Compilateur, dans le même environnement
cd compiler && pip install -e ".[dev]" -e ../core   # sans ../core, les tests qui lisent le core sont sautés (erreur si CI est défini)

# Tests (tous doivent passer avant chaque commit ; l'intégration continue GitHub Actions les relance à chaque envoi)
(cd core && pytest -q)                 # ~3 min ; `pytest -q -m "not slow"` (~20 s) pendant le développement
(cd compiler && pytest -q)            # réseau coupé ; `pytest -m network` pour l'essai Copernicus réel
GODOT=~/Applications/godot/Godot_v4.7.2-stable_linux.x86_64 engine/tests/run_engine_tests.sh
GODOT=~/Applications/godot/Godot_v4.7.2-stable_linux.x86_64 engine/tests/run_e2e.sh   # vrai core + vrai engine, ~10 s
GODOT=~/Applications/godot/Godot_v4.7.2-stable_linux.x86_64 engine/tests/run_visual_tests.sh --open   # tests graphiques (Xvfb, captures analysées, références, rapport HTML), ~2 min
scripts/bump-version.sh X.Y.Z   # change le numéro unique (VERSION, pyproject, project.godot, CHANGELOG.md), lot O2
python3 engine/tests/sim_bench.py --scenario coupures_village [--native]   # banc simulé : vrai core sur BLE simulé + vrai engine, captures et rapport (docs/OUTILS_DE_TEST.md)
python3 scripts/file_bancs.py lancer|relancer|etat FILE.toml   # file des bancs du PC en étapes courtes avec reprise, cache séparé par PR (docs/OUTILS_DE_TEST.md)
python3 scripts/file_bancs.py verifier|importer|categorie …     # paquets de 2 à 4 PR, matrice rendu/logique, étapes cloud (--lieu cloud), section « Recette PC »

# Séance (depuis Open_ride_linux/) : core en arrière-plan + fenêtre Godot ; journal dans ~/run_trainer.log
scripts/openride-dev.sh --trainer ftms --input click --gear 6 --autostart
scripts/openride-dev.sh --trainer mock --input keyboard --autostart        # sans vélo
scripts/openride-dev.sh --trainer sim --input sim --hr sim --autostart     # sans matériel, vrais pilotes BLE (scénario demo)
scripts/openride-dev.sh --trainer sim --input sim --hr sim --sim-scenario coupures --autostart   # pannes rejouées
scripts/openride-dev.sh --trainer ftms --input click --autostart --workout sweet_spot_3x10   # ERG (~/OpenRide/Workouts/<ID>.zwo)
scripts/openride-dev.sh --trainer ftms --input click --autostart --route <parcours>          # parcours compilé (défaut : demo)
openride --trainer mock --input keyboard --autostart                       # même chose en Python, avec relance de Godot (lot K6)
openride --compile-only                                                   # compile les traces GPX nouvelles/modifiées puis quitte (lot N11)
openride --no-compile                                                     # lance la séance sans compiler les traces GPX (lot N11)
openride-core run --replay ~/OpenRide/Activities/<séance>.fit --input keyboard --autostart   # rejoue une séance réelle
openride-core run --bot 200 --ghost ~/OpenRide/Activities/<séance>.fit --autostart   # bots virtuels (lot N9)
openride-core run --bot-profile climber --bot-profile sprinter --autostart          # bots à profil (lot T12)

# Après un essai (depuis core/) : résumé du journal (Perf, pertes trainer et Click, pauses)
python -m openride_core.tools.log_report ~/run_trainer.log

# Entraînements ERG
python -m openride_core.tools.workouts install | list | check FICHIER.zwo --ftp 250

# Parcours
openride-compiler build trace.gpx      # route + terrain + biome + segments ; puis : verify / info
openride-compiler build trace.gpx --biome mediterranean   # impose un biome à tout le parcours (lot U2)
openride-compiler build trace.gpx --variant basalte,ardoise   # impose la variante régionale de toutes les tuiles (lot U4) ; 3e membre facultatif : paysage (gres_rose,,canyon, lot U25)
openride-compiler list                 # liste les parcours (.world et .gpx) et leur statut
openride-compiler build-all            # compile toutes les traces GPX nouvelles ou modifiées (route,terrain,biome,segments ; --layers pour OSM)
openride-compiler build trace.gpx --offline --force   # sans réseau, tuiles d'altitude et WorldCover déjà en cache
openride-compiler build trace.gpx --layers route,terrain,buildings,vegetation,poi,water,coast,roads,bridges   # bridges : ponts dessinés (lot EA4)
openride-compiler add-layer <nom>.world terrain|biome|buildings|vegetation|poi|water|coast|roads|bridges|segments  # régénère une couche seule
openride-compiler theme-check ~/OpenRide/Themes/<nom>  # contrôle un thème (défaut : engine/themes/default/)
openride-compiler theme-list          # liste les thèmes installés et intégrés ; --json
openride-compiler theme-install SOURCE # installe un thème depuis un dossier ou .zip ; --force
openride-compiler theme-pack DOSSIER --levels 512,1024,2048   # niveaux de textures d'un pack (lot P20, Pillow) ; --fix-seams
openride-core recover                  # FIT depuis le dernier journal après un plantage
openride-core release-trainer          # libère le trainer resté réservé après un arrêt brutal
openride-core summary --ftp 250        # bilan du dernier journal (ou d'un .jsonl/.fit) : NP, IF, TSS, zones ; --json
openride-core session-report           # analyse du dernier journal (lot X12) : ~/OpenRide/rapports/<séance>/rapport.html ; --log, --engine-log
openride-core fit-check SEANCE.fit --journal JOURNAL.jsonl   # contrôle local d'un FIT réel (SDK Garmin) avant import ; --json
openride-core history --weeks 8        # historique des séances et cumul par semaine ISO ; --json ; au menu : « Historique » (lot O28, mêmes calculs)

# Diagnostic matériel
openride-core devices                  # appareils classés (trainer, Click, ceinture) et bloc [drivers] à recopier ; --json ; --save : écrit dans ~/OpenRide/config.toml (pairing.py, lot N12)
openride-core profil list [--json]    # profils de joueurs ; profil create NOM | rename ID NOM | delete ID (corbeille) (profiles.py, lot MJ7)
openride-core settings [--json]        # réglages du menu (FTP, poids, difficulté, braquet, qualité, thème) ; settings set CLÉ VALEUR écrit ~/OpenRide/config.toml, ou le profil.toml du profil en cours pour un réglage du joueur (settings.py, lots O3, O4 et MJ4)
openride-core ftp-test [--accept] [--history]   # résultat du dernier test de FTP, enregistrement de la FTP (lot O10)
openride-core profil remise-a-zero | remises | annuler-remise SAUVEGARDE   # statistiques du profil en cours remises à zéro, sauvegarde datée, annulation (lot RZ1)
openride-core profil essai [--vider]   # profil d'essai : séances simulées comptées, remise à zéro (série MJ, lot MJ2) ; --profil ID sur toute sous-commande
openride-ble-diag scan | trainer --name HomeTrainer --duration 30 | click --duration 60
openride-ble-diag spindown --duration 90   # sonde d'étalonnage FTMS (Spin Down Control 0x13, lot ET1, tools/spindown.py) ; rapport sans nom ni adresse
```

Dépendances : versions de référence validées en 3.14 dans `constraints.txt` (`pip install -c ../constraints.txt -e ".[dev]"`), à mettre à jour après une montée de version testée.

Vecteurs de route : après toute modification de `route.py`, lancer `python -m openride_core.tools.route_vectors` pour les régénérer, puis `--check` pour vérifier qu'ils sont à jour.

## Conventions

- **Langue :** commentaires, docstrings, messages de journal et documentation en français ; identifiants en anglais.
- **Python :** 3.11 minimum, et le code doit tourner en 3.14. Aucune entrée-sortie bloquante dans la boucle du core. Le matériel s'isole derrière des interfaces (`MockDriver` et `FtmsDriver` s'échangent).
- **Fichiers embarqués des paquets (lot J4) :** les paquets lisent leurs données dans leur dossier `data/` (`Path(__file__).parent / "data"`), pour marcher installés hors du dépôt ; `theme.schema.json` et le `theme.json` par défaut y sont **copiés** (les originaux restent la référence) : après un changement d'un original, recopier (la commande est dans le message de `compiler/tests/test_packaging.py`, qui compare octet pour octet). Les entraînements et plans de référence n'existent qu'une fois, dans `core/src/openride_core/data/workouts/` et `data/plans/` (plus de `core/workouts/` ni `core/plans/`, audit du 22/11).
- **GDScript :** jamais de `class_name` dans les scripts chargés par la scène principale. L'engine est lancé sans passer par l'éditeur, et Godot ne connaît alors pas les `class_name` : utiliser `preload`.
  - Les fonctions globales de Godot masquent les méthodes de même nom : `route_data.gd` utilise `wrap_s`, et non `wrap`.
  - Référence de l'API : en cas de doute sur une classe, une méthode ou une propriété, consulter la référence générée par le binaire utilisé (4.7.2, celui de la CI et du PC) plutôt que la mémoire ou la documentation en ligne d'une autre version : `$GODOT --headless --doctool /tmp/godot-doc` (quelques secondes, 1 076 classes), puis `grep` dans `/tmp/godot-doc/doc/classes/*.xml` (hors du dépôt, rien à ajouter à Git). Pas de serveur MCP ni d'addon d'éditeur : l'engine se construit par le code et se teste en ligne de commande.
- **Tests :**
  - chaque correction ou fonction a son test ;
  - le matériel se simule avec les doublures de `core/tests/test_drivers_session.py` (`FakeClient`, `fake_finder`) et `MockDriver` ;
  - les tests de session passent `routes_root=tmp_path / "routes"` et redirigent `fit_export.ACTIVITIES_DIR`, pour ne jamais écrire dans le vrai dossier personnel.
  - pytest tourne avec un HOME temporaire, des fenêtres de bureau muettes et un garde-fou qui fait échouer tout test écrivant hors de son dossier temporaire (`scripts/isolation_tests.py`, chargé par les `conftest.py`) ; une seule suite de tests ou banc à la fois sur la machine (verrou commun).
- **Git :**
  - une branche par travail ;
  - messages de commit en français ;
  - fusion dans `main` (`--no-ff`) seulement quand tout est vert ;
  - après une fusion, le propriétaire fait `git checkout main && git pull` sur son PC.
- **Fichiers à ne pas versionner :** `.venv/`, `spike_reports/`, `*.fit`, `*.jsonl`, `.coverage`.

## Faits matériels et pièges connus

- **BlueZ n'accepte qu'un scan ou une connexion à la fois.** Le verrou de `ble_util.ble_lock()` sérialise trainer et Click ; le trainer passe en premier.
- **HomeTrainer :**
  - Indoor Bike Data arrive à environ 1 Hz au repos et environ 8 Hz après des consignes de pente ;
  - plage de 0 à 1 000 W ;
  - une fréquence cardiaque de 0 signifie « pas de mesure » ;
  - « Start » (0x07) est refusé quand le trainer tourne déjà : c'est sans gravité ;
  - avant un essai, réveiller le trainer en pédalant.
- **Click :**
  - handshake `RideOn` sans chiffrement ;
  - messages `0x23` à environ 10 Hz ; bit à 0 = appuyé (bit 12 = +, bit 8 = −) ;
  - appui court sous 0,5 s, appui long à partir de 0,9 s ;
  - il ne s'annonce qu'après un appui ;
  - il se déconnecte parfois de lui-même (question ouverte) ;
  - diagnostic (lot K8) : chaque coupure est journalisée avec la durée de connexion, le temps depuis la dernière notification, le dernier appui et la dernière écriture au trainer ; cadence des notifications toutes les 60 s ; `log_report` en tire médianes et corrélations avec le trainer ;
  - s'il reste « connecté » côté BlueZ : `bluetoothctl disconnect C1:1C:00:00:00:01`.
- **Godot :** heartbeat dans un fil séparé (lié au rendu, il provoquait des pertes de liaison) ; commandes renvoyées toutes les 200 ms jusqu'à l'accusé.
- **Contrat :** dans la trame `state`, `v` est la **vitesse**, pas la version (clarifié ; renommage prévu pour un contrat v2). Le core remet `last_cmd_id` à 0 à chaque `hello`.
- **Physique :** CPU de 3 à 4 %, pas de 0,2 ms. Python suffit ; Rust seulement si les seuils de la SRS §14.1 sont dépassés.
- **Hors périmètre** (décisions du propriétaire) : Strava et tout service en ligne, avatar, vélo 3D, multijoueur.

## Façon de travailler avec le propriétaire

- Il teste sur le vrai vélo et colle les journaux dans la conversation. Pour un problème, demander les lignes utiles : `grep -E "WARNING|ERROR|Perf|Click" ~/run_trainer.log | tail -30`.
- Lui donner des commandes complètes, à copier-coller, en partant de `/home/utilisateur/Games/lolo_python`.
- Après chaque étape livrée : **ne pas écrire dans `CHANGELOG.md` ni dans `docs/SUIVI_AVANCEMENT.md`** (règle du 22 novembre, audit P3, source des conflits entre PR) ; écrire à la place un seul fichier `docs/changements/<LOT>.md` (forme dans `docs/changements/README.md`), que la passe de doc rassemble. Mettre à jour la ligne d'index du lot, sous le titre de son cahier (avec une section « Livraison » dans le lot ; plus de tableau dans `docs/lots/00_INDEX.md` depuis le lot X54, `python3 scripts/index_lots.py` le calcule) et `README.md` si les commandes changent. Ne pas écrire de nombre de tests dans le `README.md` ni dans le suivi (lot X52) : `python3 scripts/recompte_tests.py` les compte et la CI les affiche dans le résumé de chaque run ; `core/tests/test_docs_coherence.py` refuse un nombre écrit en dur.
- Les lots de `docs/lots/` peuvent être réalisés directement ou confiés à une autre IA (modèle de message dans `00_INDEX.md` §4).
