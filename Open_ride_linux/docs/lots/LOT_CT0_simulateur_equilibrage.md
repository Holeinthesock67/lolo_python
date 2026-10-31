# Lot CT0 – Simulateur d'équilibrage de la Course tactique

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : simulateur d'équilibrage de la Course tactique | Python | Y10, T13 | Moyenne | Prêt (version 5.0) |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`.

## 1. Objectif

Avant tout branchement, mesurer en temps accéléré si les règles du mode donnent des courses intéressantes : personne ne gagne en restant toujours dans les roues, personne ne gagne en roulant toujours devant, l'échappée solitaire n'est pas la stratégie dominante, et chaque profil de bot (grimpeur, rouleur, sprinteur, diesel) a un terrain où il gagne.

## 2. À lire

1. `docs/5.0/PLAN_SERIE_CT.md` (décisions du propriétaire du 29 octobre), `docs/SPECIFICATION_GENERALE.md` §6.1 et §7.1, `docs/contracts/ipc_v1.md`.
2. Code : `core/src/openride_core/tools/bots_race.py` (X27), `tools/rogue_sim.py` (R7), `sim_rider.py` (cycliste virtuel et stratégies), `bots.py` (T12, T13), `draft.py`, `rogue/wbal.py`, `physics.py`.

## 3. Prérequis

Y10 (bots qui relaient, attaquent et répondent) livré ; T13 (calibrage) livré.

## 4. Travail demandé

- Outil `python -m openride_core.tools.tactical_sim` : courses de 4 bots et d'un cycliste virtuel sur un circuit généré (CT8) ou un parcours `.world`, en temps accéléré, avec les règles de CT2 à CT7 appelées par leurs modules purs (ou des bouchons tant qu'ils n'existent pas).
- Stratégies du cycliste virtuel : « suceur de roues » (jamais devant), « rouleur » (relais réguliers), « attaquant » (contre quand un bot est sous 10 % de réserve), « échappée » (seul devant dès le départ), « mixte ».
- Valeurs dans un fichier embarqué `core/src/openride_core/tactical/balance.toml`, surchargeable par `~/OpenRide/tactical_balance.toml`, sur le modèle de `rogue/balance.toml` (R7).
- Rapport Markdown `docs/5.0/RAPPORT_EQUILIBRAGE_CT0.md` : taux de victoire par stratégie et par profil, nombre de Burnouts, de catapultes et de capacités par course, écarts à l'arrivée ; 200 courses par configuration, graine fixée.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/tactical/__init__.py`, `tactical/balance.py`, `tactical/balance.toml`, `tools/tactical_sim.py`, `core/tests/test_tactical_sim.py`, `docs/5.0/RAPPORT_EQUILIBRAGE_CT0.md`.
- **Modifiés :** ce cahier, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** l'engine, le contrat IPC, `session.py`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe ; 200 courses en moins de 60 s sur le PC de la CI.
2. Aucune stratégie ne gagne plus de 45 % des courses avec les valeurs retenues ; l'échappée solitaire gagne moins de 20 %.
3. Chaque profil de bot gagne au moins une configuration de circuit.
4. Même graine, même rapport à l'octet près.

## 8. Hors périmètre

Réglage fin après la recette sur le vélo (CT12) ; IA par apprentissage.
