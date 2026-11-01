# Lot W1 – Contrat : monde vivant, IPC du monde ouvert et dialogue avec le générateur

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Contrat : monde vivant (`live`, grille UTM, route par parties, couches par carré, `junctions.json`), IPC du monde ouvert (révision 1.5), dialogue avec `openride-worldgen` | Markdown + JSON | W0 | Petite | Livré le 27 octobre (PR #282) |

## 1. Objectif

Fixer, avant tout code de la série W, les trois contrats que les autres lots implémentent : le format du `.world` « vivant » qui s'allonge pendant la séance, les ajouts à l'IPC entre core et engine, et le dialogue entre le core et le nouveau processus `openride-worldgen`. C'est une décision du propriétaire, comme N1 et P1 : le lot rédige les ajouts, le propriétaire les valide en fusionnant.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_W.md` (en entier, surtout §4, §5 et §8), `docs/lots/00_INDEX.md`.
2. `docs/contracts/world_format_v1.md` §2 à §5 et §10, `docs/contracts/ipc_v1.md` §2 à §4 et §8, schémas de `docs/contracts/ipc/` et `docs/contracts/world/`.
3. Le rapport de mesure de W0 (dans `~/OpenRide/Cache/monde/mesures/` sur le PC, recopié en chiffres seulement dans la PR).

## 3. Prérequis

W0 livré et exécuté sur le PC (ses chiffres ne changent pas la forme du contrat, seulement les constantes notées « à confirmer »). La numérotation de l'IPC suit l'ordre fixé par le propriétaire : sur `main`, la révision 1.2 est prise par Q1 et N13 ; la proposition en attente donne 1.3 à P1 et 1.4 aux séries R, T et V. **W1 prend la révision libre suivante au moment de sa fusion (1.5 si l'ordre proposé est confirmé)** ; le format `.world` prend de même le mineur libre suivant.

## 4. Travail demandé

### 4.1 Répartition des rôles (précise le plan §5.1)

- `openride-worldgen` possède le graphe routier, le navigateur et la route engagée : il prolonge la route sur la branche par défaut et écrit les fichiers.
- Le core lit la route engagée, publie le prochain carrefour, applique le choix du cycliste (jusqu'au verrouillage) en le transmettant au générateur, et met en pause si la route connue ne suffit plus. Le core reste sans numpy.
- L'engine affiche ; il ne lit jamais la base SQLite.

### 4.2 Format du monde vivant (`world_format_v1.md`, nouveau §13)

- **Dossier :** `<cache_dir>/seances/<id>.world/`, `<id>` = `ow-<AAAAMMJJ-HHMMSS>`.
- **Origine :** coin de la grille de 5 km de la zone UTM le plus proche du départ (`E0` et `N0` multiples de 5 000). Manifeste : `live: true`, `origin_kind: "utm_grid"`, `origin` (lat, lon, alt_m du coin, `utm_zone`), `grid: {"near_m": 1000, "far_m": 5000, "e0": E0, "n0": N0}`. Ainsi les tuiles de la séance coïncident avec la grille globale : tuile proche `(ix, iz)` ↔ carré global `IX = E0/1000 + ix`, `IN = N0/1000 − iz − 1` (même règle à 5 km pour les tuiles lointaines).
- **`live.json`** (réécrit de façon atomique à chaque révision) : `revision` (entier croissant), `route` (`parts`, `length_m`, `changed_from_part`), `tiles` (`near`, `far` : listes `[ix, iz]` disponibles), `layer_tiles` (liste `[ix, iz]` dont les couches sont écrites), `status` (`ok`, `downloading`, `offline`, `missing`).
- **Route par parties :** `route/part_<k>.json`, mêmes colonnes que `route.json` plus `s0_m`. La partie `k` contient les points de `s = 1000 k` à `s = 1000 (k + 1)` inclus (bord partagé avec la suivante), au pas de 10 m. Une partie déjà publiée peut être réécrite seulement au-delà du point de verrouillage du carrefour concerné ; `changed_from_part` dit à partir d'où relire. `s` reste croissant ; le `type` est `open`.
- **Couches par carré :** `terrain/near/tile_<ix>_<iz>.f32`, `terrain/far/tile_<ix>_<iz>.f32` (format §5 inchangé) ; `buildings/`, `vegetation/`, `water/`, `poi/` : `tile_<ix>_<iz>.json`, mêmes schémas que les `chunk_<k>.json`, mais **coordonnées relatives au coin de la tuile** (`x − 1000 ix`, `z − 1000 iz`) pour que les fichiers du cache soient liés (liens symboliques) sans réécriture. `y` reste l'altitude absolue.
- **`junctions.json`** (atomique) : `revision`, liste des carrefours à moins de 3 km devant : `id` (chaîne), `s_m`, `x`, `z`, `lock_s_m` (= `s_m − 30`), `default`, `chosen`, `locked`, `branches` : `index`, `heading_deg`, `angle_deg` (relatif au cap d'arrivée, positif à droite), `road_class` (`p`, `s`, `t`, `m`, `c`, `k`, voir §4.5), `grade_pct_500m`, `dead_end`, `preview` (`x`, `y`, `z` au pas de 10 m sur 500 m, 51 points). Au plus 4 branches par carrefour (les autres sont ignorées).
- Schémas : `live.schema.json`, `route_part.schema.json`, `junctions.schema.json` dans `docs/contracts/world/` ; ajout de `live`, `origin_kind` et `grid` à `manifest.schema.json`.

### 4.3 IPC (révision 1.5, ajouts compatibles)

| Ajout | Forme |
| --- | --- |
| Commande `start_open_world` | `{lat, lon, heading_deg, nav: "ride" \| "destination" \| "loop", target: {lat, lon} ou null, loop_km: nombre ou null, seed: entier}` ; `session_state` passe à `LOADING`, puis `READY` ; `route_id` vaut `ow:<id>` |
| Commande `choose_branch` | `{junction_id, branch}` ; erreurs `branch_locked`, `unknown_junction` |
| Commandes du menu | `world_search {query}` → message `places` ; `world_map {lat, lon, radius_m}` → message `world_map` ; `world_regions {}` → message `world_regions` ; `world_pin {region_id, pinned}` |
| Messages du menu | `places`, `world_map`, `world_regions` : mêmes règles que `routes` (`request_cmd_id`, parties de 60 000 octets au plus) |
| Message `world_status` | `{phase: "dem" \| "osm" \| "tiles" \| "generate" \| "ready" \| "error", done_bytes, total_bytes ou null, squares_ready, squares_needed, message}`, sur changement et au plus 4 fois par seconde |
| Champ `open_world` de `state` | Facultatif, présent seulement en monde ouvert et absent des trames qui portent `devices` (une sur 30, l'engine garde le dernier reçu) : `rev`, `next` (prochain carrefour ou `null` : `id`, `d_m`, `default`, `chosen`, `locked`, `b` = au plus 4 triplets `[angle_deg entier, road_class, grade_pct à 0,1 près]`), `data` (`cached`, `downloading`, `offline`, `missing`) ; trame la plus chargée sous la limite de 4 096 octets de `state` (révision 1.3), `devices` compris |
| `hello_ack.config` | `open_world_dir` (dossier des séances, pour que l'engine trouve `ow:<id>`) |
| Événements `input` | Aucun nouveau : `LEFT_SHORT`, `RIGHT_SHORT` (flèches du boîtier gauche, W-Q1), `A_SHORT` et `A_LONG` existent depuis la révision 1.3 |
| `pause_reason` | `world_data` : plus de route connue devant (plan §3.6) |
| Code d'erreur | `world_unavailable` : départ hors cache sans réseau |

Choix au carrefour (W-Q1) : flèche gauche ou droite → branche voisine dans le sens de l'angle ; `A_SHORT` → branche suivante, en boucle ; `A_LONG` → valider la branche affichée tout de suite (plan de boutons, spécification générale §7.1) ; clavier ← et → dans l'engine → `choose_branch` directement ; sans appui, la branche par défaut. Tant que le lot Q6 (boîtier gauche muet après 35 à 60 s) n'est pas réglé, `A_SHORT` et le clavier sont les moyens principaux, les flèches un complément (décision D8 de l'audit IPC du 26 octobre).

Décisions de l'audit IPC du 26 octobre (rapport de la PR #288), appliquées au rebase sur les révisions 1.3 et 1.4 : `"open_world"` s'ajoute à la liste `hello_ack.config.modes` quand le core sait lancer le monde ouvert (D3) ; la limite de la trame `state` est de 4 096 octets depuis la révision 1.3 (D1), et le test de taille de W1 vérifie la trame la plus chargée, `devices` compris, sous cette limite.

### 4.4 Dialogue core ↔ générateur (`docs/contracts/worldgen_v1.md`, nouveau)

- Le core lance `openride-worldgen --session <dossier> --config <config.toml>` et lui parle en lignes JSON sur l'entrée et la sortie standard (une ligne = un message, UTF-8) ; le journal du générateur va sur sa sortie d'erreur, rangé comme celui de Godot (M8).
- Core → générateur : `open` (mêmes champs que `start_open_world`), `progress {s_m, v_mps}` (2 fois par seconde), `choose {junction_id, branch}`, `close`.
- Générateur → core : `status` (champs de `world_status`), `revision {rev, length_m, changed_from_part, junctions}`, `error {code, message}`, `closed`.
- Le générateur écrit d'abord les fichiers (atomiques), puis envoie `revision`. Le core ne lit ces fichiers que hors de la boucle à 50 Hz.
- Horizon : `length_m − s_m ≥ horizon_m` (3 000 m) visé ; amorces de 500 m de chaque branche calculées avant que le carrefour entre dans les 300 m.

### 4.5 Classes de route et configuration

- `road_class` : `p` (primary), `s` (secondary), `t` (tertiary), `m` (unclassified, residential, living_street, road, service hors parkings et allées privées), `c` (cycleway, path cyclable revêtu), `k` (track revêtue). Exclus : motorway, trunk et leurs bretelles, toute voie non revêtue (W-Q2), `access` ou `bicycle` à `no` ou `private`.
- Section `[open_world]` de `config.toml` (décrite dans `worldgen_v1.md` §6) : `cache_dir` (`~/OpenRide/Cache/monde`), `cache_max_gb` (5), `horizon_m` (3000), `offer_m` (300), `lock_m` (30), `preview_m` (500), `network` (vrai), `prefetch_history` (vrai), `prefetch_radius_km` (10), `recenter_m` (10000). Validation dans `config.py` (types et bornes) par le premier lot qui la lit (W2).

### 4.6 Plan

Reporter dans `PLAN_SERIE_W.md` §3 les chiffres mesurés par W0 et, au §5, un renvoi vers ce contrat.

## 5. Fichiers concernés

- **Modifiés :** `docs/contracts/world_format_v1.md`, `docs/contracts/ipc_v1.md`, `docs/contracts/ipc/state.schema.json`, `cmd.schema.json`, `input.schema.json`, `hello_ack.schema.json`, `error.schema.json`, `docs/contracts/world/manifest.schema.json`, `docs/2.0/PLAN_SERIE_W.md`. La section `[open_world]` est décrite dans `worldgen_v1.md` §6 ; elle entre dans la SRS §11 avec son code (W2), car le test de cohérence compare l'exemple de la SRS à `Config`.
- **Nouveaux :** `docs/contracts/worldgen_v1.md`, `docs/contracts/ipc/world_status.schema.json`, `places.schema.json`, `world_map.schema.json`, `world_regions.schema.json`, `docs/contracts/world/live.schema.json`, `route_part.schema.json`, `junctions.schema.json`, trames d'exemple, `core/tests/test_contract_open_world.py` (validation des exemples et taille de la trame la plus chargée).
- **Interdits :** tout code de production.

## 6. Modifications de contrat autorisées

Celles du §4, et elles seules : ajouts compatibles (`v` reste 1, le majeur du format reste 1).

## 7. Critères d'acceptation

1. Chaque exemple du contrat est valide pour son schéma ; un `state` sans `open_world` reste valide (lecteur v1 inchangé).
2. Trames `state` les plus chargées (ERG, 5 bots et `open_world` à 4 branches ; ERG, 5 bots et `devices`) sous 1 400 octets, vérifiées par test.
3. Exemple de `junctions.json` à 4 branches de 51 points : moins de 20 Ko.
4. Journal des changements à jour dans les trois contrats ; `pytest` passe dans `core/` et `compiler/`.
5. Le propriétaire a validé la numérotation et la répartition des rôles (§4.1).

## 8. Hors périmètre

Tout code. Les lots W2 à W15 implémentent ce contrat.

## Livraison

PR #282, fusionnée le 27 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Non : interne (décision du propriétaire) (issue #255) ».
