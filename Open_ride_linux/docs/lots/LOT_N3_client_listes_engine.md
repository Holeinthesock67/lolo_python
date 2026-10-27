# Lot N3 – Engine : client des listes v1.1 et branchement au modèle de menu (sans affichage)

## 1. Objectif

Côté Godot, demander les listes de parcours et d'entraînements au core (contrat v1.1, lot N1), les convertir en éléments du modèle de menu (`menu_model.gd`, lot K5) et produire les commandes à envoyer quand l'utilisateur choisit. Tout reste sans affichage, testable sans écran contre `fake_core.py`.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/contracts/ipc_v1.md` en v1.1 (lot N1 fusionné).
2. `docs/lots/LOT_K5_navigation_menus.md` (§9 : écran « Prêt », actions renvoyées).
3. Code : `engine/scripts/ipc_client.gd`, `engine/scripts/menu_model.gd`, `engine/tests/fake_core.py`, `engine/tests/run_engine_tests.sh`, `engine/tests/README.md`.

## 3. Prérequis

Lot N1 livré le 24 octobre : contrat v1.1 sur `main`. Ne dépend pas de la PR #91 (fichiers distincts), ni de N2 (le faux core suffit).

## 4. Travail demandé

- `ipc_client.gd` : commandes `list_routes` et `list_workouts` ; réception des messages `routes` et `workouts` (signal ou file d'attente, au choix, documenté) ; redemande si pas de réponse au bout d'une seconde, 3 fois au plus, puis erreur lisible.
- Nouveau `engine/scripts/catalog_model.gd` (`extends RefCounted`, sans `class_name`) :
  - `route_items(items) -> Array` et `workout_items(items) -> Array` au format de `menu_model.set_items` : `label` (nom, longueur en km avec une décimale, « boucle » le cas échéant ; durée en min pour un entraînement), `enabled` (`ready` ou `outdated` pour un parcours, `selectable` pour un entraînement), `detail` (« à compiler », « à recompiler », message d'erreur court) ;
  - tri : parcours prêts d'abord puis par nom ; entraînements par durée ;
  - élément « Rouler sans entraînement (SIM) » en tête de la liste des entraînements (`select_workout` avec `null`).
- `fake_core.py` : option `--catalog FICHIER.json` qui répond aux deux listes (et peut perdre la première réponse, pour tester la redemande).
- Test sans écran : le faux core répond, le modèle de menu reçoit les éléments, une suite d'événements Click mène à `select_route` puis `select_workout` puis `start`.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/catalog_model.gd`, `engine/tests/unit/test_catalog_model.gd`, `engine/tests/test_menu_ipc.gd` (avec le faux core), données de test sous `engine/tests/data/`.
- **Modifiés :** `engine/scripts/ipc_client.gd`, `engine/tests/fake_core.py`, `engine/tests/run_engine_tests.sh` (une étape), `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, scènes, scripts de rendu (E3, E4, N6), `menu_model.gd` (lecture seule ; un manque se signale).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Catalogue de test (2 prêts, 1 à compiler, 1 invalide) : 4 éléments, focus jamais sur les deux derniers, `detail` affiché.
3. Première réponse perdue : la redemande aboutit ; trois pertes : erreur lisible, menu toujours navigable (liste vide « Aucun parcours »).
4. Scénario complet au Click : `select_route` du 2ᵉ parcours, entraînement choisi, `start` ; les `cmd_id` reçus par le faux core sont croissants et acquittés.
5. Aucun nœud créé par `catalog_model.gd` (`Performance.OBJECT_NODE_COUNT`).

## 8. Hors périmètre

- Affichage des menus (N6).
- Côté core (N2).

## 9. Livraison (25 octobre 2026, PR #163)

- Code et tests fusionnés sur `main` par la PR #163 (issue #102 fermée) ; détail dans la description de la PR et dans `docs/SUIVI_AVANCEMENT.md`.
