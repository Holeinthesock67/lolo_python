# Lot GP9 – Menu : entrée du mode, réglages et objets

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : entrée « Grand Prix des objets » à l'accueil, écran de réglages et écran des objets désactivables | GDScript | GP2 | Petite | En revue (version 4.0 proposée) |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Tout régler depuis le menu, sans ligne de commande.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` §4.4 ; `engine/scripts/menu_flow.gd` ; écran des règles du Mode WTF (WTF3).

## 3. Travail demandé

- Côté core (point A2 des oublis du 8 novembre) : passer `grandprix` de `ipc_server.PENDING_MODES` à `CORE_MODES` (annoncé dans `hello_ack.config.modes`) et remettre les cinq réglages `grandprix.*` de `config.PENDING_KEYS` dans `settings.SETTINGS`, après ceux du Dernier survivant ; tests `test_conformite`, `test_contract_ipc` et `test_grandprix_session` à remettre en conséquence.
- Entrée visible quand le core annonce le mode ; parcours (circuit et tours, ou distance) ; réglages du §4.4 ; une case par objet ; « Lancer ».
- Navigation au Click et au clavier selon le plan des boutons (§7.1), sans exception.
- Scénario `menu_bench` du mode.

## 4. Critères d'acceptation

1. Réglages repris à la séance suivante.
2. Test `test_options_menus` à jour : chaque réglage `[grandprix]` atteignable par le menu.

## Livraison

Livré le 12 novembre 2026 (version 4.0 proposée). Core : `grandprix` passe de `ipc_server.PENDING_MODES` (vide) à `CORE_MODES`, les cinq réglages `grandprix.*` quittent `config.PENDING_KEYS` (vide) pour `settings.SETTINGS`, après ceux du Dernier survivant ; `test_conformite`, `test_contract_ipc` et `test_grandprix_session` remis en conséquence ; `test_options_menus` passe sans clé en attente.

Engine : « Grand Prix des objets » à l'accueil quand le core l'annonce, après le Dernier survivant (`menu_model.gd`). L'écran Prêt des modes à réglages est commun aux deux modes (`MenuModel.SETTINGS_MODES`, `prepare_settings_mode`, `set_mode_ready` ; `menu_flow.gd` `_refresh_mode_ready`), sans cas particulier : « Lancer » avec la longueur de la course (« 3 tours, 9,0 km » sur un circuit, « course de 10 km » en ligne, grisé et expliqué sur la ligne d'état quand le parcours en ligne est trop court), « Changer de parcours », puis adversaires, tours (circuit) ou distance (en ligne), niveau des bots, chaos et écart des boîtes modifiés en place par `set_setting`, puis « Objets ». L'écran des objets (`grandprix/gp_items_menu_model.gd`) a une case par objet, comme les règles du Mode WTF : `list_mode_options` à l'ouverture, un `set_mode_option` par objet basculé, « Tout activer », réponse `mode_options` (nouveau signal de `ipc_client.gd`) ; Y revient à l'écran Prêt. `start` part avec `mode` « grandprix » sans `bots`. Navigation au Click et au clavier par les mêmes touches que les autres écrans (§7.1), sans exception.

Tests : `engine/tests/unit/test_grandprix_menu.gd` et scénario `engine/tests/menu_scenarios/grand_prix.json` (distance ramenée à 5 km sur le parcours de démo, un objet coupé, départ du mode au journal du core). Guide d'utilisation : paragraphe « Grand Prix des objets ». Reste : captures du menu en low, medium et high sur le PC, à valider par le propriétaire.
