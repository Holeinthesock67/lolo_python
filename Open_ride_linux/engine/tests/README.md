# Tests de l'engine sans écran

Tous les tests se lancent depuis `Open_ride_linux/`, avec Godot 4.3 officiel
(`godotengine/godot`, version `4.3-stable`) dont le chemin est donné par `GODOT` :

```bash
GODOT=~/Applications/godot/Godot_v4.3-stable_linux.x86_64 engine/tests/run_engine_tests.sh
```

Le script renvoie 0 si tout passe et finit par un résumé (une ligne par test et son résultat).

## Tests de rendu hors écran (`engine/tests/render/`, lot E2)

En mode `--headless`, le serveur de rendu de Godot est factice : aucun shader n'est compilé. Les tests de `engine/tests/render/` rendent donc une vraie image, sous Xvfb avec l'OpenGL logiciel de Mesa (moteur Compatibility), et lisent la couleur des pixels. Même contrat que les tests unitaires (lignes `[OK]`, ligne finale, code de sortie). Paquets : `xvfb`, `xauth`, `libgl1-mesa-dri`. Sans `xvfb-run`, `run_engine_tests.sh` saute cette étape, sauf avec `REQUIRE_RENDER=1` (intégration continue), qui la fait échouer.

| Fichier | Lot | Vérifie |
| --- | --- | --- |
| `test_terrain_render.gd` | E2 | Shader triplanaire compilé et rendu : herbe, roche, neige et trois mélanges égaux à `blend_weights` (L3) à 3/255 près, seuil de pente du thème, texture utilisée à la place de la couleur |

## Tests graphiques de la scène principale (`visual_check.py`)

```bash
GODOT=~/Applications/godot/Godot_v4.3-stable_linux.x86_64 engine/tests/run_visual_tests.sh --open
```

Sans action manuelle : `visual_check.py` lance la vraie scène (`main.tscn`) sous Xvfb (OpenGL logiciel de Mesa, moteur Compatibility), face au faux core (`VisualCore`, dérivé de `fake_core.py`), pour chaque configuration `résolution:qualité` (défaut `1280x720:low,1920x1080:high,1024x600:medium`). Le parcours est la démo avec terrain synthétique. À chaque scène, le script envoie le message de test `{"type": "_test", "action": "screenshot", "path": …, "tag": …}` : l'engine enregistre l'image affichée en PNG et écrit une ligne `[test] screenshot {…}` (textes, visibilité et rectangles en pixels des éléments du HUD, images par seconde, maillages visibles, position de la caméra, `ticks_ms`). PNG lus et écrits avec la bibliothèque standard de Python.

