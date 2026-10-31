# Lot O23 – Importer une trace depuis le menu, sans relancer

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Importer une trace (GPX, FIT, TCX) depuis le menu et la compiler sans relancer | Python + GDScript | O22, N11 (livré) | Moyenne | Choix du propriétaire du 31 octobre ; spécifié |

## 1. Objectif

Suite du lot O22, choisie par le propriétaire le 31 octobre (« Aide puis import de traces »). Aujourd'hui, ajouter un parcours demande de déposer la trace dans `~/OpenRide/GPX/` et de relancer OpenRide, qui la compile au démarrage (lot N11). Comme pour les entraînements (lot N16), le menu doit proposer les traces de Téléchargements, du Bureau et de `~/OpenRide/Import`, puis les compiler sans relancer.

## 2. Spécification (à valider avant le code)

| # | Règle |
| --- | --- |
| O23-1 | « Ajouter un parcours » ouvre l'écran **Importer une trace** : fichiers `.gpx`, `.fit`, `.tcx`, `.fit.gz`, `.tcx.gz` et `.zip` des mêmes dossiers que l'import d'entraînements, sans sous-dossiers, les plus récents d'abord, 30 au plus, « déjà importé » si une trace identique est déjà dans `~/OpenRide/GPX/`. |
| O23-2 | Un choix copie la trace dans `~/OpenRide/GPX/` (jamais d'écrasement : `_2`, `_3`…), puis le core lance la compilation dans un processus à part (invariant A3). L'écran montre l'avancement, et la liste des parcours est relue à la fin, avec le focus sur le nouveau parcours. |
| O23-3 | Une trace illisible ou refusée par le compilateur affiche son erreur sur la ligne d'état. Rien n'est ajouté à la liste. |
| O23-4 | Pas d'import pendant une séance. Une seule compilation à la fois. |

## 3. Contrat

Ajout compatible à l'IPC : `list_route_imports` (réponse `route_imports`) et `import_route` (réponses `route_import_status`, puis `routes`). La révision est le premier numéro libre à la fusion.

## 4. Fichiers prévus

Core : nouveau module d'import des traces, à côté de `workout_menu.py` et `launch_compile.py` ; `ipc_server.py`. Engine : `menu_flow.gd` (écran d'import). Docs : contrat IPC, guide §4. Tests : pytest de l'import et de la compilation à part, banc des menus.
