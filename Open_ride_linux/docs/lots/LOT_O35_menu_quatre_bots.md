# Lot O35 – Quatre bots et le fantôme au menu

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Écran Prêt : « Bot 1 » à « Bot 4 » et fantôme, comme la limite du core (4 bots + 1 fantôme) ; noms distincts pour deux bots de même puissance | GDScript + Python | O7, T13, O32 | Petite | Demandé par le propriétaire le 31 octobre ; en PR |

## 1. Objectif

Question du propriétaire du 31 octobre : « On peut utiliser maximum combien de bots à la fois ? ». Le core
accepte 4 bots (puissance constante ou profil) et un fantôme (`bots_from_menu`, `MAX_CONSTANT_BOTS`, schéma
IPC `bots` limité à 5, HUD à 5 lignes), mais l'écran Prêt n'en proposait qu'un. Le propriétaire a choisi
d'aligner le menu sur le core, puis de préparer un peloton d'une douzaine de bots (lot suivant, nouvelle
révision IPC et banc PC en low, medium et high).

## 2. Spécification

| # | Règle |
| --- | --- |
| O35-1 | L'écran Prêt montre « Bot 1 : … ». Dès que « Bot n » est choisi, une ligne « Bot n+1 : aucun » apparaît juste en dessous, jusqu'à « Bot 4 » (`MenuModel.MAX_BOTS`, la limite du core). Les identifiants des lignes sont `bot1` à `bot4`. |
| O35-2 | A long sur une ligne de bot passe au choix suivant de `BOT_CHOICES`. Revenir à « aucun » retire ce bot ; les bots suivants remontent d'une ligne. |
| O35-3 | `start` envoie les bots dans l'ordre des lignes, puis le fantôme s'il est demandé. |
| O35-4 | Derniers choix (lot O32) : jusqu'à 4 bots repris dans l'ordre ; un bot inconnu du menu est sauté, au-delà de 4 ils sont ignorés. |
| O35-5 | Core : deux bots à puissance constante de même nom deviennent « Bot 200 W », « Bot 200 W 2 », etc. (comme « Grimpeur 2 » pour les profils), pour rester distincts au HUD. |

## 3. Contrat

Aucun changement : `start.bots` acceptait déjà 4 bots et un fantôme (contrat 1.3, `last_choices` 1.5).

## 4. Fichiers

- Engine : `menu_model.gd` (`MAX_BOTS`, `bot_choices`, `last_bots`, `_cycle_bot`), `ui_icons.gd`, `menu_flow.gd` (commentaire).
- Core : `bots.py` (`bots_from_menu`, noms distincts).
- Docs : `GUIDE_UTILISATION.md`.
- Tests : engine `unit/test_menu_flow.gd` (`_test_four_bots`), `unit/test_menu_model.gd`, scénarios `sessions.json` et `derniers_choix.json` ; core `test_profile_bots.py`.

## 5. Critères d'acceptation

1. `pytest -q` passe dans `core/`, et `run_engine_tests.sh` passe.
2. Sur le PC : écran Prêt, choisir 4 bots et le fantôme, démarrer ; les 5 apparaissent au HUD et sur la route, côte à côte au départ (PR #647).

## 6. Hors périmètre

Plus de 4 bots (peloton d'une douzaine) : nouvelle révision IPC (trame `state` au-delà de 4 096 octets
ou bots allégés), HUD et banc PC low, medium et high, dans un lot séparé.
