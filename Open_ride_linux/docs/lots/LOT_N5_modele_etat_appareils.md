# Lot N5 – Modèle de l'écran d'état des appareils (sans affichage)

## 1. Objectif

Avant de rouler, il faut voir d'un coup d'œil si le trainer, les deux boîtiers du Click et la ceinture cardio sont prêts, et pendant la séance être prévenu d'une batterie faible ou d'un boîtier perdu. Ce lot écrit le modèle de vue de l'écran d'état des appareils et de ses alertes, à partir de l'objet `devices` du contrat v1.1 (lot N1), avec repli sur les champs v1 `trainer_status` et `input_status`.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/contracts/ipc_v1.md` en v1.1 (§3, objet `devices`).
2. `docs/SIMULATION_BLE.md` (appareils simulés), `docs/SRS_v1.1.md` §4.2 (Click).
3. Code : `engine/scripts/banner.gd` (bandeau d'alerte actuel, lecture seule), `engine/scripts/hud_view_model.gd`, `engine/scripts/menu_model.gd`.

## 3. Prérequis

Lot N1 fusionné : **bloqué** jusque-là. Ne dépend ni de la PR #91 ni de N2 (trames écrites à la main dans le test).

## 4. Travail demandé

Nouveau `engine/scripts/devices_view_model.gd` (`extends RefCounted`, sans `class_name`) :

- `rows(state: Dictionary) -> Array` : une ligne par appareil `{id, label, status_text, level}` (`level` : `ok`, `warn`, `error`, `off`) : « Trainer Victory : connecté », « Click + : connecté, batterie 80 % », « Click − : recherche… », « Cardio : ceinture » ou « Cardio : par le trainer » ou « Cardio : absente ».
- Sans `devices` (core v1) : deux lignes tirées de `trainer_status` et `input_status`, mêmes niveaux.
- `alerts(prev_state, state) -> Array` : alertes à montrer **une fois** au changement : boîtier perdu, retour, batterie passée sous 20 % puis sous 10 %, ceinture perdue (cardio repassée au trainer). Pas d'alerte répétée tant que l'état ne change pas.
- `ready_to_ride(state) -> Dictionary` : `{ok, reason}` ; vrai si le trainer est `CONNECTED` ou `MOCK` ; un Click absent n'empêche pas de rouler (clavier), mais donne `reason` « Click absent : clavier seul ».

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/devices_view_model.gd`, `engine/tests/unit/test_devices_view_model.gd`.
- **Modifiés :** `engine/tests/README.md` (une ligne), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, `banner.gd`, scènes, contrat IPC.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Trame v1.1 du scénario `demo` (trainer, deux boîtiers à 80 %, ceinture) : 4 lignes `ok`.
3. Trame v1 sans `devices` : 2 lignes, niveaux tirés de `trainer_status` et `input_status`.
4. Suite de trames : batterie 25, 19, 18, 9 % : exactement deux alertes (sous 20 %, sous 10 %).
5. Boîtier « − » `LOST` puis `CONNECTED` : une alerte de perte, une de retour, rien entre les deux.
6. `ready_to_ride` : trainer `LOST` refusé avec une raison ; Click absent accepté avec la raison « clavier seul ».
7. Aucun nœud créé.

## 8. Hors périmètre

- Affichage (N6) et production de `devices` par le core (N2).
