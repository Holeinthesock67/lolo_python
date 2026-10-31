# Lot V3b – Pièces : gains, prix, achats, solde et vies du mode Cyber-Rogue

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Pièces : gains, prix, achats, solde, vies du mode Cyber-Rogue | Python | V2, V3, V4 | Petite | **Livré le 27 octobre** (PR #281, issue #242) ; branchement par V11 |

## 1. Objectif

Faire gagner des pièces en roulant, en même temps que l'expérience, et les dépenser au Garage (équipement) et dans le mode Cyber-Rogue (vies). Le solde se recalcule toujours : pièces gagnées d'après les journaux (V2) moins pièces dépensées d'après le profil (V4). Module pur, testé en pytest.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_V.md` §2.1 bis et §2.2 (déblocage) ; `docs/2.0/PLAN_SERIE_R.md` lot R9 (usage des vies).
2. Code : `progression.py` (V2), `equipment.py` (V3), `profile.py` (V4).

## 3. Prérequis

V2, V3 et V4 fusionnés.

## 4. Travail demandé

### 4.1 Gains (`[coins]` du fichier `progression.toml`)

Pièces à l'effort (V-Q10, décision du propriétaire du 27 octobre) : `effort = [[0, 0.25], [55, 0.5], [75, 1.0], [90, 1.5], [105, 2.0]]`, zones `[seuil en % de la FTP, pièces par minute]` appliquées à chaque seconde enregistrée selon sa puissance, en SIM comme en ERG (la distance ne compte pas). FTP : celle de l'en-tête du journal (`ftp_w`, écrite par V11) ou, à défaut, celle de `config.toml`. Puis `per_segment = 5`, `per_segment_pr = 10` (record personnel sur le segment), `per_power_record = 15` (record de puissance moyenne sur 5 s, 1, 5 ou 20 min battu par rapport aux séances comptées précédentes ; la première valeur connue n'est pas un record), `per_jersey = 20`, `rogue_boss_default = 10` et table `[coins.rogue_boss]` (10 à 50 selon le boss, la Chimère centrale à 50), `life_price = 30`. Mêmes règles d'éligibilité que l'expérience (séance de 5 min au moins, ni rejeu ni simulation). Arrondi à l'entier inférieur par séance.

### 4.2 Fonctions

- `session_coins(facts, table) -> int` et `earned_coins(progress) -> int` (somme sur les séances éligibles de `recompute`) ; `power_records(progress)` et `coins_by_session(progress, table)` pour les primes de records de puissance.
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
2. Une heure à 66 % de la FTP : 30 pièces ; à 82 % : 60 pièces, en SIM comme en ERG et quelle que soit la distance ; séance refusée : 0.
3. Achat au niveau requis avec le solde suffisant : solde diminué du prix, pièce `owned` ; achat sous le niveau : `item_locked` ; solde insuffisant : `not_enough_coins`, profil inchangé.
4. Profil effacé : solde = toutes les pièces gagnées, achats perdus mais pièces rendues (aucune perte pour le cycliste).
5. Vie achetée puis utilisée : `lives.bought` et `lives.used` à 1, solde diminué de 30 ; `use_life` sans vie : refusé.

## 8. Hors périmètre

Usage des vies dans le mode Cyber-Rogue (R9), commandes du menu (T1, V11), affichage (V8, V9).

## 9. Livraison (26 octobre 2026, issue #242)

- Code et tests : `coins.py`, section `[coins]` de `data/progression.toml`, solde affiché par `openride-core xp`, `core/tests/test_coins.py` (24 tests).
- Pièces à l'effort (V-Q10, 27 octobre) : `coins.effort_rate` et `effort_coins` ; le journal lu par `progression.session_facts` donne l'histogramme de puissance (`power_s`, pas de 10 W) et la FTP de l'en-tête (`ftp_w`) ; `coin_table(table, ftp_w)` reçoit la FTP de `config.toml`.
- `openride-core xp` lit le profil sans le réparer (`profile.peek_profile`) : la commande n'écrit toujours rien.
- Codes de refus de `buy` : `item_unknown`, `already_owned`, `item_locked`, `not_enough_coins` (les deux derniers sont ceux du contrat T1) ; `use_life` sans vie : `no_life`.

