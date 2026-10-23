# Lot J8 – Essai de bout en bout sans écran : vrai core et vrai engine

## 1. Objectif

Les tests actuels vérifient chaque programme face à une doublure : l'engine face à `engine/tests/fake_core.py`, le core face à de faux clients UDP. Aucun test ne fait dialoguer **le vrai core et le vrai engine** (audit J, recommandation J-R1). Une dérive entre `fake_core.py` et `ipc_server.py`, ou une régression d'intégration comme celle du 23 octobre, passerait inaperçue jusqu'à l'essai sur le PC.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/contracts/ipc_v1.md` (tout) et `engine/tests/README.md` (arguments `--test-mode`, journal `[test]`, commandes de test).
3. Code : `engine/tests/run_engine_tests.sh`, `engine/tests/fake_core.py` (pour réutiliser la lecture du journal `[test]`), `core/src/openride_core/__main__.py`, `core/src/openride_core/session.py` (mode `--autostart`), `scripts/openride-dev.sh`.

## 3. Prérequis

- **Après J5** (les deux lots modifient `.github/workflows/openride.yml`).
- Si le lot E1 (PR #7) n'est pas fusionné au démarrage, ne pas modifier `run_engine_tests.sh` : le nouveau script est séparé.

## 4. Travail demandé

Nouveau script `engine/tests/run_e2e.sh` (Godot 4.3 officiel, `--headless`) qui :
1. lance `openride-core run --trainer mock --input none --autostart` sur des ports de test libres, avec `HOME` redirigé vers un dossier temporaire (le journal, le FIT et le parcours `demo` n'écrivent jamais dans le vrai dossier personnel) ;
2. lance l'engine avec `--test-mode --ipc-state-port=… --ipc-cmd-port=… --routes-dir=<dossier temporaire>` ;
3. vérifie, à partir du journal `[test]` de l'engine et du journal du core :
   - `hello` puis `hello_ack` en moins de 3 s ;
   - au moins 25 trames `state` par seconde reçues sur 5 s, `seq` croissant ;
   - le parcours `demo` chargé par les deux programmes avec la **même longueur** ;
   - une commande `input_event` `PLUS_SHORT` envoyée par le script au port de commandes du core (avec un `cmd_id` élevé, par exemple 10 000, pour passer devant ceux de l'engine) change `gear` dans les trames suivantes et revient à l'engine comme événement `input` (visible dans son journal `[test]`) ;
   - arrêt de l'engine : le core passe en `PAUSED` (`engine_lost`) en moins de 3 s ; le script écoute alors lui-même le port d'état pour lire les trames ;
   - `end_session` envoyé par le script : `session_state` = `FINISHED`, `summary` conforme au schéma `state.schema.json`, un fichier `.fit` écrit dans le dossier temporaire ;
4. arrête proprement les deux programmes et renvoie 0 si tout passe ; journaux conservés en cas d'échec.

Ajouter l'étape au job `engine` de `.github/workflows/openride.yml`, après les tests existants.

Les commandes sont envoyées par le script en UDP (le core accepte toute commande dont le `cmd_id` dépasse le dernier reçu) : **ne pas modifier `main.gd`**.

## 5. Fichiers concernés

- **Nouveaux :** `engine/tests/run_e2e.sh`, éventuellement `engine/tests/e2e_check.py` (analyse des journaux).
- **Modifiés :** `.github/workflows/openride.yml` (une étape), `engine/tests/README.md` (section « Bout en bout »), `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune. Un écart entre le vrai core et le contrat est signalé, pas corrigé ici.

## 7. Critères d'acceptation

1. `GODOT=… engine/tests/run_e2e.sh` renvoie 0 en local et en intégration continue, en moins de 60 s.
2. Chaque vérification du §4 imprime une ligne `[OK]` ou `[ÉCHEC]` avec la mesure.
3. Démonstration d'échec dans le rapport : avec une longueur de `demo` volontairement modifiée d'un côté (copie temporaire), le script échoue sur la vérification de longueur.
4. Aucun fichier écrit hors des dossiers temporaires (vérifié par le script : `~/OpenRide` et `~/run_trainer.log` du `HOME` réel inchangés).

## 8. Hors périmètre

- Matériel réel, rendu visuel, images par seconde.
- Modification de `main.gd`, `ipc_client.gd` ou des scripts de rendu d'E1.

## 9. Livraison (23 octobre 2026, fait directement à la demande du propriétaire, sans sous-traitance)

- `engine/tests/run_e2e.sh` (enveloppe) et `engine/tests/e2e_check.py` (orchestration et vérifications) : vrai core et vrai engine, `HOME` temporaire, ports UDP libres, lignes `[OK]` / `[ÉCHEC]` avec mesure, journaux gardés en cas d'échec. Environ 8 s en local.
- Étape ajoutée au job `engine` de `.github/workflows/openride.yml`, après les tests existants. `main.gd` et `run_engine_tests.sh` non modifiés (E1 pas encore fusionné). J5 n'est pas fini mais ne touche plus `openride.yml` d'ici là : pas de conflit.
- Écarts assumés : l'engine n'a pas de ligne `[test]` pour un événement `input` ; le script lit la ligne « Bip : PLUS_SHORT » qu'il imprime déjà. Le braquet est lu dans les trames que le script reçoit après l'arrêt de l'engine (le port d'état est tenu par l'engine avant). La longueur du core est `route_length_m` de ces trames ; l'engine lit le même dossier de parcours que le core.
- Vérifications en plus du §4 : aucune erreur ni avertissement de Godot, code de sortie 0 du core, durée totale.
- **Écart au contrat trouvé** : le core n'envoyait que 25 trames `state` par seconde au lieu de 30 (échéance « maintenant + 1/30 s » avec des pas de 20 ms). Signalé et corrigé dans une PR séparée, avec son propre test (`core/tests/test_state_rate.py`) ; cette branche part de ce correctif. Mesure avant : 24,4 trames/s (échec) ; après : 30,0 à 30,2.
- Démonstration du critère 3 : avec une copie de `demo` de 4 800 m donnée à l'engine (`--engine-routes-dir`), le script échoue sur « même parcours demo des deux côtés : core 5000.0 m, engine 4800.0 m » et renvoie 1.
