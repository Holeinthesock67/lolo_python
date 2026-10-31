# Lot DS2 – Branchement du mode dans la séance et contrat IPC

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série DS : branchement du mode « Dernier survivant » dans la séance, réglages `[survivor]` et contrat IPC | Python | DS1 | Moyenne | **Livré le 31 octobre** (version 3.0) |

Série DS (mode « Dernier survivant », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/3.0/PLAN_SERIE_DS.md`.

## 1. Objectif

Brancher `SurvivorRace` dans la séance : valeur `survivor` de `start.mode`, réglages du mode, trame `state.survivor`, message `elimination`, `summary.survivor`, bots éliminés qui sortent de l'abri, joueur éliminé selon le réglage « Après élimination ».

## 2. À lire

`docs/3.0/PLAN_SERIE_DS.md` §2.3, §2.4, §4 et §6 ; `core/src/openride_core/session.py` (branchement du Mode WTF par le lot WTF2) ; `core/src/openride_core/settings.py` ; `docs/contracts/ipc_v1.md` (§2 limites, liste `bots`, `segment_result`).

## 3. Travail demandé

- `start` avec `mode` = `survivor` : refusé (`bad_args`) avec un entraînement ERG, un argument `bots`, un fantôme ou un parcours trop court hors circuit et monde ouvert ; plateau composé par le core.
- Réglages `survivor.opponents`, `survivor.spacing_km`, `survivor.spread`, `survivor.after_out` (section `[survivor]`), modifiables par `set_setting` ; `hello_ack` annonce le mode.
- Bonus, segments, records et maillots coupés dans ce mode ; journal, FIT et expérience comme une séance libre.
- Bot éliminé : retiré de l'abri et des écarts, champ `out` dans `bots`, se range (15 km/h) puis disparaît après 10 s ; joueur éliminé : séance continuée ou terminée selon `after_out`.
- Contrat : première révision libre à la fusion, ajouts compatibles du §6 du plan, tableau des révisions ; budget de trame vérifié par `python -m openride_core.ipc_budget`.

## 4. Critères d'acceptation

1. Une séance simulée complète (4 bots, cycliste virtuel) va jusqu'au vainqueur et donne un `summary.survivor` cohérent.
2. Chaque refus de `start` a son test ; aucune règle du classique ne change hors de ce mode.
3. Pire trame `state` du mode sous la limite de 4 096 octets, sans allègement.

## Livraison

Livré le 31 octobre 2026 (branche `claude/project-thread-ewr5b6-ds2`, après DS1 et DS3).

- `session.py` : `start` avec `mode` = `survivor` (plateau `ProfileBot` composé par le core, calibré comme au classique), refus `bad_args` (ERG, `ftp_test`, `plan_day`, `bots`, parcours trop court), consignes de survie des bots (DS3) à chaque pas, éliminations, bots éliminés qui se rangent (15 km/h) hors de l'abri puis retirés après 10 s, cycliste éliminé selon `survivor.after_out`, trame `survivor`, messages `elimination`, lignes `survivor_start`, `survivor` et `survivor_summary` au journal, `summary.survivor`, `set_ride_mode` vers l'ERG refusé.
- `config.py` (section `[survivor]`, réglages du profil du joueur), `settings.py` (quatre réglages dans « Séance » en attendant l'écran du mode, lot DS7), `ipc_server.py` (mode annoncé, champ `survivor`), `journal.py` (lignes de jeu).
- Contrat : `docs/contracts/ipc_v1.md`, `state.schema.json` (`survivor`, `summary.survivor`, `bots[].out`), nouveau `elimination.schema.json`.
- Tests : `core/tests/test_survivor_session.py`.

Écarts assumés : ajouts rangés dans la révision 1.5 (comme WTF2 et T12) et non dans une nouvelle révision ; `survivor.opponents` borné à 4 tant que le core limite les bots à 4 (DS8) ; le monde ouvert place les arches sur la distance roulée (pas de fin de parcours).
