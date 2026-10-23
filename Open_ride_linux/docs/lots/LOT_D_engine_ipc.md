# Lot D – Mise en conformité de l'engine Godot avec le contrat IPC

## 1. Objectif

Faire respecter par `openride-engine` tout ce que le contrat IPC v1 lui demande, rendre la caméra fluide (extrapolation) et ajouter des tests automatiques sans écran.

Ce lot corrige les constats M3 et F9 de l'audit. Il reste dans le démonstrateur actuel : le rendu 3D complet est l'objet du lot E1.

## 2. À lire

1. `docs/lots/00_INDEX.md`. Rappel : pas de `class_name` dans les scripts chargés par la scène principale ; utiliser `preload`.
2. `docs/contracts/ipc_v1.md` en entier, en particulier :
   - §4 : fiabilité des commandes ;
   - §5 : `hello`, `shutdown`, `error` ;
   - §6 : colonne « Réaction de l'engine ».
3. `docs/SRS_v1.1.md` §8 (fluidité) et §4.5 (navigation).
4. Code : `engine/scripts/ipc_client.gd`, `engine/scripts/main.gd`, `engine/scenes/main.tscn`, `engine/scripts/route_data.gd`.
5. Pour les tests : `core/src/openride_core/ipc_server.py`, qui donne le format exact des trames émises par le core.

## 3. Situation actuelle

- **Commandes :** `ipc_client.gd` envoie chaque commande une seule fois, sans attendre d'accusé.
- **Messages ignorés :** `hello_ack` est reçu mais n'est pas exploité, sauf pour arrêter les `hello`. `error` et `shutdown` sont ignorés.
- **Heartbeat :** il part d'un fil dédié. Ce choix corrige une perte de liaison observée sur le PC cible et doit être conservé.
- **Caméra :** `main.gd` fait tendre `current_s` vers le dernier `s` reçu (`lerpf`). La caméra a donc environ 100 ms de retard et s'arrête net si le core se tait.
- **Valeurs codées en dur :** ports 5005/5006 et parcours `res://demo/demo.world`.

## 4. Travail demandé

### D1. Fiabilité des commandes (contrat §4)

- `send_command(name, args)` mémorise la commande en attente, avec son `cmd_id`, et la renvoie toutes les 200 ms jusqu'à ce qu'un `state` porte `last_cmd_id ≥ cmd_id`.
- Au bout de 3 s sans accusé : abandon, signal `command_failed(name)` et message à l'écran.
- Plusieurs commandes peuvent être en attente en même temps.
- Les commandes `input_event` sont des appuis : elles suivent la même règle, et un appui abandonné n'est pas rejoué.

### D2. Messages du core

- **`hello_ack`** : mémoriser `config` (`ftp_w`, `gears_total`, `theme`) et l'exposer.
- **`error`** : afficher `code` et `message` dans un bandeau, pendant 5 s au moins ou jusqu'à la trame `state` suivante qui change de `session_state`.
- **`shutdown`** : afficher « Le core s'est arrêté » et revenir à l'attente, avec des `hello` toutes les secondes. Ne pas quitter.
- **Trame `state` en retard** (`seq` inférieur au dernier reçu) : l'ignorer, et compter les sauts de `seq` dans un compteur de diagnostic.

### D3. Core injoignable (contrat §6)

- Plus de `state` depuis 1 s : bandeau « core non joignable » ; extrapolation de la caméra pendant 1 s au plus, puis caméra figée ; reprise des `hello` toutes les secondes.
- Dès la reprise des trames : bandeau retiré, `hello` renvoyé si nécessaire, sans redémarrer l'engine.

### D4. Caméra : interpolation et extrapolation (SRS §8)

