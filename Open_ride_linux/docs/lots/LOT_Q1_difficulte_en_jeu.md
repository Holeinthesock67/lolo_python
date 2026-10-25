# Lot Q1 – Difficulté du trainer réglable pendant la séance

## 1. Objectif

Essai du 25 octobre sur le HomeTrainer (circuit `essai-69`) : séance jugée trop dure, presque toujours sur les petits braquets. Le core sait déjà réduire la pente envoyée au trainer (`[trainer] difficulty_pct`, 0 à 100 %, défaut 100, appliqué par `Gearing.effective_grade`), comme le réglage « difficulté du trainer » de Zwift (50 % par défaut chez Zwift), mais seulement en éditant `config.toml` avant la séance. Ce lot permet de le régler **pendant** la séance, au clavier de la fenêtre Godot, et l'affiche dans le HUD.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/SRS_v1.1.md` §4.3 (braquets) et §5 (coefficient de difficulté).
2. `docs/contracts/ipc_v1.md` (commandes `cmd`, trame `state`, historique des versions), `docs/contracts/ipc/*.schema.json`.
3. Code : `core/src/openride_core/gearing.py`, `session.py` (calcul de `grade_sent`), `ipc_server.py`, `config.py` (`TrainerConfig.difficulty_pct`, bornes), `journal.py` ; `engine/scripts/main.gd` (`_unhandled_input`), `hud_view_model.gd`, `hud_view.gd`.

## 3. Prérequis

Aucun lot. **Décision du propriétaire avant de confier le lot** : accord sur l'ajout de contrat du §6 et réponse aux questions du §9.

## 4. Travail demandé

- **Core :**
  - nouvelle commande `set_difficulty` (`args` : `{"pct": nombre}`), bornée de 0 à 100 et arrondie à l'entier, refusée avec une erreur `bad_args` hors nombre ; acceptée dans tous les états de séance ;
  - effet immédiat sur la pente envoyée, mais avec la limitation de variation habituelle (`grade_rate_pct_per_s`) pour éviter un à-coup ;
  - la vitesse virtuelle continue d'utiliser la pente réelle (inchangé) ;
  - champ `difficulty_pct` dans chaque trame `state` ;
  - une ligne de journal par changement (`Difficulté : 100 % -> 50 %`) et le champ dans le `.jsonl` ;
  - la valeur de départ reste celle de `config.toml`. L'enregistrement dans `config.toml` revient au menu des réglages (O4).
- **Engine :**
  - touches `D` (−10 %) et `Maj+D` (+10 %) dans la fenêtre Godot, qui envoient `set_difficulty` avec la valeur courante ± 10 ;
  - ligne « Difficulté 50 % » dans le HUD (modèle `hud_view_model.gd`, affichage `hud_view.gd`), cachée quand la valeur vaut 100 % ;
  - bip court à chaque changement (même famille que les bips d'appui).
- Documentation : tableau « Commandes pendant la séance » du `README.md`, contrat IPC.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/session.py`, `ipc_server.py`, `journal.py` ; `engine/scripts/main.gd` (touches et envoi seulement), `hud_view_model.gd`, `hud_view.gd` ; `docs/contracts/ipc_v1.md`, `docs/contracts/ipc/cmd.schema.json` et `state.schema.json` ; `README.md` ; `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Nouveaux :** `core/tests/test_difficulty.py` ; `engine/tests/unit/test_hud_difficulty.gd` (ou cas ajoutés à `test_hud_view_model.gd`).
- **Interdits :** `gearing.py` (la formule ne change pas), `ftms_driver.py`, scripts de rendu.

## 6. Modifications de contrat autorisées

Ajout compatible au contrat IPC (version 1.2, à noter dans l'historique) : commande `set_difficulty` et champ `difficulty_pct` (entier) dans `state`. Un engine v1.1 qui ignore le champ fonctionne comme avant. Rien d'autre.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/` et `compiler/` ; `engine/tests/run_engine_tests.sh` passe (hors échec connu `test_tree_renderer`, #119).
2. Séance simulée (`--trainer mock`) sur une pente de 8 % au braquet 12 : `grade_sent` vaut la pente effective à 100 %, puis la moitié de la pente effective après `set_difficulty 50`, atteinte avec la vitesse de variation configurée ; la vitesse virtuelle ne change pas à puissance égale.
3. `set_difficulty` à −5, 150 ou « abc » : bornée à 0 et 100, ou refusée avec `bad_args` ; le core ne plante pas.
4. `difficulty_pct` présent dans chaque trame `state` et dans le `.jsonl` ; schémas JSON à jour et tests de contrat verts.
5. Engine : `D` puis `Maj+D` envoient les bonnes valeurs (test avec le faux core) ; ligne du HUD visible à 50 %, cachée à 100 %.

**Sur le PC cible (le propriétaire) :** sur la rampe à 10 % d'`essai-69`, passer de 100 à 50 % puis 30 % et dire si la sensation devient juste.

## 8. Hors périmètre

- Curseur dans le menu des réglages et enregistrement dans `config.toml` (O4).
- Changement de la formule des braquets ou des bornes de pente.

## 9. Questions au propriétaire

1. Valeur par défaut : rester à 100 % (comportement actuel) ou passer à 50 % comme Zwift ?
2. Un bouton du Click pour la difficulté ? Sur le boîtier droit, Y = pause (N6) et Z = bonus (série T, 2.0) ; A est libre. Sinon : clavier seulement.
