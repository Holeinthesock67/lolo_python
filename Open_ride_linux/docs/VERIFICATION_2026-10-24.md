# Vérification d'OpenRide Linux – 24 octobre 2026

## 1. Périmètre et méthode

- **Code vérifié :** `Open_ride_linux/` au commit `237b94f` (fusion de la PR #43).
- **Environnements :**
  - Python 3.14.6 avec `constraints.txt` (comme la colonne 3.14 de l'intégration continue) ;
  - Python 3.11 sans contraintes (comme la colonne 3.11) ;
  - Godot 4.3-stable officiel, sans écran.
- **Méthode :**
  1. contrôle de la structure (arborescence, `pyproject.toml`, droits d'exécution des scripts, index des lots, règles de `CLAUDE.md`) ;
  2. exécution des suites officielles (core, compilateur, engine, bout en bout, vecteurs de route, `pip check`) ;
  3. analyse statique (`ruff` règles F, E9, B, PLE, ASYNC ; `pyright` sur `core/src` et `compiler/src`) ;
  4. tests exploratoires de cas limites, écrits hors du dépôt (annexe A), sur les parseurs BLE, les `.zwo`, le contrôleur ERG, la physique et le compilateur GPX.
- **Hors périmètre :** essais sur le matériel réel (Victory, Click).

## 2. Synthèse

Le projet est en bon état : **toutes les suites officielles passent**, en 3.11 comme en 3.14, et la structure est conforme à `CLAUDE.md`. Aucun bug bloquant n'a été trouvé. Les constats ci-dessous sont des défauts de robustesse sur des entrées aberrantes, une incohérence de documentation et de la dette de qualité (imports inutilisés, annotations de type inexactes).

## 3. Résultats des suites officielles

| Suite | Python 3.14 (contraintes) | Python 3.11 (sans contraintes) | Durée (3.14) |
| --- | --- | --- | --- |
| `pip check` | OK | OK | – |
| Core (`pytest -q`) | 261 passés, 0 échec | 255 passés, 6 lents sautés (`-m "not slow"`), 0 échec | 2 min 08 s |
| Compilateur (`pytest -q`) | 154 passés, 2 réseau désélectionnés, 0 échec | 154 passés, 0 échec | 8 s |
| Vecteurs de route (`route_vectors --check`) | à jour | – | < 1 s |
| Engine (`run_engine_tests.sh`) | thèmes 40/40, ERG 54/54, scénarios IPC 8/8, aucune erreur Godot | – | ~ 40 s |
| Bout en bout (`run_e2e.sh`) | 13/13 contrôles OK, HOME réel inchangé | – | 8,2 s |

Aucun test n'a écrit dans le vrai dossier personnel (`~/OpenRide`, `~/.cache/openride`, `~/run_victory.log` absents après les suites).

## 4. Structure du projet

Conforme sur les points vérifiés :

- trois programmes (`core/`, `compiler/`, `engine/`) avec chacun leurs tests ; paquets installables en mode éditable ;
- tous les modules cités dans la section « Architecture » de `CLAUDE.md` existent (contrôlé aussi par `test_docs_coherence.py`) ;
- scripts `scripts/openride-dev.sh`, `engine/tests/*.sh` et `*.py` versionnés exécutables (mode 100755) ;
- aucun `class_name` dans les scripts GDScript de la scène principale ;
- fichiers interdits (`.venv/`, `*.fit`, `*.jsonl`, `.coverage`) couverts par `.gitignore`.

Écarts :

| N° | Gravité | Constat |
| --- | --- | --- |
| S1 | Faible | **Lots K6 et K7 absents de `docs/lots/`.** `README.md`, `CLAUDE.md` et `SUIVI_AVANCEMENT.md` citent le lanceur `openride` (« lot K6 ») et le bilan `summary` (« lot K7 »), mais ni `00_INDEX.md` ni un fichier `LOT_K6_*.md` / `LOT_K7_*.md` n'existent. La règle de `CLAUDE.md` (statut dans l'index et section « Livraison » dans le lot) n'est donc pas respectée pour ces deux livraisons, et `test_docs_coherence.py` ne le détecte pas (il ne contrôle que les lots déjà listés dans l'index). |
| S2 | Faible | **Dépendance de test implicite du compilateur.** Plusieurs tests du compilateur importent `openride_core` (vérification croisée avec `load_world`, parité du catalogue), mais l'extra `dev` de `compiler/pyproject.toml` ne l'installe pas. C'est documenté (commentaire du `pyproject.toml`, `CLAUDE.md`) et l'intégration continue installe les deux paquets, mais `pip install -e "compiler[dev]"` seul donne une suite en échec à l'import. |

## 5. Erreurs et défauts trouvés dans le code

### 5.1 Défauts de robustesse (tests exploratoires en échec)

| N° | Gravité | Fichier | Constat | Reproduction |
| --- | --- | --- | --- | --- |
| R1 | Moyenne | `core/src/openride_core/workout.py:152-160` | **`Repeat` d'un `<IntervalsT>` non borné.** `Repeat="2000000"` est accepté : 4 millions de blocs créés en 5,8 s. Avec une valeur plus grande, la lecture épuise la mémoire. Comme `list_workouts` lit tous les `.zwo` du dossier, un seul fichier aberrant (téléchargé ou mal édité) peut figer ou faire tomber le core au démarrage. Proposition : borner `Repeat` (par exemple à 100) et lever `WorkoutError` au-delà. | `parse_workout('<workout_file><workout><IntervalsT Repeat="2000000" OnDuration="1" OffDuration="1" OnPower="1" OffPower="0.5"/></workout></workout_file>', "x")` |
| R2 | Faible | `core/src/openride_core/tools/workouts.py` (`check --ftp`) | **FTP nulle ou négative acceptée par `workouts check`.** `--ftp 0` affiche des cibles à 0 W ; `--ftp -100` affiche des cibles négatives (« -60 -> -45 W ») sans erreur, code de sortie 0. `openride-core summary` refuse, lui, une FTP ≤ 0 (`SummaryError`) : comportement incohérent entre les deux outils. | `python -m openride_core.tools.workouts check workouts/vo2_5x3.zwo --ftp -100` |
| R3 | Très faible | `core/src/openride_core/workout.py:303` (`ErgController.step`) | **`dt` négatif non refusé** : `step(-10)` fait passer `t_block` à -10. Pas atteignable aujourd'hui (la session dérive `dt` d'une horloge monotone), signalé pour un futur appelant. Le constructeur accepte aussi une FTP ≤ 0 ; la configuration la borne à 50–600 W, donc sans effet en séance. | `ErgController(w, 200).step(-10)` |
| R4 | Très faible | `core/src/openride_core/gearing.py:43-51` | **Pente NaN non filtrée** : `effective_grade(nan)` renvoie NaN (le bornage `min/max` laisse passer NaN), puis `ftms.cmd_set_sim_params` lève `ValueError`. Aucune source de NaN identifiée (le compilateur et `verify` rejettent les valeurs non finies), mais un `math.isfinite` au bornage rendrait la chaîne sûre. | `Gearing(GearingConfig()).effective_grade(float("nan"))` |

