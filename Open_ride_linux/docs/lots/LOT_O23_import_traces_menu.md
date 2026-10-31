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

Ajout compatible à l'IPC, révision 1.5 (`docs/contracts/ipc_v1.md`, section « Traces importées depuis le menu des parcours ») : `list_route_imports` (réponse `route_imports`, en morceaux comme les autres listes) et `import_route {path}` (réponses `route_import` phase `compiling`, puis phase `done` avec `route_id` et `name`). Refus par `error` : `route_invalid` (trace illisible ou refusée par le compilateur), `busy` (séance en cours ou compilation déjà lancée).

## 4. Réalisation

- Core : `route_import.py` (candidats, copie dédoublonnée par contenu et par identifiant de parcours, commande du compilateur, résultat lu dans le catalogue) ; `session.py` (commandes, compilation `openride-compiler build-all` en sous-processus, 600 s au plus) ; `ipc_server.py`.
- Engine : `ipc_client.gd` (signaux `route_imports_received`, `route_import_received`) ; `menu_flow.gd` (écran **Importer une trace**, ligne d'état, focus sur le nouveau parcours) ; `main.gd` ; `route_help.gd` (sujet « Ajouter une trace » réécrit).
- Tests : `core/tests/test_route_import.py` (compilateur factice, trames validées par les schémas) ; `test_menu_flow.gd` ; scénario `engine/tests/menu_scenarios/parcours_import.json` (vrai compilateur sur une trace synthétique).
- Docs : contrat IPC et schémas `route_imports`, `route_import` ; `GUIDE_UTILISATION.md` §4.

## 5. Statut

En PR, captures du banc des menus à valider par le propriétaire avant fusion. Reste un essai sur le PC (une vraie trace Garmin, compilation d'une nouvelle région) via le fil de fusion.
