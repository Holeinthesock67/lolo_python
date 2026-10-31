# Lot X53 – Garde-fou des options hors menu

## 1. Objectif

Audit des options du 31 octobre (`docs/AUDIT_OPTIONS_MENUS_2026-10-31.md`, validé par le propriétaire) : le gravel et la ceinture cardio étaient lus par le code sans être réglables dans un menu, et rien ne l'a signalé. Principe du propriétaire : à la fin, le jeu s'utilise sans ligne de commande ni fichier à modifier à la main. Ce lot ajoute un test qui échoue dès qu'une option arrive sans menu ni raison écrite.

## 2. Règles vérifiées par `core/tests/test_options_menus.py`

| # | Règle |
| --- | --- |
| X53-1 | Toute clé de `Config` est au menu Réglages (`settings.SETTINGS`) ou rangée une seule fois dans `config.py` : `OTHER_SCREEN_KEYS` (autre écran, vérifié : l'écran Appareils écrit bien la clé), `EXPERT_KEYS` (réglage fin documenté), `DEV_KEYS` (outil d'essai ou valeur posée par le lanceur), `PENDING_KEYS` (à relier, avec le numéro du lot). Chaque entrée a sa raison ; une entrée qui ne correspond plus à une clé est signalée. |
| X53-2 | Tout argument lu par `engine/scripts/engine_args.gd` est passé par `launcher.build_supervisor` depuis la configuration, ou rangé dans `launcher.ENGINE_ARGS_NOT_FROM_CONFIG` avec sa raison, jamais les deux. |
| X53-3 | Toute commande citée entre accents graves dans `docs/GUIDE_UTILISATION.md` (`openride`, `openride-core`, `openride-compiler`, `python -m`) a une raison ou le lot qui la remplacera par un menu (`GUIDE_COMMANDS` du test) ; même chose pour les éditions de `config.toml` demandées (`GUIDE_FILE_EDITS`). Une ligne qui n'est plus citée doit être retirée. |

Un lot qui relie une option au menu la retire de `PENDING_KEYS`, de `ENGINE_ARGS_NOT_FROM_CONFIG` ou des listes du guide : le test l'y oblige.

## 3. Fichiers

- `core/src/openride_core/config.py` : `OTHER_SCREEN_KEYS`, `EXPERT_KEYS`, `DEV_KEYS`, `PENDING_KEYS`.
- `core/src/openride_core/launcher.py` : `ENGINE_ARGS_NOT_FROM_CONFIG`.
- `core/tests/test_options_menus.py`, avec un test négatif par règle.

## 4. Critères d'acceptation

1. Le test passe sur `main` après O24 (la ceinture est écrite par l'écran Appareils).
2. Ajouter une clé à `Config` sans la ranger, ou un argument à l'engine, fait échouer le test avec un message qui cite la clé.
