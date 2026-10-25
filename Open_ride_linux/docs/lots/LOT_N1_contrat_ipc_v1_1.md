# Lot N1 – Contrat IPC v1.1 : listes des parcours et des entraînements, état des appareils, bilan enrichi

## 1. Objectif

Le menu piloté au Click (lot N6) doit remplacer `--autostart`. Pour cela, l'engine doit obtenir du core la liste des parcours et des entraînements, l'état des appareils et un bilan de fin de séance plus riche que le `summary` actuel. Ce lot écrit ces ajouts dans le contrat IPC et ses schémas JSON, **sans changer `v`** (ajouts compatibles, contrat §8).

**Lot interne : la forme du contrat est une décision du propriétaire.** Le cahier propose une forme complète, prête à valider ; une fois le contrat fusionné, les lots N2, N3, N5 et N8 deviennent délégables.

## 2. À lire

1. `docs/contracts/ipc_v1.md` (tout), `docs/contracts/ipc/` (schémas existants).
2. `docs/SRS_v1.1.md` §4.5 (navigation), §7 (menu des parcours, « à compiler »), §13.
3. Code : `core/src/openride_core/catalog.py` (`RouteEntry`, statuts), `core/src/openride_core/workout.py` (`WorkoutInfo`), `core/src/openride_core/tools/session_summary.py` (NP, IF, TSS), `engine/scripts/menu_model.gd` (`set_items`).

## 3. Prérequis

Aucun pour la rédaction. La fusion attend l'accord du propriétaire sur les questions du §4.6.

## 4. Proposition

### 4.1 Listes

| Message | Sens | Champs |
| --- | --- | --- |
| commande `list_routes` | engine vers core | `args` : `{}` |
| commande `list_workouts` | engine vers core | `args` : `{}` |
| `routes` | core vers engine | `request_cmd_id`, `part`, `parts`, `items` (liste), `truncated` (booléen) |
| `workouts` | core vers engine | `request_cmd_id`, `part`, `parts`, `items` (liste), `truncated` (booléen) |

