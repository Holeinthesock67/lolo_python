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
