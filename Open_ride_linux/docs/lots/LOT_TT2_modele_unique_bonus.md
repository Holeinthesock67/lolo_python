# Lot TT2 – Modèle unique des bonus

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série TT : core, modèle unique de bonus décrit par des données dans `powerups.py` (effets du Grand Prix compris), tirage selon le contexte, refus motivé ; Plume, Casque, Puissance, Enclume | Python | TT1, T6, T7, GP1 | Moyenne | Prêt (version 4.0) |

Série TT (bonus tactiques, version 4.0). Plan de la série : `docs/4.0/PLAN_SERIE_TT.md`, recommandations retenues par le propriétaire le 29 octobre (« ok pour tout », §6 du plan). Cahier rédigé le 8 novembre 2026 (le plan les annonçait, aucun n'existait).

## 1. Objectif

Remplacer les trois bonus codés de la série T par une table de données unique : un bonus = un effet, un facteur, une durée, des conditions. Aucun bonus n'a de branche de code à lui.

## 2. À lire

Plan §2 et §3 ; `core/src/openride_core/powerups.py` (T6) ; `core/src/openride_core/grandprix/effects.py` (lignes `EffectSpec` du lot GP1, écrites en attendant TT2) ; `docs/lots/LOT_GP1_objets_core.md` §3 ; `core/src/openride_core/wind.py` (`grade_offset_pct`).

## 3. Travail demandé

- Table unique dans `powerups.py` : effets `mass`, `cda`, `power`, `draft`, `crr`, `breakaway` du plan, **plus les effets du Grand Prix** (`kick`, `slip`, `speed_floor`, `cap`, `immune`, `wind`) déplacés depuis `grandprix/effects.py` sans être réécrits ; `grandprix/` lit ensuite la même table (un seul système, décision du plan GP).
- Plume (`feather`, masse × 0,90, 20 s), Casque (`aero`), Puissance (`power`), Enclume (`anvil`, masse × 1,6, refusée au-dessus de −1,5 %, suspendue au-dessus de −0,5 %).
- Tirage qui exclut les bonus inutiles (conditions du plan §3) ; jeux `classiques` et `tactiques`.
- Refus motivé : réserve gardée, champ `refused`, ligne `powerup` au journal avec la raison.
- Supplément de pente SIM calculé avec la **masse de base** (l'Enclume et la Plume ne se sentent pas au trainer).
- `~/OpenRide/powerups.toml` : une section par bonus, bornes par bonus.

## 4. Critères d'acceptation

1. Avec `off`, séance identique au bit près ; avec `classiques`, identique à la 2.0 (test de non-régression sur une séance rejouée).
2. Tests du Grand Prix verts sans changement de comportement.
3. Gain de chaque bonus dans son terrain idéal entre 1,5 et 2,5 s (test sur `physics.py`).

## 5. Fichiers touchés

`core/src/openride_core/powerups.py`, `core/src/openride_core/grandprix/effects.py`, `core/src/openride_core/classic.py`, `core/tests/test_powerups*.py`.