- Élément de `routes` : `id`, `name`, `status` (`ready`, `to_compile`, `outdated`, `invalid`, valeurs de `catalog.py`), `length_m` (nombre ou `null`), `route_type` (`open`, `loop`, `out_and_back` ou `null`), `has_terrain`, `error` (chaîne ou `null`).
- Élément de `workouts` : `id`, `name`, `duration_s`, `block_count`, `selectable`, `error` (chaîne ou `null`), `profile` (au plus 30 triplets `[durée_s, fraction de FTP au début, fraction à la fin]`, pour l'aperçu ; `profile_truncated` au-delà).
- Au plus 200 éléments au total (`truncated` vrai au-delà), en une ou plusieurs parties de 60 000 octets au plus (exception à la limite de 1 400 octets, sur `127.0.0.1` seulement).
- Fiabilité : la commande suit la règle du §4 (renvoi jusqu'à `last_cmd_id`). La réponse peut se perdre : l'engine redemande si aucun `routes` ou `workouts` portant son `request_cmd_id` n'arrive dans la seconde (au plus 3 fois). Le core répond à chaque demande, y compris un `cmd_id` déjà traité.
- Le core ne lit le disque qu'à la demande, hors de la boucle à 50 Hz (fil ou tâche séparée), et répond dans les 500 ms pour 200 parcours.

### 4.2 État des appareils

Champ facultatif `devices` de la trame `state`, envoyé une fois par seconde (une trame sur 30) et à chaque changement :

| Clé | Contenu |
| --- | --- |
| `trainer` | `{status, name, address}` ; `status` reprend `trainer_status` |
| `click` | liste de `{side, status, battery_pct}` ; `side` : `plus`, `minus` ou `single` ; `status` : `CONNECTED`, `SEARCHING`, `LOST` ; `battery_pct` entier ou `null` |
| `hr` | `{status, source, battery_pct}` ; `source` : `strap`, `trainer` ou `null` ; `status` : `CONNECTED`, `SEARCHING`, `LOST`, `NONE` |

`trainer_status` et `input_status` restent présents et inchangés (lecteurs v1).

### 4.3 Bilan enrichi

Champs facultatifs ajoutés à `summary` : `np_w`, `intensity_factor` (rapport, par exemple 0,85), `tss`, `elevation_gain_m`, `avg_cadence_rpm`, `avg_hr_bpm`, `max_power_w`, `blocks` (en ERG : au plus 24 triplets `[index, puissance moyenne, cible moyenne]`, `blocks_truncated` au-delà). Mêmes définitions que `openride-core summary` (lot K7) ; `null` quand la donnée manque.

### 4.4 Bots

Le champ `bots` déjà annoncé au §3 est précisé : au plus 5 éléments `{id, name, s, v, kind}` (4 bots et un fantôme, lot N9), `kind` valant `constant` ou `ghost`, `id` de 8 caractères et `name` de 16 au plus, pour que la trame la plus chargée tienne dans 1 400 octets.

### 4.5 Reprise après un plantage du core

Nouvelle valeur `core_restarted` de `pause_reason` : le core relancé par le lanceur (lot N8) reprend la séance du journal en pause, avec `t` et `s` restaurés. L'engine affiche « Séance reprise après un incident » et attend `resume`, comme après `engine_lost`.

### 4.6 Questions pour le propriétaire

1. Les listes passent-elles par l'IPC (proposition) ou l'engine lit-il lui-même `~/.local/share/openride/routes/` et `~/OpenRide/Workouts/` ? Proposition : IPC, une seule source de vérité (le core), pas de lecture de `.zwo` en GDScript.
2. `devices` dans `state` (proposition) ou message séparé `devices` à 1 Hz ?
3. Compilation d'un GPX depuis le menu : reportée (le lanceur compile les traces nouvelles au démarrage, lot N11) ou commande `compile_route` avec progression dès la v1.1 ? Proposition : reportée.

## 5. Fichiers concernés

- **Modifiés :** `docs/contracts/ipc_v1.md` (§3, §4, §5, journal des changements), `docs/contracts/ipc/state.schema.json`, `docs/contracts/ipc/cmd.schema.json`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `docs/contracts/ipc/routes.schema.json`, `docs/contracts/ipc/workouts.schema.json`, avec trames d'exemple.
- **Interdits :** tout le code (N2, N3, N5).

## 6. Modifications de contrat autorisées

Celles du §4, une fois validées par le propriétaire. `v` reste 1.

## 7. Critères d'acceptation

1. `pytest -q` passe dans `core/` (validation des schémas et des trames d'exemple par `test_docs_coherence.py`).
2. Chaque nouveau message a un schéma et au moins une trame d'exemple valide ; une trame v1 sans `devices` reste valide.
3. Journal des changements du contrat complété (date, ajouts compatibles).
4. Accord écrit du propriétaire sur les trois questions du §4.6.

## 8. Hors périmètre

- Implémentation côté core (N2, N8, N9) et côté engine (N3, N5, N6).
- Compilation depuis le menu, si le propriétaire la reporte.

## 9. Livraison (24 octobre 2026)

Le propriétaire a validé les trois propositions du §4.6 le 24 octobre à 21 h 26 : listes par l'IPC, `devices` dans `state`, compilation depuis le menu reportée (lot N11).

- `docs/contracts/ipc_v1.md` : révision 1.1 (§2 taille des listes, §3 `devices`, bilan enrichi et `bots`, §4 `list_routes`, `list_workouts`, `routes`, `workouts`, §6 plantage du core, §7 trames d'exemple, §8 journal).
- Schémas : `state.schema.json` et `cmd.schema.json` complétés, `routes.schema.json` et `workouts.schema.json` nouveaux.
- `core/tests/test_contract_ipc.py` : trames d'exemple v1.1 validées, contrôles négatifs, trame d'état la plus chargée (ERG, `devices`, 5 bots : 1 396 octets) et bilan complet sous 1 400 octets, listes de 200 éléments sous 60 000 octets par partie.
- Écarts avec la proposition initiale : `if_pct` devient `intensity_factor` (un rapport, comme `openride-core summary`) ; le profil passe de 60 couples à 30 triplets (début et fin de chaque bloc, pour les rampes) ; les listes se découpent en parties ; les bots sont limités à 5.