- **Mémoire :** garder les deux dernières trames `(t_reçu, s, v)`, `t_reçu` étant l'horloge locale `Time.get_ticks_usec()`.
- **Position affichée :** `s_aff = s_dernier + v_dernier × (maintenant − t_reçu_dernier)`, bornée à 1 s d'extrapolation.
- **Correction douce :** quand une nouvelle trame arrive, l'écart entre la position affichée et la position extrapolée de la nouvelle trame est rattrapé en 150 ms, sans saut. La position ne recule jamais pendant `RUNNING`.
- **Hors `RUNNING` :** la caméra se cale sur `s` sans extrapolation.
- **Parcours en boucle** : appliquer `route.wrap_s(s)` (lot A ; la méthode ne s'appelle pas `wrap`, nom déjà pris par une fonction globale de Godot).

### D5. Paramètres et parcours

- **Ports :** lus sur la ligne de commande de l'engine, après `--` :
  - arguments : `--ipc-state-port=5005 --ipc-cmd-port=5006` ;
  - lecture par `OS.get_cmdline_user_args()` ;
  - valeurs par défaut : 5005 et 5006.
  - Si le port d'écoute est occupé, afficher un message explicite et quitter avec le code 1 (contrat §2).
- **Parcours :** chargé selon le `route_id` reçu dans `state`.
  - Dossier : `<routes>/<route_id>.world`, où `<routes>` vaut `~/.local/share/openride/routes`, ou l'argument `--routes-dir=…`.
  - Chargement à chaque changement de `route_id`, en tâche de fond si possible.
  - Repli sur `res://demo/demo.world` si `route_id` vaut `demo` et que le dossier utilisateur manque.
  - Un parcours introuvable affiche un bandeau, sans planter.
  - Chargement avec `route_data.gd` du lot A : `var r = preload("res://scripts/route_data.gd").new()`, puis `r.load_world_dir(chemin)` (renvoie vrai ou faux ; message dans `r.load_error`). Méthodes : `sample(s)` (dictionnaire complet), `sample_point(s)`, `sample_heading_deg(s)`, `sample_grade(s)`, `wrap_s(s)`, `is_loop()` ; propriétés `length_m`, `type`, `n`, `x`, `z`, `alt_m`.

### D6. Tests automatiques sans écran (audit F9)

- **Faux core :** `engine/tests/fake_core.py` (Python 3, bibliothèque standard seulement). Il écoute le port de commandes, envoie des `state` à 30 Hz et rejoue des scénarios.
- **Lanceur :** `engine/tests/run_engine_tests.sh`. Il démarre le faux core, lance `godot --headless --path engine -- --ipc-state-port=… --ipc-cmd-port=…` avec un script de test, et renvoie 0 si tous les scénarios passent.
- **Scénarios minimaux :**
  1. `hello` répété jusqu'au `hello_ack`, puis arrêt des `hello`.
  2. Une commande dont le faux core ignore les trois premiers envois : l'engine la renvoie, puis la voit acquittée.
  3. Une commande jamais acquittée : abandon au bout de 3 s ± 0,3 s, signal émis.
  4. Le faux core se tait 1,5 s : bandeau affiché ; extrapolation pendant 1 s, puis caméra figée ; les trames reprennent et le bandeau disparaît.
  5. Le faux core envoie `shutdown` : l'engine ne quitte pas et renvoie des `hello`.
  6. Des trames `state` en désordre : seule la plus récente est appliquée.
  7. Une trame `error` : le bandeau contient le code.
  8. Les heartbeats arrivent à 2 Hz ± 20 % pendant 10 s.
- **Comment l'engine expose son état aux tests :** le choix est libre (journal sur la sortie standard au format `[test] clé=valeur`, ou fichier). Le documenter dans `engine/tests/README.md`.
- Godot 4.3 officiel est téléchargeable sur GitHub (`godotengine/godot`, version `4.3-stable`). Le chemin de l'exécutable se donne par la variable `GODOT`.

## 5. Fichiers concernés

- **Modifiés :**
  - `engine/scripts/ipc_client.gd`, `engine/scripts/main.gd`, `engine/scenes/main.tscn` (si un bandeau y est ajouté) ;
  - `scripts/openride-dev.sh` : passer les ports de `config.toml` si c'est simple, sinon laisser les valeurs par défaut.
- **Nouveaux :**
  - `engine/scripts/` : modules auxiliaires si besoin (`camera_follow.gd`, `banner.gd`, …) ;
  - `engine/tests/` : tout le dossier.
- **Si le lot A est livré :** utilisation de `route_data.gd` sans le modifier, sauf correction signalée dans le rapport.

## 6. Modifications de contrat autorisées

Aucune. Les arguments de ligne de commande de l'engine ne font pas partie du contrat IPC ; les documenter dans `engine/tests/README.md` et dans `README.md`.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` renvoie 0 ; les 8 scénarios sont listés avec leur résultat.
2. `pytest` passe toujours dans `core/` (rien n'y est modifié).
3. Avec le vrai core (`openride-core run --trainer mock --input none --autostart`) et l'engine sans écran pendant 60 s, le core ne journalise aucun « Heartbeat engine perdu ».
4. Le scénario « Core injoignable » montre une caméra figée au plus 1,1 s après la dernière trame.
5. Aucune erreur ni avertissement de script dans la sortie de Godot, hors avertissements connus du mode sans écran (mesh nul, objets non libérés à la sortie).
6. **Essai manuel du propriétaire :** sur le PC cible, la caméra avance sans saccade visible à 60 images par seconde. Une relance de Godot en pleine séance permet de reprendre avec `+` / `−`. Ce second point dépend aussi du lot C1.

## 8. Hors périmètre

- Ruban de route, terrain, ciel et arbres (lot E1 et suivants).
- Menus de sélection (lot G, à rédiger).
- Bips des appuis : déjà faits, à conserver.
