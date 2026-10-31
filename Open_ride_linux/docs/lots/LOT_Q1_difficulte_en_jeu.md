# Lot Q1 – Difficulté du trainer réglable pendant la séance

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Difficulté du trainer : défaut 50 %, commande `set_difficulty` pendant la séance, HUD (curseur dans O4) | Python + GDScript | — | Petite | Oui (contrat IPC v1.2 accepté le 25 octobre) ; issue #168 |

## 1. Objectif

Essai du 25 octobre sur le HomeTrainer (circuit `essai-69`) : séance jugée trop dure, presque toujours sur les petits braquets. Le core sait déjà réduire la pente envoyée au trainer (`[trainer] difficulty_pct`, 0 à 100 %, défaut 100, appliqué par `Gearing.effective_grade`), comme le réglage « difficulté du trainer » de Zwift, mais seulement en éditant `config.toml` avant la séance. Ce lot passe la valeur par défaut à 50 % comme Zwift, permet de la changer **pendant** la séance par une commande IPC et l'affiche dans le HUD. Le curseur qui envoie cette commande est dans le menu des réglages et l'écran de pause (lots O3 et O4) ; il n'y a ni bouton du Click ni touche dédiée (décision du propriétaire du 25 octobre).

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/SRS_v1.1.md` §4.3 (braquets) et §5 (coefficient de difficulté), `docs/lots/LOT_O3_reglages_core.md` et `LOT_O4_menu_reglages.md` (le curseur).
2. `docs/contracts/ipc_v1.md` (commandes `cmd`, trame `state`, historique des versions), `docs/contracts/ipc/*.schema.json`.
3. Code : `core/src/openride_core/gearing.py`, `session.py` (calcul de `grade_sent`), `ipc_server.py`, `config.py` (`TrainerConfig.difficulty_pct`, bornes), `journal.py` ; `engine/scripts/hud_view_model.gd`, `hud_view.gd`, `ipc_client.gd`.

## 3. Prérequis

Aucun. Décisions du propriétaire prises le 25 octobre : ajout de `set_difficulty` au contrat accepté, défaut 50 %, pas de bouton du Click, réglage par un curseur dans un menu.

## 4. Travail demandé

- **Core :**
  - valeur par défaut de `TrainerConfig.difficulty_pct` : 50 ; mettre à jour les tests qui supposaient 100 (sans changer ce qu'ils vérifient : leur passer `difficulty_pct = 100` explicitement quand ils testent la formule) ;
  - nouvelle commande `set_difficulty` (`args` : `{"pct": nombre}`), bornée de 0 à 100 et arrondie à l'entier, refusée avec une erreur `bad_args` hors nombre ; acceptée dans tous les états de séance, y compris `RUNNING` et `PAUSED` (contrairement à `set_setting` d'O4) ;
  - effet immédiat sur la pente envoyée, mais avec la limitation de variation habituelle (`grade_rate_pct_per_s`) pour éviter un à-coup ;
  - la vitesse virtuelle continue d'utiliser la pente réelle (inchangé) ;
  - champ `difficulty_pct` dans chaque trame `state` et dans `hello_ack.config` ;
  - une ligne de journal par changement (`Difficulté : 50 % -> 30 %`) et le champ dans le `.jsonl` ;
  - la commande ne change que la séance en cours ; l'enregistrement dans `config.toml` passe par `set_setting` (O3, O4).
- **Engine :**
  - fonction `send_set_difficulty(pct)` dans `ipc_client.gd`, appelée plus tard par le curseur d'O4 (aucune touche ni bouton dans ce lot) ;
  - ligne « Difficulté 50 % » dans le HUD (modèle `hud_view_model.gd`, affichage `hud_view.gd`), cachée quand la valeur vaut 100 %.
- Documentation : contrat IPC, `README.md` (réglage du trainer et valeur par défaut).

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/config.py` (défaut seulement), `session.py`, `ipc_server.py`, `journal.py`, tests du core qui supposaient 100 % ; `engine/scripts/ipc_client.gd`, `hud_view_model.gd`, `hud_view.gd` ; `engine/tests/fake_core.py` (accepte `set_difficulty`) ; `docs/contracts/ipc_v1.md`, `docs/contracts/ipc/cmd.schema.json`, `state.schema.json` et `hello_ack.schema.json` ; `README.md` ; `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Nouveaux :** `core/tests/test_difficulty.py` ; cas ajoutés à `engine/tests/unit/test_hud_view_model.gd`.
- **Interdits :** `gearing.py` (la formule ne change pas), `ftms_driver.py`, `main.gd`, scripts du menu (O4), scripts de rendu.

## 6. Modifications de contrat autorisées

Ajout compatible au contrat IPC (version 1.2, accepté par le propriétaire le 25 octobre, à noter dans l'historique) : commande `set_difficulty` et champ `difficulty_pct` (entier) dans `state` et `hello_ack.config`. Un engine v1.1 qui ignore le champ fonctionne comme avant. Rien d'autre.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/` et `compiler/` ; `engine/tests/run_engine_tests.sh` passe (hors échec connu `test_tree_renderer`, #119).
2. Sans `difficulty_pct` dans `config.toml`, la séance démarre à 50 % (ligne de journal au démarrage).
3. Séance simulée (`--trainer mock`) sur une pente de 8 % au braquet 12 : `grade_sent` vaut la moitié de la pente effective à 50 %, puis 30 % de celle-ci après `set_difficulty 30`, atteinte avec la vitesse de variation configurée ; la vitesse virtuelle ne change pas à puissance égale.
4. `set_difficulty` à −5, 150 ou « abc » : bornée à 0 et 100, ou refusée avec `bad_args` ; le core ne plante pas ; acceptée en `RUNNING` et en `PAUSED`.
5. `difficulty_pct` présent dans chaque trame `state`, dans `hello_ack.config` et dans le `.jsonl` ; schémas JSON à jour et tests de contrat verts.
6. Engine : `send_set_difficulty(30)` envoie la bonne commande (test avec le faux core) ; ligne du HUD visible à 50 %, cachée à 100 %.

**Sur le PC cible (le propriétaire) :** rouler la rampe à 10 % d'`essai-69` à 50 % (défaut) et dire si la sensation est juste ; tant qu'O4 n'est pas livré, changer la valeur dans `config.toml`.

## 8. Hors périmètre

- Le curseur lui-même, dans les réglages et l'écran de pause (O3, O4).
- Bouton du Click ou touche du clavier pour la difficulté (refusé par le propriétaire).
- Changement de la formule des braquets ou des bornes de pente.
- La résistance que le trainer calcule lui-même sur le plat (air et roulement, d'après la vitesse de sa roue) : la difficulté ne la change pas.
