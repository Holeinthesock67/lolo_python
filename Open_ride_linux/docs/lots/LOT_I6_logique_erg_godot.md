# Lot I6 – Logique de l'entraînement ERG côté Godot

## 1. Objectif

Préparer l'affichage des entraînements ERG dans l'engine (sprint 4 de la SRS : bandeau, bip à T − 3 s, histogramme des blocs) en livrant d'abord la **logique**, testée sans écran : ce qu'il faut afficher et quand biper, calculé à partir de l'objet `erg` des trames `state`. Le dessin à l'écran et le branchement dans `main.gd` viendront dans un lot F2, avec un contrôle visuel.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/SRS_v1.1.md` §6 (ERG, bandeau, bip) et §13 (critère du sprint 4 : bip à T − 3 s).
3. `docs/contracts/ipc_v1.md` §3 (objet `erg` : `workout_name`, `block_index`, `block_count`, `block_type`, `block_remaining_s`, `block_total_s`, `target_w`, `next_target_w`, `bias_pct`, `paused`) et §2 (fréquence des trames, 30 Hz).
4. Code :
   - `core/src/openride_core/workout.py` (`ErgController.to_dict`, profil des blocs) ;
   - `engine/scripts/ipc_client.gd` et `main.gd` (réception des trames, sans les modifier) ;
   - `engine/tests/fake_core.py` et `run_engine_tests.sh` (scénarios face au faux core).

## 3. Prérequis

- Lot F livré.
- **Lot E1 fusionné** (PR #7), pour la même raison que le lot I5 (`run_engine_tests.sh`). Partir de `main` à jour après cette fusion.

## 4. Travail demandé

### 4.1 Script `engine/scripts/erg_view_model.gd` (nouveau, sans `class_name`, chargé par `preload`)

Entrée : l'objet `erg` de chaque trame (ou `null`) et l'heure de rendu. Sortie : un dictionnaire prêt à afficher, sans aucun nœud Godot.

| Sortie | Règle |
| --- | --- |
| `visible` | `erg` non nul |
| `title` | `workout_name`, et « Bloc i / n » |
| `target_text` | « 238 W », ou « Roue libre » si `block_type` vaut `freeride` ; « (110 %) » ajouté si le biais n'est pas 100 |
| `next_text` | « Ensuite : 300 W dans 0:42 », ou vide au dernier bloc |
| `remaining_text` | `block_remaining_s` en m:ss, interpolé entre deux trames avec l'horloge de rendu (pas de saut d'une seconde à 30 Hz), figé si `paused` |
| `progress` | de 0 à 1 dans le bloc |
| `beep` | vrai **une seule fois** par bloc, au premier rendu où le temps restant interpolé passe sous 3,0 s ; jamais en pause ; jamais pour un bloc de moins de 4 s ; de nouveau possible après un changement de `block_index` (y compris par saut de bloc) |
| `paused_text` | « ERG en pause » si `paused` |

**Histogramme :** fonction `profile_bars(blocks: Array, ftp_w: float, width: float, height: float) -> Array` qui transforme une liste de blocs (type, durée, fraction de début et de fin, comme `WorkoutInfo.profile` du core) en rectangles ou trapèzes normalisés. La liste des blocs n'existe pas encore dans le contrat IPC : la fonction est testée avec des données construites par le test, et le rapport le signale pour le lot G.

### 4.2 Tests sans écran

- `engine/tests/test_erg_view_model.gd` : cas unitaires (biais, roue libre, dernier bloc, pause, saut de bloc, bloc court, interpolation du temps restant, unicité du bip à 30 Hz et à 144 Hz de rendu).
- Scénario face au faux core : `fake_core.py` gagne une option qui émet un entraînement simulé (trames `state` avec `erg`) ; un script de test vérifie qu'un bip et un seul est demandé par bloc, à 3,0 s ± 0,1 s de la fin.
- Étape « ERG (lot I6) » ajoutée à `run_engine_tests.sh`.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/erg_view_model.gd`, `engine/tests/test_erg_view_model.gd`.
- **Modifiés :** `engine/tests/fake_core.py` (option ajoutée, comportement par défaut inchangé), `engine/tests/run_engine_tests.sh` (une étape), `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdit :** `main.gd`, `ipc_client.gd` et les scripts de rendu de E1.

## 6. Modifications de contrat autorisées

Aucune. Si un champ manque à l'objet `erg` pour une règle du §4.1, s'arrêter et le signaler.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier avec Godot 4.3 sans écran, en local et dans l'intégration continue ; les 8 scénarios IPC existants restent verts.
2. Chaque règle du tableau du §4.1 a au moins un test.
3. Sur l'entraînement simulé (les 10 blocs du fichier de référence du lot F, tous de plus de 4 s, sans pause) : exactement 10 bips, un par bloc, chacun entre 3,1 et 2,9 s avant la fin du bloc ; avec une pause ERG pendant les 3 dernières secondes d'un bloc, ce bloc n'en déclenche aucun.
4. Aucun `class_name` ; aucune ligne `WARNING:` ou `SCRIPT ERROR` dans la sortie de Godot.

## 8. Hors périmètre

- Dessin du bandeau et de l'histogramme, son du bip (lot F2, avec contrôle visuel et à l'oreille).
- Messages IPC donnant la liste des blocs (lot G).
