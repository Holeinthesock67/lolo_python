# OpenRide Linux – Contrat du générateur du monde ouvert (worldgen v1)

26 octobre 2026, lot W1 (IPC révision 1.5, validée par le propriétaire le 26 octobre). Plan : `docs/2.0/PLAN_SERIE_W.md`.

## 1. Rôles

| Programme | Rôle |
| --- | --- |
| `openride-worldgen` (paquet du compilateur, Python avec numpy) | Télécharge et convertit les données, tient le cache, construit le graphe routier, choisit la branche par défaut (navigateur), prolonge la route engagée, calcule les amorces de branches et les carrés, écrit le monde vivant (`world_format_v1.md` §13) |
| openride-core (sans numpy) | Lance le générateur, lui donne la position, lit la route engagée hors de la boucle à 50 Hz, publie le prochain carrefour dans `state`, applique le choix du cycliste jusqu'au verrouillage, met en pause s'il n'y a plus de route connue |
| openride-engine | Affiche le monde vivant et le HUD du carrefour ; ne parle qu'au core (`ipc_v1.md`, monde ouvert) |

Le générateur possède la route engagée : c'est lui qui la prolonge et la réécrit après un changement de branche. Le core ne fait que la lire.

## 2. Transport

- Le core lance `openride-worldgen --session <dossier de séance> --config <config.toml>` et garde le processus pendant la séance.
- Messages en lignes JSON UTF-8 : core → générateur sur l'entrée standard, générateur → core sur la sortie standard, une ligne par message, vidée aussitôt. Une ligne illisible est ignorée et comptée dans le journal.
- Le journal du générateur (en français) va sur sa sortie d'erreur ; le core le range comme celui de Godot (lot M8).
- Le générateur écrit d'abord les fichiers du monde vivant (de façon atomique, `live.json` en dernier), puis envoie `revision`. Le core relit ces fichiers dans un fil à part, jamais dans la boucle à 50 Hz.

## 3. Messages du core vers le générateur

| `type` | Champs | Effet |
| --- | --- | --- |
| `open` | `lat`, `lon`, `heading_deg`, `nav` (`ride`, `destination`, `loop`), `target` (`{lat, lon}` ou `null`), `loop_km` (nombre ou `null`), `seed` (entier), `network` (booléen) | Prépare la séance : origine sur la grille, données, relief, carrés du départ, première route engagée |
| `progress` | `s_m`, `v_mps` | Position du cycliste le long de la route engagée, deux fois par seconde |
| `choose` | `junction_id`, `branch` | Choix du cycliste ; refusé après le verrouillage |
| `close` | — | Fin de séance : le générateur termine ses écritures (5 s au plus), met l'index du cache à jour et répond `closed` |

## 4. Messages du générateur vers le core

| `type` | Champs | Sens |
| --- | --- | --- |
| `status` | `phase` (`dem`, `osm`, `tiles`, `generate`, `ready`, `error`), `done_bytes`, `total_bytes` (ou `null`), `squares_ready`, `squares_needed`, `message`, `data` (`cached`, `downloading`, `offline`, `missing`) | Avancement ; `phase` = `ready` quand la séance peut démarrer. Le core le relaie en `world_status` |
| `revision` | `rev`, `length_m`, `changed_from_part`, `junctions` (nombre de carrefours dans `junctions.json`) | De nouveaux fichiers sont prêts |
| `error` | `code` (`world_unavailable`, `branch_locked`, `unknown_junction`, `internal`), `message` | Erreur ; `world_unavailable` pendant `open` met fin à la préparation |
| `closed` | — | Réponse à `close` |

## 5. Règles de la route engagée

| Grandeur | Valeur | Clé de configuration |
| --- | --- | --- |
| Horizon : route engagée devant le cycliste | au moins 3 000 m | `horizon_m` |
| Distance à laquelle un carrefour est proposé | 300 m | `offer_m` |
| Verrouillage du choix avant le carrefour | 30 m | `lock_m` |
| Amorce calculée pour chaque branche | 500 m, avant que le carrefour soit à moins de `offer_m` | `preview_m` |
| Recentrage de l'origine de rendu dans l'engine | tous les 10 000 m | `recenter_m` |

- Sans choix du cycliste, la route suit la branche par défaut du navigateur.
- Un choix avant le verrouillage remplace la route après le carrefour par l'amorce de la branche choisie, puis la prolonge jusqu'à l'horizon ; `changed_from_part` indique la première partie réécrite.
- Hors ligne, seules des arêtes dont le relief et les carrés sont disponibles sont engagées ; s'il n'y en a aucune, la branche par défaut est le demi-tour. Plus de route du tout : `status` avec `data` = `missing`, et le core met en pause (`world_data`).
- Routes admises : classes `p`, `s`, `t`, `m`, `c`, `k` (`world_format_v1.md` §13) ; ni autoroute, ni voie rapide, ni voie non revêtue, ni voie interdite aux vélos.

## 6. Configuration `[open_world]`

Section ajoutée à `config.toml` par le premier lot qui la lit (W2), avec sa validation et sa place dans la SRS §11 :

| Clé | Défaut | Rôle |
| --- | --- | --- |
| `cache_dir` | `~/OpenRide/Cache/monde` | Cache du monde ouvert (plan §4) |
| `cache_max_gb` | 5 | Plafond du cache (décision W-Q3) |
| `horizon_m`, `offer_m`, `lock_m`, `preview_m`, `recenter_m` | 3 000, 300, 30, 500, 10 000 | §5 |
| `network` | vrai | Faux : aucun téléchargement, cache seulement |
| `prefetch_history` | vrai | Préchargement autour des départs habituels (décision W-Q4) |
| `prefetch_radius_km` | 10 | Rayon de ce préchargement |

## 7. Exemple

```text
core → {"type":"open","lat":44.174,"lon":5.279,"heading_deg":90,"nav":"ride","target":null,"loop_km":null,"seed":7,"network":true}
gen  → {"type":"status","phase":"dem","done_bytes":0,"total_bytes":44000000,"squares_ready":0,"squares_needed":24,"message":"relief N44 E005","data":"downloading"}
gen  → {"type":"status","phase":"ready","done_bytes":44000000,"total_bytes":44000000,"squares_ready":24,"squares_needed":24,"message":"","data":"cached"}
gen  → {"type":"revision","rev":1,"length_m":3410.0,"changed_from_part":0,"junctions":2}
core → {"type":"progress","s_m":125.0,"v_mps":8.3}
core → {"type":"choose","junction_id":"j123456","branch":0}
gen  → {"type":"revision","rev":2,"length_m":3530.0,"changed_from_part":2,"junctions":2}
core → {"type":"close"}
gen  → {"type":"closed"}
```

## 8. Journal des changements

| Version | Date | Changement |
| --- | --- | --- |
| 1 | 26 octobre 2026 | Première version (lot W1) |