Vérifiés sans défaut : trames FTMS tronquées ou vides (les exceptions de `ftms.py` sont rattrapées dans `ftms_driver.py:143` et `:156`), consigne ERG hors plage (bornée par `power_range` avant l'encodage), 20 000 trames Click aléatoires, varint protobuf de longueur énorme, `.zwo` sans bloc (refusé), physique à pas de 1 s et en descente à 25 % (stable et finie), GPX avec points dupliqués, aller-retour intégré, BOM et espace de noms inconnu, franchissement de l'antiméridien, bombe d'entités XML (refusée par expat).

### 5.2 Analyse statique – `ruff`

26 constats, aucun bug fonctionnel :

- **Imports inutilisés (F401), 15 :** `compiler/src/openride_compiler/osm_layers.py:20` (`tile_filename`, seul cas dans le code de production) ; dans les tests : `compiler/tests/test_osm.py` (6), `core/tests/test_conformite.py`, `test_contract_ipc.py` (2), `test_docs_coherence.py`, `test_ipc_mock.py`, `test_log_report.py`, `test_replay.py`, `test_route.py`.
- **Variable de boucle inutilisée (B007) :** `core/src/openride_core/catalog.py:183` (`gpx_name`, à renommer `_gpx_name` ou à itérer sur `.values()`).
- **Asyncio (ASYNC109/ASYNC110), 10 :** paramètres `timeout` sur des fonctions `async` (`ble_util.py:56`, `tools/ble_diag.py:64`, doublures de test) et attente active par `asyncio.sleep` dans une boucle (`input_providers.py:106`, `tests/test_trainer_release.py:127`). Choix de conception acceptables ; à revoir seulement si une migration vers `asyncio.timeout` est envisagée.
- **`zip()` sans `strict=` (B905), 18 :** non retenu (paires décalées `zip(a, a[1:])`, longueurs volontairement différentes).

### 5.3 Analyse statique – `pyright`

32 erreurs de typage, toutes des faux positifs à l'exécution (rétrécissement de type non vu, `Optional` déjà contrôlé plus haut, bibliothèques sans annotations). Une seule est une **annotation inexacte** à corriger :

- `compiler/src/openride_compiler/osm_layers.py:881` : `replace_layer_dir(..., chunks: dict[int, list[dict]])` reçoit aussi `water_chunks`, de type `dict[int, dict[str, list[dict]]]` (`cli.py:238`). Le code fonctionne (le paramètre est seulement transmis à `writer_fn`) ; l'annotation devrait être `Any` ou une union.

Les autres concernent `verify.py` (valeurs `None` déjà rejetées par `_is_number`), `launcher.py` (`env` optionnel), `fit_export.py` (`round(None)` impossible car protégé par `if hrs`), `workout.py:183` (`child.text` déjà testé), `replay.py:44`, `pipeline.py:87`, `terrain.py:22` (`scipy.spatial.cKDTree` non exporté dans les annotations de SciPy), `ble_util.py:40` (`dbus-fast`).

## 6. Recommandations, par priorité

1. **R1** : borner `Repeat` dans `workout.py` et ajouter le test correspondant dans `core/tests/test_workout.py`.
2. **S1** : créer `LOT_K6_*.md` et `LOT_K7_*.md` avec leur section « Livraison », les inscrire dans `00_INDEX.md` ; éventuellement étendre `test_docs_coherence.py` pour signaler un « lot Xn » cité dans la doc mais absent de l'index.
3. **R2** : refuser `--ftp` ≤ 0 dans `tools/workouts.py`, comme `summary`.
4. Nettoyer les imports inutilisés (`ruff check --select F401 --fix`) et corriger l'annotation de `replace_layer_dir`.
5. **R3, R4, S2** : à traiter au fil de l'eau.

## Annexe A – Tests exploratoires

Écrits hors du dépôt pour ne pas casser la règle « tous les tests passent avant chaque commit ». 20 tests : 17 passés, 3 en échec (R1, R3 et le constructeur ERG avec FTP 0, qui relève de R3). Les cas en échec sont reproductibles avec les commandes de la colonne « Reproduction » du §5.1, depuis `core/` avec l'environnement activé.
