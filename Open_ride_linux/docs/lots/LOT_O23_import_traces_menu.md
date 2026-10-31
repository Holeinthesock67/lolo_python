# Lot O23 – Importer une trace depuis le menu, sans relancer

## 1. Objectif

Suite du lot O22, choisie par le propriétaire le 31 octobre (« Aide puis import de traces »). Aujourd'hui, ajouter un parcours demande de déposer la trace dans `~/OpenRide/GPX/` et de relancer OpenRide, qui la compile au démarrage (lot N11). Comme pour les entraînements (lot N16), le menu doit proposer les traces de Téléchargements, du Bureau et de `~/OpenRide/Import`, puis les compiler sans relancer.

## 2. Spécification

| # | Règle |
| --- | --- |
| O23-1 | « Ajouter un parcours » ouvre l'écran **Importer une trace** : fichiers `.gpx`, `.fit`, `.tcx`, `.fit.gz`, `.tcx.gz` et `.zip` des mêmes dossiers que l'import d'entraînements, sans sous-dossiers, les plus récents d'abord, 30 au plus, « déjà importé » si une trace identique est déjà dans `~/OpenRide/GPX/`. |
| O23-2 | Un choix copie la trace dans `~/OpenRide/GPX/` (jamais d'écrasement : `_2`, `_3`…), puis le core lance la compilation dans un processus à part (invariant A3). L'écran montre l'avancement, et la liste des parcours est relue à la fin, avec le focus sur le nouveau parcours. |
| O23-3 | Une trace illisible ou refusée par le compilateur affiche son erreur sur la ligne d'état. Rien n'est ajouté à la liste. |
| O23-4 | Pas d'import pendant une séance. Une seule compilation à la fois. |

## 3. Contrat

Ajout compatible à l'IPC, révision 1.5 (ouverte) : `list_route_imports` (réponse `route_imports`, en parties) et `import_route` (réponses `route_import_status` : `compiling` toutes les 2 s, puis `done` ou `failed`). À `done`, l'engine redemande `list_routes` (comme après `workout_saved`) et met le focus sur `route_id`. Détail : `docs/contracts/ipc_v1.md`, schémas `route_imports` et `route_import_status`.

## 4. Réalisation (31 octobre)

Demande du propriétaire, 31 octobre : « L'ajout de trace n'est pas pratique, il faut mettre le fichier à la main puis redémarrer le jeu. »

- Core : `route_import.py` (traces proposées, copie sans écrasement par identifiant normalisé, plan de compilation d'après le catalogue) ; `session.py` lance `openride-compiler build <trace> --out <parcours>` (`--force` si périmé ou illisible) en sous-processus asyncio, 900 s au plus, et retire la copie d'une trace refusée ; `ipc_server.py` (requêtes idempotentes, `route_imports` parmi les listes).
- Engine : écran « Importer une trace » (`menu_flow.gd`) avec carte explicite (dossier, formats, « pas besoin de relancer »), ligne d'état de la compilation en secondes, retour à la liste et focus sur le nouveau parcours ; `ipc_client.gd`, `main.gd` ; aide des parcours (`route_help.gd`) mise à jour.
- Une trace déposée à la main dans `~/OpenRide/GPX/` reste compilée au lancement (N11).
- Tests : `core/tests/test_route_import.py` (doublure `tests/data/stub_compiler.py`), `test_menu_flow.gd` (`_test_route_import`), banc des menus `parcours_import`.
- Reste : tests Godot, banc des menus et captures sur le PC (file du fil de fusion), validation des captures par le propriétaire, puis essai avec un vrai export Garmin.
