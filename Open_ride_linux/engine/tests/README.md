# Tests de l'engine sans écran

Tous les tests se lancent depuis `Open_ride_linux/`, avec Godot 4.3 officiel
(`godotengine/godot`, version `4.3-stable`) dont le chemin est donné par `GODOT` :

```bash
GODOT=~/Applications/godot/Godot_v4.3-stable_linux.x86_64 engine/tests/run_engine_tests.sh
```

Le script renvoie 0 si tout passe et finit par un résumé (une ligne par test et son résultat).

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

## Étapes du script

1. **Tests unitaires** : tous les fichiers de `engine/tests/unit/` (ci-dessus).
2. **Couches OSM** (`test_osm_layers.gd`, lot K4) : `make_osm_world.py` produit avec le vrai compilateur (installé : `pip install -e compiler`), sans réseau, un `.world` à quatre couches à partir des réponses Overpass enregistrées (`compiler/tests/data/osm/`) et écrit les nombres attendus (`expected.json`) ; le test vérifie que `osm_layers.gd` lit autant d'éléments que le compilateur en a écrits, tronçon par tronçon, puis les fichiers corrompus (JSON invalide, anneau de 2 points, `density` 1,5, `kind` inconnu, version `2.0`), `chunks_for_window` et le temps de lecture de 200 bâtiments.
3. **Rendu par tronçons** (`test_world_streamer.gd`, lot E1) : le script écrit d'abord la démo avec terrain synthétique (`python -m openride_core.tools.fake_world --demo --terrain`, lancé avec `PYTHONPATH=core/src`, bibliothèque standard seulement) dans un dossier temporaire, puis vérifie le ruban, les tuiles et la fenêtre de chargement (tableau ci-dessous). Ce test ne doit écrire aucune erreur ni aucun avertissement.
4. **ERG** (`test_erg_view_model.gd`, lot I6) : modèle de vue ERG (`erg_view_model.gd`), histogramme `profile_bars` et scénario des 10 blocs face à `fake_core.py --erg-workout` (bips à T − 3 s ± 0,1 s).
5. **Scénarios IPC** : `fake_core.py` (Python 3, bibliothèque standard) joue le rôle du core ; l'engine tourne sans écran avec `--test-mode` et charge la démo avec terrain du même dossier temporaire.
6. **Contrôle de la sortie de Godot** : aucune erreur ni aucun avertissement de script, hors avertissements connus du mode sans écran (objets non libérés à la sortie, mesh nul).

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
| `route_loaded id=… length_m=… path=…` / `route_missing id=…` | Parcours chargé / introuvable (la ligne d'information qui précède dit si le terrain est présent) |
| `cam s=… age_ms=… frozen=0\|1 moved=0\|1` | Position affichée de la caméra, à 20 Hz ; `age_ms` : âge de la dernière trame |

Le faux core déclenche une commande par un message de test `{"type": "_test", "action": "send_command", "name": …, "args": {…}}` envoyé sur le port d'état. Hors `--test-mode`, ce type est inconnu et donc ignoré (contrat §1).

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
