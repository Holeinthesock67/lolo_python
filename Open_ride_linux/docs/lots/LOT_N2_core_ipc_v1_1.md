# Lot N2 – Core : messages du contrat IPC v1.1 (listes, appareils, bilan enrichi)

## 1. Objectif

Faire parler le core selon le contrat IPC v1.1 rédigé dans le lot N1 : répondre à `list_routes` et `list_workouts`, publier l'objet `devices` dans la trame `state` et enrichir `summary` en fin de séance. Le menu de l'engine pourra alors se passer de `--autostart`.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/contracts/ipc_v1.md` **dans sa version v1.1** (lot N1 fusionné) et ses schémas.
2. `docs/SIMULATION_BLE.md` (appareils simulés, batterie du Click).
3. Code : `core/src/openride_core/ipc_server.py`, `core/src/openride_core/session.py`, `core/src/openride_core/catalog.py`, `core/src/openride_core/workout.py`, `core/src/openride_core/input_providers.py` (`battery_pct`), `core/src/openride_core/hr_monitor.py`, `core/src/openride_core/tools/session_summary.py`, `core/tests/test_ipc_contract*.py` ou équivalent.

## 3. Prérequis

- Lot N1 fusionné (contrat validé par le propriétaire) : **bloqué** jusque-là.
- E3/E4 (PR #91) et lots M2 et M4 (PR #89 et #90) : fusionnés le 24 octobre, partir de `main` à jour (ils ont modifié `session.py`, `hr_monitor.py` et `input_providers.py`).

## 4. Travail demandé

- `list_routes` : appelle `catalog.list_routes()` hors de la boucle à 50 Hz (`asyncio.to_thread` ou équivalent), convertit chaque `RouteEntry` au format du contrat, coupe à 200 éléments. Réponse renvoyée à chaque demande, même pour un `cmd_id` déjà traité.
- `list_workouts` : idem avec la liste des entraînements (`WorkoutInfo`), profil réduit à 60 couples au plus (fusion des blocs voisins, durée totale conservée).
- `devices` : construit à partir des pilotes (trainer, un ou deux boîtiers Click, ceinture ou cardio du trainer), envoyé une trame sur 30 et à chaque changement d'état ; aucune lecture Bluetooth supplémentaire (on publie ce que les pilotes savent déjà).
- `summary` enrichi : réutilise les calculs de `session_summary.py` sur les enregistrements de la séance, sans relire le journal.
- Les messages restent validés par les schémas en test (comme les messages v1).

## 5. Fichiers concernés

- **Modifiés :** `ipc_server.py`, `session.py`, `input_providers.py` et `hr_monitor.py` (exposer l'état et la batterie en lecture seule si ce n'est pas déjà fait), `core/tests/` (tests du contrat), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Nouveaux :** `core/src/openride_core/ipc_lists.py` (conversion catalogue et entraînements vers le contrat), `core/tests/test_ipc_v1_1.py`.
- **Interdits :** `docs/contracts/` (sauf erreur signalée), l'engine.

## 6. Modifications de contrat autorisées

Aucune : le contrat est celui du lot N1. Un écart trouvé est signalé, pas corrigé.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Avec 3 parcours prêts, 1 à compiler et 1 invalide dans un dossier temporaire : `routes` contient 5 éléments aux bons statuts, validé par `routes.schema.json`.
3. 250 parcours : 200 éléments, `truncated` vrai, datagramme sous 60 ko, réponse en moins de 500 ms.
4. Pendant la lecture du catalogue, la boucle à 50 Hz ne prend pas de retard de plus de 20 ms (mesure dans le test avec un catalogue ralenti artificiellement).
5. Bluetooth simulé, scénario `demo` (`--trainer sim --input sim --hr sim`) : `devices` présent une trame sur 30, deux boîtiers Click avec leur batterie, ceinture `strap` ; coupure d'un boîtier du scénario : `devices` envoyé à la trame suivante avec `LOST`.
6. Fin de séance ERG simulée : `summary` contient `np_w`, `tss` et `blocks`, égaux à `openride-core summary` sur le journal produit (à 1 W ou 0,1 TSS près).
7. Un engine v1 (scénarios IPC existants de `fake_core.py` / `run_e2e.sh`) fonctionne sans changement.

## 8. Hors périmètre

- Affichage (N5, N6) et client engine (N3).
- Compilation depuis le menu.