| Scène | Vérifications |
| --- | --- |
| `attente` | Aucun core : ligne d'état « en attente du core… », valeurs `--`, éléments dans l'écran |
| `vue_fixe` | Séance à l'arrêt à s = 1 500 m : les sept lignes du HUD exactes, ligne ERG cachée, bandeau caché, éléments dans l'écran sans chevauchement, texte dessiné (pixels clairs), image ni noire ni uniforme, ciel en haut, sol en bas, maillages affichés |
| `mouvement_1`, `mouvement_2` | 8 m/s : vitesse 28.8 km/h, distance qui avance, caméra à 8 m/s ± 25 % (temps de l'engine), sol qui défile |
| `erg` | Ligne ERG visible, cible dans la ligne de puissance, pente « trainer en ERG », mise en page |
| `pause` | « PAUSED (trainer_lost) » et « RECONNECTING » dans la ligne d'état |
| `core_muet_1`, `core_muet_2` | Core muet : `core_lost`, bandeau « Core non joignable » rouge et sans recouvrir le HUD, caméra et image figées |
| `reprise` | Bandeau disparu, image normale |
| `erreur` | Trame `error` : code `route_invalid` dans le bandeau rouge, sans recouvrir le HUD |
| `journal` | Aucune erreur ni avertissement Godot (mêmes tolérances que ci-dessous), rendu actif |

Images de référence : avec `--golden DOSSIER`, les scènes reproductibles (`attente`, `vue_fixe`, `pause`, `erreur` : s fixé, rien ne bouge) sont comparées aux références ; échec si l'écart moyen dépasse 6 niveaux sur 255 ou si plus de 1 % des pixels changent de plus de 40 niveaux (un défaut localisé, comme une ligne du HUD disparue, ne pèse que quelques niveaux en moyenne). Le rapport montre alors les écarts en rouge. `--update-golden` enregistre les captures comme références. `run_visual_tests.sh` garde les références dans `~/.cache/openride/visual_golden` (`VISUAL_GOLDEN`) et les crée au premier lancement ; après un changement graphique voulu, le relancer avec `--update-golden`.

Sortie : une ligne `[OK]` ou `[ÉCHEC]` par vérification, `rapport.html` (captures, textes du HUD, mesures, tableau des vérifications) et les PNG dans le dossier `--out` (`run_visual_tests.sh` : `~/OpenRide/visual_tests/<date>`, ou `VISUAL_OUT`). Code de sortie 0 si tout passe, 1 sinon, 2 si Godot ou `xvfb-run` manque. `--native` lance l'engine sur l'écran réel avec son rendu habituel (Forward+, GTX 1060) au lieu de Xvfb : la fenêtre s'ouvre environ une minute par configuration, sans rien à faire (références distinctes à prévoir, le rendu n'étant pas celui de Mesa).

`run_engine_tests.sh` lance la même vérification sur `VISUAL_CONFIGS` (défaut `1280x720:low`, environ 40 s, sans références ; `none` pour la sauter), donc aussi en intégration continue.

