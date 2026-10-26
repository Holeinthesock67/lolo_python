# Lot V3b – Pièces : gains, prix, achats, solde et vies du mode Cyber-Rogue

## 1. Objectif

Faire gagner des pièces en roulant, en même temps que l'expérience, et les dépenser au Garage (équipement) et dans le mode Cyber-Rogue (vies). Le solde se recalcule toujours : pièces gagnées d'après les journaux (V2) moins pièces dépensées d'après le profil (V4). Module pur, testé en pytest.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_V.md` §2.1 bis et §2.2 (déblocage) ; `docs/2.0/PLAN_SERIE_R.md` lot R9 (usage des vies).
2. Code : `progression.py` (V2), `equipment.py` (V3), `profile.py` (V4).

## 3. Prérequis

V2, V3 et V4 fusionnés.

## 4. Travail demandé

### 4.1 Gains (`[coins]` du fichier `progression.toml`)

`per_km = 1`, `per_segment = 5`, `per_jersey = 20`, `rogue_boss_default = 10` et table `[coins.rogue_boss]` (10 à 50 selon le boss, la Chimère centrale à 50), `per_erg_min = 0.5` (V-Q10 : le plan ne donne pas de gain pour l'ERG ; 0,5 pièce par minute vaut 1 pièce par km à 30 km/h), `life_price = 30`. Mêmes règles d'éligibilité que l'expérience (séance de 5 min au moins, ni rejeu ni simulation). Arrondi à l'entier inférieur par séance.

### 4.2 Fonctions

- `session_coins(facts, table) -> int` et `earned_coins(progress) -> int` (somme sur les séances éligibles de `recompute`).
- `balance(progress, profile) -> int` : gagnées − achats − vies achetées ; jamais négatif à l'affichage (un solde négatif, possible si le fichier de données a baissé les gains, bloque les achats sans rien retirer).
- `item_state(item, progress, profile) -> "locked" | "buyable" | "owned" | "equipped"` : possédée si pièce par défaut, achetée ou offerte par un défi réussi ; achetable si le niveau est atteint ; verrouillée sinon (une pièce offerte par défi seulement, sans niveau ni prix, reste verrouillée jusqu'au défi).
- `owned_items(progress, profile, catalogue) -> set[str]` (passé à `profile.equip`).
- `buy(item_id, progress, profile, catalogue, ts)` : refuse `item_locked` (niveau non atteint ou pièce de défi), `already_owned`, `not_enough_coins` ; sinon enregistre l'achat dans le profil (V4) et renvoie le nouveau solde.
- `buy_life(progress, profile, table)` et `use_life(profile)` pour la série R (R9 décide quand une vie sert).

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/coins.py`, `core/tests/test_coins.py`.
- **Modifiés :** `core/src/openride_core/data/progression.toml` (`[coins]`), `tools/xp.py` (solde affiché par `openride-core xp`), `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** `session.py`, l'IPC, l'engine, le code de la série R.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Séance de 30 km : 30 pièces ; ERG de 60 min : 30 pièces ; séance refusée : 0.
3. Achat au niveau requis avec le solde suffisant : solde diminué du prix, pièce `owned` ; achat sous le niveau : `item_locked` ; solde insuffisant : `not_enough_coins`, profil inchangé.
4. Profil effacé : solde = toutes les pièces gagnées, achats perdus mais pièces rendues (aucune perte pour le cycliste).
5. Vie achetée puis utilisée : `lives.bought` et `lives.used` à 1, solde diminué de 30 ; `use_life` sans vie : refusé.

## 8. Hors périmètre

Usage des vies dans le mode Cyber-Rogue (R9), commandes du menu (V1, V11), affichage (V8, V9).

## 9. Livraison (26 octobre 2026, issue #242)

- Code et tests : `coins.py`, section `[coins]` de `data/progression.toml`, solde affiché par `openride-core xp`, `core/tests/test_coins.py` (16 tests).
- En ERG, comme pour l'expérience (V-Q7), les minutes remplacent la distance : 0,5 pièce par minute au lieu d'1 par km.
- `openride-core xp` lit le profil sans le réparer (`profile.peek_profile`) : la commande n'écrit toujours rien.
- Codes de refus de `buy` : `item_unknown`, `already_owned`, `item_locked`, `not_enough_coins` (les deux derniers sont ceux du contrat V1) ; `use_life` sans vie : `no_life`.

