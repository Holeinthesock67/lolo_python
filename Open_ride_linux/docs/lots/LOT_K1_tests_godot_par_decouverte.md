# Lot K1 – Tests Godot sans écran lancés par découverte

## 1. Objectif

Chaque lot Godot (A, E1, I5, I6) a ajouté sa propre étape à `engine/tests/run_engine_tests.sh`. Le fichier est devenu un point de conflit : la PR #7 (E1) a dû être réconciliée à la main avec I5 et I6 (audit J, constat J-M4). Les lots K2 à K5 ajoutent chacun un test GDScript : ils ne doivent plus toucher ce script.

Ce lot fait découvrir automatiquement les tests unitaires GDScript d'un dossier, pour qu'un lot n'ait plus qu'à y déposer son fichier.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `engine/tests/README.md`, `engine/tests/run_engine_tests.sh`.
3. Les tests existants : `engine/tests/test_route_vectors.gd`, `test_theme_loader.gd`, `test_erg_view_model.gd` (et, après fusion d'E1, `test_world_streamer.gd`).
4. `.github/workflows/openride.yml` (job `engine`).

## 3. Prérequis

**Après la fusion de la PR #7 (E1)** dans `main`, qui modifie aussi `run_engine_tests.sh`. Partir de `main` à jour.

## 4. Travail demandé

- Nouveau dossier `engine/tests/unit/`. Contrat d'un test unitaire, écrit en tête de `engine/tests/README.md` :
  - un script `test_*.gd` qui `extends SceneTree`, se lance par `godot --headless --path engine --script res://tests/unit/test_x.gd` ;
  - il écrit une ligne `[OK] …` ou `[ÉCHEC] …` par vérification, puis une ligne finale `<nom> : N vérifications, M échecs` ;
  - il quitte avec le code 0 si tout passe, 1 sinon ; il ne dépend d'aucun port réseau ni d'aucun fichier hors de `res://` et `user://`.
- `run_engine_tests.sh` lance chaque `engine/tests/unit/test_*.gd` par ordre alphabétique, dans une étape « Tests unitaires », avec le même filtre d'erreurs et d'avertissements Godot que les étapes existantes ; le résumé final liste chaque fichier et son résultat.
- Déplacer dans `unit/` les tests qui respectent déjà ce contrat (`test_route_vectors.gd`, `test_theme_loader.gd`) et retirer leur étape dédiée. Les tests qui ont besoin d'un faux core (`test_erg_view_model.gd`, scénarios IPC) ou d'un fichier généré (`test_world_streamer.gd`) gardent leur étape.
- Variable facultative `UNIT=nom` pour ne lancer qu'un test.

## 5. Fichiers concernés

- **Nouveaux :** `engine/tests/unit/` (tests déplacés), `engine/tests/unit/test_exemple_echec.gd` n'est **pas** versionné (voir §7).
- **Modifiés :** `engine/tests/run_engine_tests.sh`, `engine/tests/README.md`, chemins `res://tests/...` dans les tests déplacés, `docs/SUIVI_AVANCEMENT.md` (une ligne), `README.md` (commande, si elle change).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `GODOT=… engine/tests/run_engine_tests.sh` renvoie 0 sur `main`, avec les mêmes nombres de vérifications qu'avant (vecteurs 42, thèmes 40, ERG 54, scénarios 8, rendu E1).
2. Démonstration dans le rapport : un fichier `engine/tests/unit/test_zz_echec.gd` temporaire qui échoue fait renvoyer 1 au script et apparaît dans le résumé ; un fichier qui écrit `SCRIPT ERROR` aussi.
3. `UNIT=test_route_vectors engine/tests/run_engine_tests.sh` ne lance que ce test et les étapes à faux core sont sautées.
4. L'intégration continue reste verte, sans modification du job (le script garde son nom et son code de sortie).

## 8. Hors périmètre

- Nouveau test fonctionnel (lots K2 à K5).
- Changement des scénarios IPC.
