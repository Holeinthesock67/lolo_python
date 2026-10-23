# OpenRide Linux – consignes pour Claude Code

Simulateur de cyclisme indoor 3D à usage personnel, natif Linux, plus léger que Zwift.
Propriétaire : Laurent (francophone). **Réponds toujours en français**, de façon concise.

## Matériel et machine cible

- **Matériel :**
  - home trainer JetBlack Victory (FTMS), annoncé en Bluetooth sous le nom « Victory 9908 » ;
  - Zwift Cog ;
  - Zwift Click, adresse `F4:C4:59:15:E1:E7`, modèle récent, messages de type `0x23`.
- **PC cible :** PC de bureau MSI (`depret-MS-7A67`), Ubuntu, GTX 1060, Python 3.14, Godot 4.3 dans `~/Applications/godot/`.
  - Utilisateur `depret` ; dépôt dans `/home/depret/Games/lolo_python`.
  - Un lien `~/Games/Open_ride_linux` pointe vers le dossier du projet.
- **Dépôt GitHub :** `Holeinthesock67/lolo_python`. C'est un dépôt commun à d'autres projets : **ne jamais modifier quoi que ce soit hors de `Open_ride_linux/`**.

## Documents qui font loi (à lire avant de coder)

- `docs/SRS_v1.1.md` : spécification.
- `docs/contracts/ipc_v1.md` et schémas `docs/contracts/ipc/*.schema.json` : messages core ↔ engine.
- `docs/contracts/world_format_v1.md` et `docs/contracts/world/` : format des parcours `.world`, schémas et vecteurs de test de la route.
- `docs/SUIVI_AVANCEMENT.md` : état, tests faits, reste à faire.
- `docs/lots/00_INDEX.md` : lots de travail (cahiers des charges autonomes) et leur statut.
- `docs/AUDIT_2026-10-23.md` : audit et suivi des constats.
- `docs/spikes.md` : faits mesurés sur le matériel.

**Règle :** un contrat ne se modifie que par ajout compatible, avec une ligne au journal des changements du document. Si un contrat paraît faux, le signaler au lieu de l'interpréter.

## Architecture

Trois programmes. Le core est le maître : il détient l'état de la séance, et l'engine n'affiche que ce qu'il reçoit.

| Dossier | Programme | Rôle |
| --- | --- | --- |
| `core/` | `openride-core` (Python, asyncio, bleak) | BLE (Victory, Click), physique à 50 Hz, braquets, journal, FIT, serveur IPC UDP (état à 30 Hz sur le port 5005, commandes sur le port 5006) |
| `compiler/` | `openride-compiler` (Python, numpy, scipy, pyproj) | GPX vers dossier `.world`, couche route (la couche terrain viendra avec le lot B2) |
| `engine/` | Godot 4.3 (GDScript) | Rendu, HUD, caméra interpolée et extrapolée, bips des appuis |

**Modules clés du core** (`core/src/openride_core/`) :
- `session.py` : boucle principale ;
- `ftms_driver.py` : pilote du Victory ;
- `input_providers.py` : Click et clavier ;
- `ble_util.py` : verrou BLE, repli BlueZ ;
- `recorder.py` : journal, mémoire, FIT ;
- `route.py` : lecture des `.world` et interpolation ;
- `demo_world.py` : parcours de démonstration ;
- `physics.py`, `gearing.py`, `ftms.py`, `zwift_click.py` : modules purs, sans entrées-sorties.

## Commandes

```bash
# Environnement du core (une fois)
cd core && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
# Compilateur, dans le même environnement
cd compiler && pip install -e ".[dev]" -e ../core

# Tests (tous doivent passer avant chaque commit)
(cd core && pytest -q)
(cd compiler && pytest -q)
GODOT=~/Applications/godot/Godot_v4.3-stable_linux.x86_64 engine/tests/run_engine_tests.sh

# Séance (depuis Open_ride_linux/) : core en arrière-plan + fenêtre Godot ; journal dans ~/run_victory.log
scripts/openride-dev.sh --trainer ftms --input click --gear 6 --autostart
scripts/openride-dev.sh --trainer mock --input keyboard --autostart        # sans vélo

# Parcours
openride-compiler build trace.gpx      # puis : verify / info
openride-core recover                  # FIT depuis le dernier journal après un plantage

# Diagnostic matériel
openride-ble-diag scan | trainer --name Victory --duration 30 | click --duration 60
```