Premier défaut trouvé : le bandeau d'alerte (placé à 360 px du bord) recouvrait le HUD dès que celui-ci s'élargissait (ligne d'état, ligne ERG). Il se place désormais à droite du HUD s'il reste 360 px, sinon dessous (`banner.gd`, `layout_for`, test `unit/test_banner_layout.gd`).

## Tests unitaires (`engine/tests/unit/`, lot K1)

Pour ajouter un test, il suffit de déposer un fichier dans `engine/tests/unit/` : le script le découvre, sans modification. Contrat d'un test unitaire :

- un script `test_*.gd` qui `extends SceneTree` et se lance par `godot --headless --path engine --script res://tests/unit/test_x.gd` ;
- il écrit une ligne `[OK] …` ou `[ÉCHEC] …` par vérification, puis une ligne finale `<nom> : N vérifications, M échecs` (`<nom>` : nom du fichier sans `.gd`) ;
- il quitte avec le code 0 si tout passe, 1 sinon ; il ne dépend d'aucun port réseau ni d'aucun fichier hors de `res://` et `user://`.

Les fichiers sont lancés par ordre alphabétique. Un test échoue si son code de sortie n'est pas 0, si sa ligne finale manque, s'il écrit une erreur ou un avertissement Godot (`SCRIPT ERROR`, `ERROR:`, `WARNING:`, hors avertissements connus du mode sans écran) ou s'il dépasse `UNIT_TIMEOUT` secondes (120 par défaut : une erreur de script dans `_init` laisse Godot tourner sans quitter).

`UNIT=test_route_vectors engine/tests/run_engine_tests.sh` ne lance que ce test et saute les autres étapes (rendu, ERG, scénarios à faux core).

| Fichier | Lot | Vérifie |
| --- | --- | --- |
| `test_route_vectors.gd` | A | `route_data.gd` contre `docs/contracts/world/route_test_vectors.json` (42 vecteurs) |
| `test_theme_loader.gd` | I5 | Validation, fusion avec le thème `default` et chargement de textures dans `theme_loader.gd` (40 vérifications) |
| `test_menu_model.gd` | K5 | Navigation des menus (`menu_model.gd`) : 12 scénarios d'événements du Click (focus, éléments désactivés, boucle, retour, confirmation, liste vide), événements inconnus, clavier, aucun nœud créé |
| `test_vegetation_placer.gd` | K3 | Placement des arbres (`vegetation_placer.gd`) : déterminisme et empreinte figée, densité par `kind`, bruit sans zone, exclusions (route, limite des arbres, pente, trous), temps d'une tuile |
| `test_hud_view_model.gd` | K2 | Modèle de vue du HUD (`hud_view_model.gd`) : textes et valeurs limites, profil d'altitude (ouvert et boucle), prochaine montée, temps de `profile` |
| `test_building_mesh.gd` | L1 | Maillage 3D des bâtiments extrudés (`building_mesh.gd`) : murs à arêtes vives, toit plat avec cour intérieure, sens des anneaux, couleurs déterministes par `id`, cas invalides et temps de 500 bâtiments |
| `test_water_mesh.gd` | L2 | Maillage de l'eau (`water_mesh.gd`) : cours d'eau en ruban (droits et en coude), plans d'eau avec îles, largeur par défaut, cas invalides et déterminisme |
| `test_theme_render_params.gd` | L3 | Paramètres de rendu tirés du thème (`theme_render_params.gd`) : uniforms terrain, fonction de référence du mélange herbe/roche/neige, poids triplanaires, route et direction du soleil |
| `test_terrain_material.gd` | E2 | Instanciation et configuration du shader triplanaire (`terrain_material.gd` et `terrain.gdshader`) : uniforms du thème et constantes de L3, textures (avec mipmaps), ligne médiane de la route sur une texture de thème, tuiles sans couleur de sommet (le rendu réel est vérifié dans `tests/render/`) |
| `test_render_quality.gd` | E1 | Brouillard de limite (`render_quality.gd`, `main.tscn`) : mode profondeur à pleine opacité (`fog_density` = 1), début et fin avec et sans terrain |
| `test_quality_presets.gd` | L4 | Préréglages de qualité (`quality_presets.gd`) et arguments `--quality` / `--theme` de `engine_args.gd` |
| `test_banner_layout.gd` | – | Placement du bandeau d'alerte (`banner.gd`, `layout_for`) : à droite du HUD s'il reste 360 px, sinon dessous, jamais par-dessus, de 800 à 3 840 px de large |
| `test_sound_model.gd` | L5 | Modèle sonore sans affichage (`sound_model.gd`) : vent, roue libre (délai 0,5 s et arrêt à > 10 W), hystérésis des points d'intérêt, lissage 12 dB/s et déterminisme |
| `test_render_quality.gd` | E3 | Application des préréglages de qualité (`render_quality.gd` et `quality_presets.gd`) : caméra, ombres, SSAO, MSAA, brouillard en profondeur et volumétrique |
| `test_tree_renderer.gd` | E3 | Rendu et gestion des arbres (`tree_renderer.gd`) : LOD0 (0-300 m avec ombres) et LOD1 (300-1500 m sans ombre), déterminisme, exclusions (route, pente, limite des arbres), budget d'instances |
| `test_hud_view.gd` | E3 | Affichage du HUD (`hud_view.gd`) : valeurs principales (>= 48 px), libellés (>= 24 px), profil d'altitude (120 colonnes), prochaine montée, mise en page sans chevauchement à 1280x720 et 1920x1080 |
| `test_erg_view.gd` | N7 | Bandeau et histogramme ERG (`erg_view.gd`) : textes du bandeau (bloc i/n, type, cible biais compris, temps restant, cible suivante, pause), zones de Coggan aux seuils de `openride-core summary`, largeurs des blocs selon le profil v1.1, curseur juste à la seconde, repli en cases égales sans profil, caché en SIM, mise en page à 1280x720 et 1920x1080 |
| `test_summary_view_model.gd` | N4 | Modèle de l'écran de fin de séance (`summary_view_model.gd`) : 10 lignes du bilan enrichi dans l'ordre fixé, 3 lignes en v1, blocs ERG avec déviations et couleurs, fichier FIT seul, écran de menu avec confirmation de quitter, aucun nœud créé |
| `test_devices_view_model.gd` | N5 | Modèle d'état des appareils (`devices_view_model.gd`) : lignes d'état en v1.1 et repli v1, alertes de perte/reconnexion et batterie sous 20 % / 10 %, `ready_to_ride`, aucun nœud créé |
| `test_catalog_model.gd` | N3 | Modèle de catalogue (`catalog_model.gd`) : conversion des parcours et entraînements au format de menu, labels, tri, focus sautant les éléments désactivés, aucun nœud créé |
| `test_cue_model.gd` | essai | Consignes d'essai (`cue_model.gd`) : lecture et tri du fichier `~/OpenRide/Essais/<parcours>.consignes.json`, consignes invalides ignorées, chaque consigne donnée une seule fois à sa distance, réarmement après un nouveau départ, aucun nœud créé |
| `test_sound_player.gd` | E4 | Lecteurs et sons procéduraux du parcours (`sound_player.gd`) : synthèse au démarrage (< 500 ms), vent, roue libre, limitation à 4 lecteurs 3D actifs, volumes à 0,5 dB de `sound_model.gd` |

## Étapes du script

1. **Tests unitaires** : tous les fichiers de `engine/tests/unit/` (ci-dessus).
2. **Couches OSM** (`test_osm_layers.gd`, lot K4 et `test_osm_streamer.gd`, lot E4) : `make_osm_world.py` produit avec le vrai compilateur (installé : `pip install -e compiler`), sans réseau, un `.world` à quatre couches à partir des réponses Overpass enregistrées (`compiler/tests/data/osm/`) et écrit les nombres attendus (`expected.json`) ; le test vérifie que `osm_layers.gd` lit autant d'éléments que le compilateur en a écrits, tronçon par tronçon, puis les fichiers corrompus (JSON invalide, anneau de 2 points, `density` 1,5, `kind` inconnu, version `2.0`), `chunks_for_window` et le temps de lecture de 200 bâtiments.
3. **Rendu par tronçons** (`test_world_streamer.gd`, lot E1) : le script écrit d'abord la démo avec terrain synthétique (`python -m openride_core.tools.fake_world --demo --terrain`, lancé avec `PYTHONPATH=core/src`, bibliothèque standard seulement) dans un dossier temporaire, puis vérifie le ruban, les tuiles et la fenêtre de chargement (tableau ci-dessous). Ce test ne doit écrire aucune erreur ni aucun avertissement.
4. **ERG** (`test_erg_view_model.gd`, lot I6) : modèle de vue ERG (`erg_view_model.gd`), histogramme `profile_bars` et scénario des 10 blocs face à `fake_core.py --erg-workout` (bips à T − 3 s ± 0,1 s).
5. **Scénarios IPC** : `fake_core.py` (Python 3, bibliothèque standard) joue le rôle du core ; l'engine tourne sans écran avec `--test-mode` et charge la démo avec terrain du même dossier temporaire.
6. **Contrôle de la sortie de Godot** : aucune erreur ni aucun avertissement de script, hors avertissements connus du mode sans écran (objets non libérés à la sortie, mesh nul).

Thème d'essai pour le PC cible (hors du script) : `make_texture_theme.py` écrit un thème à trois textures 2 048² dans `~/OpenRide/Themes/essai_textures` ; procédure dans [docs/ESSAI_GRAPHIQUE_E2.md](../../docs/ESSAI_GRAPHIQUE_E2.md).

Lancement seul du test de rendu :

```bash
PYTHONPATH=core/src python3 -m openride_core.tools.fake_world --demo --terrain --out /tmp/routes
"$GODOT" --headless --path engine --script res://tests/test_world_streamer.gd -- /tmp/routes/demo.world
```

## Rendu par tronçons (lot E1)

| N° | Test | Vérification |
| --- | --- | --- |
| 1 | Raccord route-terrain | À s = 0 puis 2 500 m : objets chargés = fenêtre attendue (calculée à part) ; centre du ruban = `sample_point(s).y` à 1 cm ; à 3 m du bord, terrain affiché sous la route de 0 à 20 cm ; tuile lointaine abaissée de 2 m |
| 2 | Durée sans fuite | De 0 à la fin à 20 m/s simulés (60 images/s, sans attente réelle) : `MeshInstance3D` bornés, aucun tronçon manquant sous la caméra ni 10 s plus loin, `Performance.OBJECT_COUNT` en fin à ± 5 % du premier tiers |
| 3 | Jointures | Dernière coupe d'un tronçon = première du suivant, sommet par sommet (démo avec et sans terrain) |
| 4 | Terrain absent | `res://demo/demo.world` : sol plat 5 m sous l'altitude minimale, ruban affiché |
| – | Compléments | `NaN` (moyenne des voisins, puis replis), faces tournées vers le haut ; temps de construction d'un tronçon et d'une tuile |

Variables facultatives : `UNIT` et `UNIT_TIMEOUT` (tests unitaires, ci-dessus), `STATE_PORT` et `CMD_PORT` (ports de test, 15005 et 15006 par défaut, pour ne pas gêner un core réel), `SCENARIOS` (par exemple `1,2,3` ; le 1 doit venir en premier car il exige un engine qui vient de démarrer), `ENGINE_LOG` (fichier où garder le journal de l'engine).

## Scénarios

| N° | Scénario | Vérification |
| --- | --- | --- |
| 1 | `hello` jusqu'au `hello_ack` | `hello` espacés d'1 s ± 0,3 s ; aucun `hello` après le `hello_ack` ; configuration reçue journalisée |
| 2 | Commande ignorée trois fois | 4 envois du même `cmd_id`, espacés de 200 ms environ, puis accusé et fin des renvois |
| 3 | Commande jamais acquittée | Abandon entre 2,7 et 3,3 s, signal `command_failed`, message dans le bandeau, plus de renvoi |
| 4 | Core muet 1,5 s | Bandeau « core non joignable » ; la caméra avance pendant la première seconde (extrapolation), ne bouge plus au-delà de 1,1 s, ne recule jamais ; à la reprise le bandeau disparaît |
| 5 | `shutdown` | Bandeau « Le core s'est arrêté » ; l'engine reste en vie (heartbeats) et renvoie des `hello` ; un nouveau core dont `seq` repart de 1 est accepté |
| 6 | Trames `state` en désordre | La trame arrivée en retard est ignorée et comptée ; la plus récente est appliquée |
| 7 | Trame `error` | Le bandeau contient le code (`route_invalid`) |
| 8 | Heartbeats | 2 Hz ± 20 % pendant 10 s |

## Arguments de l'engine

Ils se donnent après `--` (lecture par `OS.get_cmdline_user_args()`, voir `engine/scripts/engine_args.gd`). Ils ne font pas partie du contrat IPC.

| Argument | Défaut | Rôle |
| --- | --- | --- |
| `--ipc-state-port=N` | 5005 | Port d'écoute des trames du core. S'il est occupé, l'engine affiche un message et quitte avec le code 1 |
| `--ipc-cmd-port=N` | 5006 | Port du core vers lequel partent `hello`, `heartbeat`, `cmd`, `bye` |
| `--routes-dir=CHEMIN` | `~/.local/share/openride/routes` | Dossier des parcours : l'engine charge `<dossier>/<route_id>.world` ; pour `demo`, repli sur `res://demo/demo.world` (sans terrain) si le dossier manque |
| `--test-mode` | absent | Journal de test et messages de test (ci-dessous) ; limite le rendu à 60 images par seconde |

## Ce que l'engine expose aux tests

Avec `--test-mode`, l'engine écrit sur la sortie standard des lignes `[test] clé=valeur`, lues au fil de l'eau par `fake_core.py` dans le fichier où le script redirige la sortie :

| Ligne | Moment |
| --- | --- |
| `hello_ack config={…}` | `hello_ack` reçu (configuration en JSON) |
| `state seq=N s=… session=…` | Trame `state` appliquée |
| `state_late seq=N late=K` | Trame en retard ignorée (K : total) |
| `cmd_sent name=… id=N` | Nouvelle commande |
| `cmd_acked name=… id=N sends=K` | Commande acquittée après K envois |
| `cmd_failed name=… id=N after_ms=… sends=K` | Commande abandonnée |
| `core_lost age_ms=…` / `core_returned` | Core injoignable depuis 1 s / trames reprises |
| `shutdown` | Message `shutdown` reçu |
| `banner text=…` | Texte du bandeau à chaque changement (lignes séparées par ` \| `, vide quand il disparaît) |
| `screenshot {…}` | Capture demandée par le message de test `screenshot` (tests graphiques, ci-dessus) |
| `route_loaded id=… length_m=… path=…` / `route_missing id=…` | Parcours chargé / introuvable (la ligne d'information qui précède dit si le terrain est présent) |
| `cam s=… age_ms=… frozen=0\|1 moved=0\|1` | Position affichée de la caméra, à 20 Hz ; `age_ms` : âge de la dernière trame |

Le faux core déclenche une commande par un message de test `{"type": "_test", "action": "send_command", "name": …, "args": {…}}` envoyé sur le port d'état, et une capture d'écran par `{"type": "_test", "action": "screenshot", "path": …, "tag": …}`. Hors `--test-mode`, ce type est inconnu et donc ignoré (contrat §1).

## Bout en bout (lot J8)

```bash
GODOT=~/Applications/godot/Godot_v4.3-stable_linux.x86_64 engine/tests/run_e2e.sh [--keep]
```

`run_e2e.sh` appelle `e2e_check.py`, qui lance le vrai core (`openride-core run --trainer mock --input none --autostart`) puis l'engine en `--test-mode`, tous deux avec un `HOME` temporaire et deux ports UDP libres. Chaque vérification imprime une ligne `[OK]` ou `[ÉCHEC]` avec sa mesure :

| Vérification | Attendu |
| --- | --- |
| hello puis hello_ack | moins de 3 s entre `Reçu 'hello'` (core) et `hello_ack reçu` (engine) |
| trames state | au moins 25 par seconde sur 5 s (lignes `[test] state`), `seq` croissant |
| input_event relayé | commande `input_event` `PLUS_SHORT` (`cmd_id` 10 000) envoyée par le script : traitée par le core, `Bip : PLUS_SHORT` dans la sortie de l'engine |
| perte de l'engine | engine arrêté : le script écoute le port d'état, `PAUSED` (`engine_lost`) en moins de 3 s |
| braquet | `gear` passé de 12 à 13 dans les trames du core |
| même parcours demo | `route_length_m` du core égal (à 0,05 m près) à la longueur de `route_loaded` de l'engine, qui lit le même dossier de parcours que le core |
| end_session | `FINISHED`, résumé présent, trame conforme à `docs/contracts/ipc/state.schema.json` |
| fichier FIT | écrit dans le dossier temporaire |
| Godot, core, HOME | aucune erreur ni avertissement de Godot (mêmes tolérances que `run_engine_tests.sh`), core arrêté avec le code 0, `~/OpenRide` et `~/run_trainer.log` du vrai `HOME` inchangés, moins de 60 s au total |

Le script renvoie 0 si tout passe. En cas d'échec, ou avec `--keep`, `core.log` et `engine.log` restent dans le dossier temporaire indiqué. `e2e_check.py --engine-routes-dir DOSSIER` donne à l'engine un autre dossier de parcours que le core (sert à vérifier que la comparaison des longueurs échoue).

## Essai avec le vrai core (critère 3 du lot D)

```bash
source core/.venv/bin/activate
openride-core run --trainer mock --input none --autostart > /tmp/core.log 2>&1 &
"$GODOT" --headless --path engine > /tmp/engine.log 2>&1 &
sleep 60; kill %2; sleep 1; kill -INT %1; wait
grep -c "Heartbeat engine perdu" /tmp/core.log    # attendu : 0
```
