# Lot WTF3 – Menu du mode WTF et écran des treize interrupteurs

Série WTF (mode « What the fuck », demande du propriétaire du 29 octobre 2026). Plan de la série : `docs/2.0/PLAN_SERIE_WTF.md`.

## 1. Objectif

Entrée « Mode WTF » dans le menu principal, et écran listant les treize règles (nom, phrase, interrupteur) navigable au Click, au clavier et à la souris.

## 2. À lire

`docs/PRESENTATION_MENUS.md` ; `engine/scripts/` (menus) ; message `wtf_rules` du lot WTF2.

## 3. Travail demandé

- Entrée de menu, écran des règles (une ligne par règle, + et − ou Entrée basculent), bouton « Tout allumer ».
- Scénario `menu_bench` qui coupe puis rallume une règle.

## 4. Critères d'acceptation

1. Tests Godot (`run_engine_tests`) et `menu_bench` passent.
2. Captures de l'écran montrées au propriétaire avant fusion.

## 5. Livraison (30 octobre)

- `engine/scripts/wtf/wtf_rules_model.gd` : écran des règles sans nœud (13 lignes « Nom : oui/non », « Tout allumer », « Lancer une séance WTF »), liste par défaut tant que le core n'a pas répondu, bascule affichée tout de suite puis corrigée par la réponse `wtf_rules`.
- `menu_model.gd` : entrée « Mode WTF » (quand `hello_ack.config.modes` porte `wtf`), `prepare_wtf()`, écran Prêt du mode (Démarrer, Changer les règles, parcours, bot, fantôme ; pas de passage en ERG), `start` avec `mode` « wtf ».
- `menu_flow.gd`, `main.gd`, `ipc_client.gd` : actions `list_wtf_rules` et `set_wtf_rules` (une commande `set_wtf_rule` par règle), signal `wtf_rules_received`.
- Tests : `engine/tests/unit/test_wtf_menu.gd` ; scénario `engine/tests/menu_scenarios/mode_wtf.json` (une règle coupée, `wtf.toml` écrit, Tout allumer, départ, bilan).
- Reste : captures de l'écran montrées au propriétaire (file du PC).
