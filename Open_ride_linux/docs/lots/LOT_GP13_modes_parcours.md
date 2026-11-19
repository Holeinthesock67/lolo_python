# Lot GP13 – Vélodrome et Grand Prix à l'accueil, avec leurs propres parcours

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : parcours propres à un mode (Vélodrome, Grand Prix), règle unique, accueil et listes | Python, GDScript | GP9, VD10, O32, O38 | Moyenne | GP13a **livré le 16 novembre** (PR #904, avec GP14) ; GP13b à venir (lot gelé du 19 novembre) |

Série GP (mode « Grand Prix des objets ») et série VD (vélodrome). Plan validé par le propriétaire le 15 novembre 2026 : `PLAN_PARCOURS_GRAND_PRIX.md` (dossier du projet, v2).

## 1. Objectif

Essai du 15 novembre : le Grand Prix courait sur le dernier parcours roulé (l'Alpe d'Huez, 14 km de montée), où le changement de voie ne se teste pas. Demande du propriétaire : « sortir le vélodrome de parcours, et ça devient un mode de jeu directement accessible dans l'accueil. Idem pour les parcours pour Grand Prix ». Principe : une règle pour tous les modes, sans exception.

## 2. La règle

Un mode peut avoir ses propres parcours, reconnus à une étiquette de leur fiche (`library.tags`, lot O15). Table unique du core, `mode_routes.MODE_ROUTE_TAGS` : `track` → `velodrome`, `grandprix` → `grandprix`, publiée à l'engine (`hello_ack.config.mode_routes`, contrat IPC révision 1.19).

1. Un parcours d'un mode n'est pas dans la liste générale « Parcours » ; la liste ouverte depuis l'écran Prêt du mode ne montre que les siens.
2. Accueil › « Vélodrome » ou « Grand Prix des objets » : écran Prêt sur le dernier parcours du mode (`last_choices.mode_routes`), sinon le premier de la liste ; sans parcours, la liste vide le dit (« Aucun parcours pour ce mode », contenus de départ).
3. Une séance hors de ces modes repart sur le dernier parcours libre (`last_choices.route_id`, montré à l'accueil), envoyé au core par `select_route`.
4. Le core range un `select_route` d'un parcours de mode dans `last_choices.mode_routes` et ne recharge au démarrage que le dernier parcours libre. La séance conseillée (lot CO9) ne choisit que des parcours libres.
5. Le Circuit des Prés (O38) passe au Grand Prix (étiquette `grandprix`, `demo_biomes.DEMO_TAGS`) ; un circuit écrit avant le lot est remplacé par les contenus de départ (`demo_world.biome_demo_outdated`). Le Col du lacet reste en session libre.

## 3. Livraison (GP13a, 15 novembre 2026)

- Core : `mode_routes.py` (module pur), `last_choices.mode_routes` et `remember_mode_route`, `Session._remember_route`, `hello_ack.config.mode_routes`, `coach_game.load_candidates` ; compilateur : `demo_biomes.DEMO_TAGS`.
- Engine : `menu_model.gd` (`route_mode`, `routes_mode`, `free_world_id`, `prepare_track`, `_open_ready`, `take_pending_route`, entrée « Vélodrome » de l'accueil ; l'écran du vélodrome s'ouvre par son mode et non plus dès qu'une piste est choisie), `menu_flow.gd` (listes filtrées, `select_route` du parcours choisi par le menu), `catalog_model.gd` (`mode_route_ids`, `routes_of_mode`, étiquette « Grand Prix »).
- Contrat : `ipc_v1.md` §5 « Parcours propres à un mode », `hello_ack.schema.json` ; `rev` annoncée inchangée jusqu'à la fusion des révisions 1.17 (#884) et 1.18 (#894).
- Tests : `core/tests/test_mode_routes.py`, `engine/tests/unit/test_mode_routes.gd`, `test_track_menu.gd` repris ; scénarios `menu_bench` `velodrome` (accueil › Vélodrome) et `grand_prix` (parcours d'essai `grand_prix_parcours`).
- Guide : `GUIDE_UTILISATION.md` (modes à parcours propres, vélodrome, Grand Prix).

## 4. Retours de l'essai du 15 novembre (GP14, même PR)

- Boîtes : une rangée tous les 500 m par défaut (`box_every_m`, 500 à 3 000 m) ; une boîte prise disparaît jusqu'à sa reformation (REFORM_S = 2 s, inchangé) : `state.gp.boxes` part de 30 m derrière et `state.gp.boxes_gone` liste `[rang, voie]` des boîtes prises (`BoxRows.near`, `BoxRows.gone`).
- Distance : la course dure au plus le parcours (`distance_km` borné par la longueur restante) ; « Lancer » n'est grisé que sous 1 km (`MIN_COURSE_M`).
- Coup reçu : tant qu'un effet d'attaque, de piège ou contre la tête court sur le cycliste, le bandeau d'avertissement dit « Touché ! Bidon glissant 2 s » et le contour de l'écran prend la couleur de l'objet (`gp_hud_model.hit_view`) ; une menace en vue passe avant ; son et onomatopée inchangés ; jamais de flash plein écran.
- Panneaux de segment (« Sommet dans 500 m » au km 1 du Col du lacet, à gauche) : plaque blanche cadrée de noir sur poteaux à colliers, construite par `roadside_props.build_board` (même plaque que les panneaux du bord de route) au lieu d'une caisse blanche.

## 5. Reste

- Banc PC : `menu_bench` `grand_prix` et `velodrome` en `low`, `medium` et `high` (captures de l'accueil et des écrans Prêt à valider par le propriétaire) ; captures GP14 : coup reçu (bandeau et contour) et panneaux du km 1 du Col du lacet, vus 15 m avant (`--at-m 485,985` : « Sommet dans 1 km » à 500 m, « Sommet dans 500 m » à 1 000 m, à gauche).
- GP13b : Boucle de la Corniche (boucle de 2,5 km, méditerranéen) et Route des Vignes (6 km en ligne, vallonnée), routes revêtues sans épingle et test des routes larges ; bancs `grand_prix` et `grand_prix_onze`.
- Recette GP11 (#845) : étape 2 sur la Route des Vignes après GP13b.
