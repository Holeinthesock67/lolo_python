# Lot BA1 – Gestes des bots écrits et entendus

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Quand un bot voisin attaque, suit une attaque ou lance son sprint : une ligne en mots dans le bandeau et un son court, dans tous les modes à bots | Python, GDScript | Y10, T12, CR1 (livrés) | Petite | En revue (PR à valider : captures du bandeau) |

## 1. Objectif

Essai du propriétaire du 22 novembre en mode Course : « rien n'indique quand un bot utilise un boost (ni mot, ni
son, ni effet visuel) ». Vérifié dans le code : les bots ne prennent jamais de bonus ; le « boost » est une
**attaque** (`bot_tactics`, lot Y10 : 1,15 à 1,30 × CP quelques secondes, en montée ou au dernier kilomètre d'un
sprint), une **réponse** à un départ, ou le **pic du sprint** d'un profil (lot T12). Le core ne les envoyait pas.

Règles : mots écrits (jamais la couleur seule), un son, une seule règle pour tous les modes à bots, pas de
consigne (on dit ce que fait le bot, jamais ce que doit faire le cycliste).

## 2. La règle

| # | Règle |
| --- | --- |
| BA1-1 | **Core.** `ProfileBot.move()` : `attack` pendant une attaque, `respond` quand il suit un départ, `sprint` au pic de son sprint ; champ facultatif `move` des éléments de `bots` (révision 1.35, numéro provisoire), absent sans geste. Peloton allégé : seulement pour les 5 bots les plus proches (`LIGHT_DROPPED`). |
| BA1-2 | **Engine.** `bot_moves_model.gd` : au **début** d'un geste d'un bot à moins de 250 m, une ligne dans le bandeau d'information (clé `bot_move`, 3 s) : « Grimpeur attaque, 40 m devant », « Rouleur suit l'attaque, 12 m derrière », « Sprinteur lance le sprint, à ta hauteur », et le son `bot_attack` (trois notes montantes brèves). Attaque avant sprint avant réponse ; au plus une ligne toutes les 4 s ; jamais le fantôme ; seulement en séance qui roule, hors Cyber-Rogue. |
| BA1-3 | **Contrat.** Ajout compatible (journal de `ipc_v1.md`, schéma `state.schema.json`) ; un engine plus ancien ignore `move`. Numéro 1.35 provisoire : à renuméroter au-dessus du `CONTRACT_REV` de `main` à la fusion. |

## 3. Fichiers

`core/src/openride_core/bots.py`, `ipc_server.py`, `ipc_budget.py` ; `engine/scripts/bot_moves_model.gd` (nouveau),
`main.gd`, `banner.gd`, `event_sounds_model.gd` ; tests `core/tests/test_bot_move.py` (nouveau), `test_contract_ipc.py`,
`engine/tests/unit/test_bot_moves_model.gd` (nouveau), scénario du banc des menus `ba1_attaque` (nouveau) ;
`docs/contracts/ipc_v1.md`, `docs/contracts/ipc/state.schema.json`, `docs/GUIDE_UTILISATION.md`, `CHANGELOG.md`.

## 4. Recette PC (catégorie : logique)

HUD seul (une ligne du bandeau existant) et un champ du core : banc PC medium seul, captures low, medium et high
du bandeau à valider par le propriétaire.

```bash
cd ~/Games/lolo_python/Open_ride_linux
python3 engine/tests/menu_bench.py --scenario ba1_attaque --scenario course --qualite medium --captures ecrans
```

Capture à valider : `ba1_bandeau`. Pas d'essai vélo dédié : le ressenti se juge à la prochaine Course.

## Livraison

22 novembre 2026, préparé pendant la pause des travaux (après l'essai de 14 h 30), poussé à la reprise.