Vecteurs de route : après toute modification de `route.py`, lancer `python -m openride_core.tools.route_vectors` pour les régénérer, puis `--check` pour vérifier qu'ils sont à jour.

## Conventions

- **Langue :** commentaires, docstrings, messages de journal et documentation en français ; identifiants en anglais.
- **Python :** 3.11 minimum, et le code doit tourner en 3.14. Aucune entrée-sortie bloquante dans la boucle du core. Le matériel s'isole derrière des interfaces (`MockDriver` et `FtmsDriver` s'échangent).
- **GDScript :** jamais de `class_name` dans les scripts chargés par la scène principale. L'engine est lancé sans passer par l'éditeur, et Godot ne connaît alors pas les `class_name` : utiliser `preload`.
  - Les fonctions globales de Godot masquent les méthodes de même nom : `route_data.gd` utilise `wrap_s`, et non `wrap`.
- **Tests :**
  - chaque correction ou fonction a son test ;
  - le matériel se simule avec les doublures de `core/tests/test_drivers_session.py` (`FakeClient`, `fake_finder`) et `MockDriver` ;
  - les tests de session passent `routes_root=tmp_path / "routes"` et redirigent `fit_export.ACTIVITIES_DIR`, pour ne jamais écrire dans le vrai dossier personnel.
- **Git :**
  - une branche par travail ;
  - messages de commit en français ;
  - fusion dans `main` (`--no-ff`) seulement quand tout est vert ;
  - après une fusion, Laurent fait `git checkout main && git pull` sur son PC.
- **Fichiers à ne pas versionner :** `.venv/`, `spike_reports/`, `*.fit`, `*.jsonl`, `.coverage`.

## Faits matériels et pièges connus

- **BlueZ n'accepte qu'un scan ou une connexion à la fois.** Le verrou de `ble_util.ble_lock()` sérialise trainer et Click ; le trainer passe en premier.
- **Victory :**
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
  - s'il reste « connecté » côté BlueZ : `bluetoothctl disconnect F4:C4:59:15:E1:E7`.
- **Godot :** heartbeat dans un fil séparé (lié au rendu, il provoquait des pertes de liaison) ; commandes renvoyées toutes les 200 ms jusqu'à l'accusé.
- **Contrat :** dans la trame `state`, `v` est la **vitesse**, pas la version (clarifié ; renommage prévu pour un contrat v2). Le core remet `last_cmd_id` à 0 à chaque `hello`.
- **Physique :** CPU de 3 à 4 %, pas de 0,2 ms. Python suffit ; Rust seulement si les seuils de la SRS §14.1 sont dépassés.
- **Hors périmètre** (décisions de Laurent) : Strava et tout service en ligne, avatar, vélo 3D, multijoueur.

## Façon de travailler avec Laurent

- Il teste sur le vrai vélo et colle les journaux dans la conversation. Pour un problème, demander les lignes utiles : `grep -E "WARNING|ERROR|Perf|Click" ~/run_victory.log | tail -30`.
- Lui donner des commandes complètes, à copier-coller, en partant de `/home/depret/Games/lolo_python`.
- Après chaque étape livrée : mettre à jour `docs/SUIVI_AVANCEMENT.md`, le statut dans `docs/lots/00_INDEX.md` (avec une section « Livraison » dans le lot) et `README.md` si les commandes changent.
- Les lots de `docs/lots/` peuvent être réalisés directement ou confiés à une autre IA (modèle de message dans `00_INDEX.md` §4).
