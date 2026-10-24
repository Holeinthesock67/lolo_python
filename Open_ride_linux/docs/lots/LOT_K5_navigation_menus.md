# Lot K5 – Navigation des menus au Click (machine à états, sans affichage)

## 1. Objectif

Le menu du lot G se pilote avec deux boutons seulement (Click : + et −, appui court ou long) et au clavier. Ce lot écrit la logique de navigation, indépendante de l'affichage et du futur contrat IPC v1.1 : listes, focus, validation, retour, confirmation. Le lot G n'aura plus qu'à brancher les données (parcours, entraînements) et l'affichage.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/SRS_v1.1.md` §4.4 (appuis courts et longs), §7 (menu des parcours, « à compiler »), §13 (écrans) ; `docs/contracts/ipc_v1.md` §3 et §6 (`input`, `input_event`).
3. Code : `engine/scripts/main.gd` (touches actuelles, lecture seule), `engine/scripts/erg_view_model.gd` (style d'un modèle sans nœud).

## 3. Prérequis

Lot K1 livré.

## 4. Travail demandé

Nouveau `engine/scripts/menu_model.gd` (`extends RefCounted`, sans `class_name`), sans nœud :

- Écrans décrits par des données : `{id, title, items: [{id, label, enabled, detail}], on_back}` ; écrans de départ : accueil (Rouler, Entraînements, Réglages, Quitter), liste des parcours, liste des entraînements, confirmation (Oui / Non), écran de pause (Reprendre, Terminer et enregistrer, Abandonner).
- Entrées : `PLUS_SHORT` (suivant), `MINUS_SHORT` (précédent), `PLUS_LONG` (valider), `MINUS_LONG` (retour) ; mêmes noms que l'IPC. Le clavier se ramène à ces quatre événements.
- `handle(event: String) -> Dictionary` renvoie l'état (écran, index du focus, éléments) et une **action** éventuelle (`{"action": "select_route", "route_id": …}`, `start`, `pause`, `end_session`, `quit`…), sans rien envoyer lui-même.
- Règles : le focus saute les éléments désactivés (par exemple un parcours « à compiler » ou un entraînement invalide, qui affichent leur `detail`) ; la liste boucle ; une action destructrice (Abandonner, Quitter) passe par l'écran de confirmation ; une liste vide affiche un élément désactivé « Aucun parcours » et le retour reste possible.
- `set_items(screen_id, items)` pour injecter les listes (aujourd'hui par le test, demain par le contrat v1.1).

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/menu_model.gd`, `engine/tests/unit/test_menu_model.gd`.
- **Modifiés :** `engine/tests/README.md` (une ligne), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, `ipc_client.gd`, contrat IPC.

## 6. Modifications de contrat autorisées

Aucune. Les actions renvoyées reprennent les noms de commandes du contrat v1 quand ils existent ; les autres (`quit`, ouverture d'un écran) restent internes à l'engine.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Scénarios écrits comme suites d'événements avec l'état attendu après chacune (au moins 10) : choisir le 3ᵉ parcours et démarrer ; passer un parcours désactivé ; boucler en fin de liste ; retour depuis chaque écran ; abandon confirmé et abandon annulé ; liste vide.
3. Aucun scénario ne produit d'action quand le focus est sur un élément désactivé.
4. Événement inconnu : ignoré, état inchangé.
5. Aucun nœud créé (vérifié par `Performance.OBJECT_NODE_COUNT` avant et après).

## 8. Hors périmètre

- Affichage des menus, police, sons (G, interne).
- Messages IPC de liste (contrat v1.1, décision du propriétaire).
