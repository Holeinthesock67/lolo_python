# Lot CT14 – Profil de bot « Baroudeur »

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : profil de bot « Baroudeur » (échappée au long cours) dans le jeu | Python, GDScript | CT0, CT1 | Petite | Prêt (version 5.0, idée retenue par le propriétaire le 7 novembre) |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`.

## 1. Objectif

Faire vivre l'échappée : dans le rapport CT0 avant ce profil, l'échappée solitaire ne gagnait jamais. Le baroudeur est un rouleur endurant qui part devant tôt dans la course et oblige le groupe à rouler pour le reprendre. Le lot CT0 l'a ajouté au simulateur seulement (`tools/tactical_sim.py`, `BAROUDEUR`) ; ce lot le met dans le jeu.

## 2. À lire

`docs/5.0/RAPPORT_EQUILIBRAGE_CT0.md`, `tools/tactical_sim.py` (`BAROUDEUR`, `_bot_power`), `bots.py` (`PROFILES`, T12), `bot_tactics.py` (`Character`, Y10), `docs/contracts/ipc_v1.md` (valeurs de `profile`), `engine/scripts/menu_model.gd`, `bot_hud_model.gd`.

## 3. Prérequis

CT0 fusionné ; CT1 (révision du contrat de la série CT).

## 4. Travail demandé

- `bots.PROFILES["baroudeur"]` : valeurs du simulateur (70 kg, 3,7 W/kg, W′ 22 kJ, plat 1,00, montée 0,95), le simulateur reprenant ensuite `PROFILES` sans profil à part.
- Comportement : dans `bot_tactics.py`, un champ `breakaway` de `Character` (échappée dans les 60 premiers % de la course à 1,05 × CP, jusqu'à 35 % de réserve, relancée à 80 % ; valeurs de `tactical/balance.toml`), pour tous les modes où les bots ont une tactique (`classic` compris), sans exception par mode.
- Contrat : valeur `baroudeur` de `profile` dans la révision de CT1 (`start.bots`, éléments de `bots` dans `state`).
- Engine : nom « Baroudeur » au menu des bots et au HUD ; maquette du menu validée par le propriétaire avant fusion, captures en low, medium et high.

## 5. Fichiers concernés

- **Modifiés :** `bots.py`, `bot_tactics.py`, `tools/tactical_sim.py`, `tactical/balance.toml`, `docs/contracts/ipc_v1.md` (par CT1), `menu_model.gd`, `bot_hud_model.gd` et leurs tests, ce cahier, `SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Valeur `baroudeur` de `profile`, dans la révision de CT1.

## 7. Critères d'acceptation

1. `pytest -q` et les tests de l'engine passent.
2. Le rapport CT0 régénéré reste dans ses critères ; le baroudeur gagne au moins un circuit.
3. `bots_race` : un baroudeur calibré au niveau du cycliste finit à moins de 2 % de lui (règle de X27).
4. Captures du menu et du HUD validées par le propriétaire.

## 8. Hors périmètre

D'autres profils (puncheur) : à proposer après la recette CT12.
