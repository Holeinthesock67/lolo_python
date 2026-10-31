# Lot O26 – Réglages manquants : décor vivant, relief exagéré, ressenti du vent

## 1. Objectif

Audit des options du 31 octobre (`docs/AUDIT_OPTIONS_MENUS_2026-10-31.md`, validé par le propriétaire) : trois réglages utiles au joueur n'existaient que dans `config.toml`. Le guide demandait même d'éditer le fichier pour couper le décor vivant. Deux légendes s'affichaient avec leur valeur technique : le mode du vent et le thème par défaut.

## 2. Spécification

| # | Règle |
| --- | --- |
| O26-1 | Réglages › Graphisme gagne « Décor vivant » (`render.living`, oui / non) et « Relief exagéré » (`render.visual_grade_scale`, de 100 à 300 % par pas de 25, 250 % par défaut). Réglages › Vent gagne « Ressenti du vent » (`wind.feel` : par la pente, ou par le trainer, à l'essai). |
| O26-2 | Deux règles de forme valent pour toutes les clés (`settings.py`) : un booléen du fichier est un choix `on` / `off` au menu ; `Setting.scale` affiche un nombre à virgule en entier (2,5 → 250 %) et le divise à l'écriture. Pas de cas particulier par clé. |
| O26-3 | Décor vivant et relief sont passés par le lanceur à l'engine : `applies` = `relaunch` (nouvelle valeur du contrat, révision 1.5). La carte du réglage dit « S'applique au prochain lancement d'OpenRide ». Quand l'une de ces valeurs diffère de celle du lancement, le sous-écran se termine par « Relancer OpenRide maintenant » (détail : les réglages concernés), qui relance par le code 64 comme l'écran Appareils. |
| O26-4 | Légendes en français : vent coupé, constant, en rafales, celui du thème ; thème « par défaut » ; décor vivant oui, non (rendu de la 1.0) ; unité du plafond du vent « pts de pente ». |
| O26-5 | Le guide ne demande plus d'éditer `config.toml` ; le garde-fou X53 refuse désormais toute phrase « écrivez dans `~/OpenRide/…` » sans raison écrite. Les trois clés quittent `PENDING_KEYS`. |

## 3. Contrat

`docs/contracts/ipc_v1.md` et `settings.schema.json` : valeur `relaunch` de `applies`, booléens en `on` / `off`, échelle des nombres à virgule ; 28 réglages, sous le plafond de 32.

## 4. Fichiers

- Core : `settings.py` ; `config.py` (`PENDING_KEYS`).
- Engine : `settings_view_model.gd` (légendes, `launch_values`, ligne « Relancer »), `menu_flow.gd`.
- Docs : contrat, schéma, `GUIDE_UTILISATION.md`, `SRS_v1.1.md` §11, `CHANGELOG.md`, `scripts/config.example.toml`.
- Tests : `core/tests/test_settings.py`, `core/tests/test_options_menus.py`, `engine/tests/unit/test_menu_flow.gd` ; bancs des menus `reglages` et `persistance`.

## 5. Critères d'acceptation

1. `settings` contient les trois réglages ; écrire « non » met `living = false`, écrire 150 % met `visual_grade_scale = 1.5`.
2. Après un changement de décor vivant, « Relancer OpenRide maintenant » apparaît, et le relancement applique la valeur.
3. Sur le PC (fil de fusion) : relief à 100 % puis 250 % sur une montée, captures en low, medium et high à valider.
