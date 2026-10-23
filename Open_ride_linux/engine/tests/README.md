# Tests de l'engine sans écran

Tous les tests se lancent depuis `Open_ride_linux/`, avec Godot 4.3 officiel
(`godotengine/godot`, version `4.3-stable`) dont le chemin est donné par `GODOT` :

```bash
GODOT=~/Applications/godot/Godot_v4.3-stable_linux.x86_64 engine/tests/run_engine_tests.sh
```

Le script renvoie 0 si tout passe. Il enchaîne :

1. **Vecteurs de route** (`test_route_vectors.gd`, lot A) : `route_data.gd` contre `docs/contracts/world/route_test_vectors.json`.
2. **Thèmes** (`test_theme_loader.gd`, lot I5) : validation, fusion avec le thème `default` et chargement de textures dans `theme_loader.gd`.
3. **ERG** (`test_erg_view_model.gd`, lot I6) : modèle de vue ERG (`erg_view_model.gd`), histogramme `profile_bars` et scénario des 10 blocs face à `fake_core.py --erg-workout` (bips à T − 3 s ± 0,1 s).
4. **Scénarios IPC** : `fake_core.py` (Python 3, bibliothèque standard) joue le rôle du core ; l'engine tourne sans écran avec `--test-mode`.
5. **Contrôle de la sortie de Godot** : aucune erreur ni aucun avertissement de script, hors avertissements connus du mode sans écran (objets non libérés à la sortie, mesh nul).

Variables facultatives : `STATE_PORT` et `CMD_PORT` (ports de test, 15005 et 15006 par défaut, pour ne pas gêner un core réel), `SCENARIOS` (par exemple `1,2,3` ; le 1 doit venir en premier car il exige un engine qui vient de démarrer), `ENGINE_LOG` (fichier où garder le journal de l'engine).

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
| `--routes-dir=CHEMIN` | `~/.local/share/openride/routes` | Dossier des parcours : l'engine charge `<dossier>/<route_id>.world` ; pour `demo`, repli sur `res://demo/demo.world` si le dossier manque |
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
| `route_loaded id=… length_m=… path=…` / `route_missing id=…` | Parcours chargé / introuvable |
| `cam s=… age_ms=… frozen=0\|1 moved=0\|1` | Position affichée de la caméra, à 20 Hz ; `age_ms` : âge de la dernière trame |

Le faux core déclenche une commande par un message de test `{"type": "_test", "action": "send_command", "name": …, "args": {…}}` envoyé sur le port d'état. Hors `--test-mode`, ce type est inconnu et donc ignoré (contrat §1).

## Essai avec le vrai core (critère 3 du lot D)

```bash
source core/.venv/bin/activate
openride-core run --trainer mock --input none --autostart > /tmp/core.log 2>&1 &
"$GODOT" --headless --path engine > /tmp/engine.log 2>&1 &
sleep 60; kill %2; sleep 1; kill -INT %1; wait
grep -c "Heartbeat engine perdu" /tmp/core.log    # attendu : 0
```
