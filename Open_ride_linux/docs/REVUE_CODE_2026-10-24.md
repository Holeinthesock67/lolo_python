# Revue de code d'OpenRide Linux – 24 octobre 2026

## 1. Périmètre et méthode

- **Code relu :** `Open_ride_linux/` au commit `ef69e42` (fusion de la PR #61), c'est-à-dire tout ce qui est arrivé depuis l'audit J du 23 octobre au soir (`4e0d399`) : lot E1 (route et terrain par tronçons), lots K1 à K8, pilote FTMS mis en conformité (PR #45), deux boîtiers Click (#47), braquets réactifs (#46), cahiers K (#29). Soit 65 fichiers et environ 5 500 lignes ajoutées.
- **Méthode :**
  1. lecture du diff, fichier par fichier, en priorité sur le code qui parle au matériel (`ftms_driver.py`, `input_providers.py`, `ble_util.py`, `session.py`) ;
  2. suites officielles (core, compilateur, engine, bout en bout, vecteurs de route) ;
  3. `ruff check --select F,E9,B007,PLE` ;
  4. essais ciblés hors des suites pour confirmer chaque constat (journaux synthétiques, relance rapide de Godot).
- **Ne refait pas** la [vérification du 24 octobre](VERIFICATION_2026-10-24.md) ni l'[audit FTMS](AUDIT_FTMS_2026-10-24.md) : leurs constats encore ouverts sont seulement mis à jour au §5.
- **Hors périmètre :** essais sur le matériel réel.

## 2. Synthèse

Le code fusionné cette nuit est solide : toutes les suites passent et la relecture n'a trouvé **aucun défaut qui touche une séance**. Un vrai défaut a été trouvé dans l'outil de diagnostic : `log_report` donnait des durées de connexion fausses avec les deux boîtiers du Click récent (C1). Le reste est un message trompeur du lanceur, de la dette de tests et de lint, et une limite d'installation déjà connue. Tout est corrigé dans cette PR, sauf C5 (lot J4) et C6, qui relève de la suite du plan (E3, G).

## 3. Constats

| N° | Gravité | Fichier | Constat |
| --- | --- | --- | --- |
| C1 | Moyenne | `core/src/openride_core/tools/log_report.py` | **Diagnostic du Click faux avec deux boîtiers.** Le lot K8 appariait chaque coupure à la dernière connexion, quel que soit le boîtier. Depuis #47, les boîtiers « + » et « − » sont connectés en même temps : boîtier 1 connecté à 19:00:05, boîtier 2 à 19:00:55, coupure du boîtier 1 à 19:01:05 → rapport « connexion de 10 s » au lieu de 60 s. Les délais de reconnexion étaient faussés de la même façon. La ligne de coupure ne portait pas l'adresse du boîtier, ce qui empêchait de les distinguer. |
| C2 | Faible | `core/src/openride_core/launcher.py`, `README.md` | **Pause promise à tort.** Le lanceur annonçait « la séance est en pause en attendant » à chaque relance de Godot, et le README « la séance reste en pause pendant ce temps ». En réalité, le core ne met en pause qu'après 2 s sans heartbeat (`engine_lost`) : une relance plus rapide passe sans pause (vérifié en relançant Godot à la main). |
| C3 | Faible | `core/tests/test_docs_coherence.py` | **Copie de l'analyseur de commandes du core.** Le contrôle des commandes citées dans la documentation utilisait une copie à la main de l'analyseur d'`openride-core`. Elle avait déjà oublié `release-trainer` une fois : une sous-commande ou une option ajoutée sans mettre la copie à jour aurait fait échouer le test sur une documentation juste, ou laissé passer une documentation fausse. |
| C4 | Très faible | `core/tests/test_docs_coherence.py` | **Exceptions périmées.** `CITED_PATH_EXCEPTIONS` excusait encore `road_builder.gd`, `terrain_tiles.gd` et `world_streamer.gd` « pas encore fusionnés » ; E1 est fusionné, ces exceptions masquaient une éventuelle suppression future de ces fichiers. |
| C5 | Très faible | `core/src/openride_core/launcher.py:40` | **Dossier de l'engine déduit de l'emplacement du paquet** (`parents[3]`). Juste en installation éditable (le seul mode documenté), faux si le core est installé ailleurs ; même famille que J-F2, à couvrir par le lot J4 (variable ou option `--engine-dir`). |
| C6 | Information | `engine/scripts/` | **Modèles K2 à K5 et I6 pas encore branchés.** `hud_view_model.gd`, `vegetation_placer.gd`, `osm_layers.gd`, `menu_model.gd` et `erg_view_model.gd` sont testés sans écran mais aucune scène ne les utilise encore : le HUD affiché reste celui du Spike 0 et le décor se limite à la route et au terrain d'E1. C'est le découpage prévu (branchement dans E3 et G), noté ici pour qu'aucun essai sur le PC cible n'attende ces éléments à l'écran. |
| Q1 | Dette | 16 fichiers | **Lint :** 15 imports inutilisés (F401) et 2 variables de boucle inutilisées (B007, `catalog.py:183` et `test_click_journal.py:34`). |

### Relu sans défaut

- **`ftms_driver.py`, classe `ControlPoint` :** une procédure à la fois, attente de l'indication 0x80 (1 s au plus) avant la commande suivante, abonnement aux indications avant toute écriture, y compris dans `release-trainer`. `CancelledError` toujours relancée.
- **Consignes :** puissance ERG arrondie au pas annoncé (`power_increment`) sans sortir de la plage. Mode absent de Fitness Machine Feature : consigne non envoyée et avertissement écrit une seule fois. `Fitness Machine Status` 0xFF (contrôle perdu) et 0x01 (Reset par un tiers) : consigne renvoyée à la prochaine boucle. Cardio conservé quand une trame partielle ne le porte pas.
- **Braquet immédiat (#46) :** `immediate` est remis à zéro à chaque envoi. Un changement de braquet sur le plat part donc au plus tard 0,2 s après, au lieu de 2 s.
- **`input_providers.py`, `ClickPair` (#47) :**
  - les deux fournisseurs se partagent les adresses réservées (`claimed`), qui sont libérées à la coupure ;
  - un double appui reçu par les deux boîtiers dans les 0,15 s ne compte qu'une fois ;
  - l'absence du second boîtier n'est écrite qu'en DEBUG ;
  - `input_status` vaut CONNECTED tant qu'un des deux boîtiers est connecté.
- **`world_streamer.gd` (E1) :**
  - les fils de travail écrivent seulement dans le dictionnaire de leur travail, et le fil principal ne le lit qu'une fois la tâche terminée ;
  - le compteur de génération écarte les résultats d'un ancien parcours ;
  - `clear()` attend les tâches avant de libérer quoi que ce soit ;
  - les statistiques sont protégées par un `Mutex`.
- **`main.gd` :** `set_world` est appelé à chaque changement de parcours ; le brouillard suit la présence du terrain.

## 4. Corrections apportées (cette PR)

| N° | Correction | Test |
| --- | --- | --- |
| C1 | `input_providers.py` : la ligne de coupure porte l'adresse du boîtier (`Zwift Click déconnecté (adresse A) après …`). `log_report.py` : connexions et coupures suivies par adresse. Pour les journaux d'avant cette PR (coupure sans adresse) : un seul boîtier connecté → c'est lui ; deux boîtiers → durée lue dans la ligne. Les anciens journaux sans adresse du tout donnent les mêmes résultats qu'avant. | `test_click_diagnostic_two_boxes` (`core/tests/test_log_report.py`) |
| C2 | Message du lanceur, docstring et README : « la séance passe en pause si Godot reste absent plus de 2 s ». | – |
| C3 | `__main__.py` : nouvelle fonction `build_parser()`, que `main()` et `test_docs_coherence.py` utilisent tous les deux. La copie est supprimée. | contrôle existant des commandes citées |
| C4 | Les trois exceptions E1 sont retirées. | contrôle existant des chemins cités |
| R4 | `gearing.py` : une pente effective NaN donne 0 % au lieu de traverser le bornage jusqu'à l'encodage FTMS ; une pente infinie reste bornée. | `test_nan_grade_gives_flat_and_infinite_grade_is_clamped` (`core/tests/test_gearing_config.py`) |
| Q1 | `ruff --select F401 --fix`, `catalog.py` itère sur `.values()`, `_` dans `test_click_journal.py`. `ruff check --select F,E9,B007,PLE` ne signale plus rien. | – |
| Annotation | `osm_layers.py` : `replace_layer_dir(..., chunks: dict[int, Any])`, qui reçoit aussi les tronçons d'eau (constat pyright de la vérification du 24 octobre). | – |

## 5. Suivi des constats encore ouverts

| N° | Origine | État |
| --- | --- | --- |
| C5 | Cette revue | Ouvert, rattaché au lot J4. |
| C6 | Cette revue | Prévu : lots E3 (HUD, arbres, OSM) et G (menus). |
| R3 | Vérification du 24 octobre | Ouvert (`ErgController.step` accepte un `dt` négatif ; inatteignable aujourd'hui). |
| S2 | Vérification du 24 octobre | Ouvert (tests du compilateur qui importent le core sans le déclarer dans l'extra `dev`). |
| Click | Audit du 23 octobre | Stabilité à mesurer sur le PC cible ; le rapport `log_report` est maintenant juste avec deux boîtiers (C1). |

## 6. Résultats des suites (après corrections)

| Suite | Résultat |
| --- | --- |
| Core (`pytest -q`, Python 3.13) | 300 passés, 0 échec |
| Compilateur (`pytest -q`) | 154 passés, 2 réseau désélectionnés |
| Engine (`run_engine_tests.sh`, Godot 4.3 sans écran) | tous les tests unitaires et les 8 scénarios IPC passent |
| Bout en bout (`run_e2e.sh`) | tous les contrôles passent |
| Vecteurs de route (`route_vectors --check`) | à jour |
| `ruff check --select F,E9,B007,PLE` | aucun constat |
