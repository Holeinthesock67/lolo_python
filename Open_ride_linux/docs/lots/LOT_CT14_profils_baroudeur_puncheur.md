# Lot CT14 – Profils de bot « Baroudeur » et « Puncheur »

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : profils de bot « Baroudeur » (échappée au long cours) et « Puncheur » (attaque dans les raidards) dans le jeu | Python, GDScript | CT0, CT1 | Moyenne | Prêt (version 5.0, idées retenues par le propriétaire le 7 novembre) |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`.

## 1. Objectif

Deux profils de plus, chacun avec un terrain et un geste qu'aucun autre n'a (condition posée le 7 novembre pour garder la course lisible) :
- **Baroudeur** : rouleur endurant qui part devant tôt dans la course et oblige le groupe à rouler pour le reprendre (dans le rapport CT0 d'avant, l'échappée ne gagnait jamais) ;
- **Puncheur** : attaque à 1,45 × CP dans les 600 derniers mètres d'une bosse de 1,5 km au plus ; terrain : les murs et les bosses courtes et raides (circuit `mur_final` du simulateur), entre le sprinteur et le grimpeur. Le puncheur figurait au premier plan de la série T et avait été remplacé par le rouleur le 27 octobre ; il revient ici.

Le lot CT0 les a ajoutés au simulateur seulement (`tools/tactical_sim.py`, `BAROUDEUR`, `PUNCHEUR`) ; ce lot les met dans le jeu. Si le rapport CT0 montre qu'un des deux n'a pas de terrain à lui, il est retiré plutôt qu'ajouté.

## 2. À lire

`docs/5.0/RAPPORT_EQUILIBRAGE_CT0.md`, `tools/tactical_sim.py` (`BAROUDEUR`, `PUNCHEUR`, `_bot_power`), `bots.py` (`PROFILES`, T12), `bot_tactics.py` (`Character`, Y10), `docs/contracts/ipc_v1.md` (valeurs de `profile`), `engine/scripts/menu_model.gd`, `bot_hud_model.gd`.

## 3. Prérequis

CT0 fusionné ; CT1 (révision du contrat de la série CT).

## 4. Travail demandé

- `bots.PROFILES["baroudeur"]` (70 kg, 3,75 W/kg, W′ 18 kJ, plat 1,00, montée 0,95) et `bots.PROFILES["puncheur"]` (68 kg, 3,6 W/kg, W′ 24 kJ, plat 0,95, montée 0,98) : valeurs du simulateur, qui reprend ensuite `PROFILES` sans profil à part.
- Comportement : dans `bot_tactics.py`, un champ `breakaway` de `Character` (échappée dans les 60 premiers % de la course à 1,05 × CP, jusqu'à 35 % de réserve, relancée à 80 %) et un champ `punch` (attaque dans le raidard), valeurs de `tactical/balance.toml`, pour tous les modes où les bots ont une tactique (`classic` compris), sans exception par mode.
- Contrat : valeurs `baroudeur` et `puncheur` de `profile` dans la révision de CT1 (`start.bots`, éléments de `bots` dans `state`).
- Engine : noms « Baroudeur » et « Puncheur » au menu des bots et au HUD ; maquette du menu validée par le propriétaire avant fusion, captures en low, medium et high.

## 5. Fichiers concernés

- **Modifiés :** `bots.py`, `bot_tactics.py`, `tools/tactical_sim.py`, `tactical/balance.toml`, `docs/contracts/ipc_v1.md` (par CT1), `menu_model.gd`, `bot_hud_model.gd` et leurs tests, ce cahier, `SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Valeurs `baroudeur` et `puncheur` de `profile`, dans la révision de CT1.

## 7. Critères d'acceptation

1. `pytest -q` et les tests de l'engine passent.
2. Le rapport CT0 régénéré reste dans ses critères ; le baroudeur et le puncheur sont chacun premier bot d'au moins un circuit.
3. `bots_race` : un baroudeur et un puncheur calibrés au niveau du cycliste finissent à moins de 2 % de lui (règle de X27).
4. Captures du menu et du HUD validées par le propriétaire.

## 8. Hors périmètre

D'autres profils : à proposer après la recette CT12, avec la même condition (un terrain et un geste à eux).
