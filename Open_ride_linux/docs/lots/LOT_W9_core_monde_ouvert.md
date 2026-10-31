# Lot W9 – Core : séance en monde ouvert, route qui s'allonge, choix et verrouillage

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Core : séance en monde ouvert, route qui s'allonge, choix au Click et verrouillage, pause `world_data` | Python | W1, W8 (W15 pour commencer) | Moyenne | Non : interne (séance du core) (issue #264) |

## 1. Objectif

Brancher le monde ouvert dans la séance du core : lancer le générateur, suivre la route engagée qui s'allonge, publier le prochain carrefour dans `state`, appliquer le choix du cycliste jusqu'au verrouillage, mettre en pause si la route connue ne suffit plus, et journaliser la balade.

## 2. À lire

1. `LOT_W1_contrat_monde_vivant.md`, `docs/contracts/ipc_v1.md` (révision du monde ouvert), `docs/contracts/worldgen_v1.md`, `docs/2.0/PLAN_SERIE_W.md` §3.5, §3.6, §5.4 et §8 (W-Q1, W-Q5).
2. Code : `core/src/openride_core/session.py`, `route.py`, `ipc_server.py`, `launcher.py` (lancement et journal de Godot), `config.py`, `zwift_click.py`, `recorder.py`, `journal.py`.

## 3. Prérequis

W1 et W8 livrés. W15 (faux générateur) permet de commencer avant W8 : les tests de ce lot utilisent le faux générateur.

## 4. Travail demandé

- **`LiveRoute`** (`core/src/openride_core/live_route.py`) : même interface de lecture que `Route` (`grade_at`, `sample`, `length_m`), sur des parties de 1 km ; `apply_revision(rev, changed_from_part)` charge les nouvelles parties **dans un fil**, puis remplace la table d'un coup sous verrou ; la boucle à 50 Hz ne lit jamais le disque. `s` au-delà de la longueur connue : pente de la dernière valeur, et signal « route manquante ».
- **Générateur :** `WorldgenClient` lance `openride-worldgen` (chemin trouvé comme Godot l'est par le lanceur), lit sa sortie dans un fil, envoie `progress` 2 fois par seconde, relaie `status` en `world_status` vers l'engine, journalise sa sortie d'erreur (même rotation que M8) ; plantage du générateur : une relance, puis pause `world_data`.
- **Commande `start_open_world` :** `LOADING`, `world_status`, `READY` sur `ready` ; `route_id` = `ow:<id>` ; `hello_ack.config.open_world_dir`. Erreur `world_unavailable` relayée.
- **Carrefours :** `state.open_world` (W1 §4.3) construit depuis `junctions.json` (relu à chaque révision, hors boucle) ; `next` = premier carrefour devant ; `locked` vrai quand `s ≥ lock_s_m`.
- **Choix (W-Q1) :** en monde ouvert seulement, `LEFT_SHORT` et `RIGHT_SHORT` (bits 0 et 2 du boîtier gauche, déjà décodés par `zwift_click.py`) et `A_SHORT` du boîtier droit deviennent des choix quand un carrefour est proposé (à moins de `offer_m`) et non verrouillé, et `A_LONG` valide tout de suite la branche affichée (plan de boutons, spécification générale §7.1) ; ailleurs, ils gardent leur sens habituel. `choose_branch` de l'engine (clavier) a le même effet. Le choix est envoyé au générateur ; la réponse `branch_locked` est relayée en `error`.
- **Pente :** la pente envoyée au trainer passe par la limitation de variation existante (`grade_rate_pct_per_s`) au changement de branche ; en ERG, la pente ne joue pas sur la résistance (W-Q5).
- **Pause :** `pause_reason = "world_data"` quand `length_m − s < 200 m`, que le générateur signale `missing` ou soit seulement en retard sur le cycliste (le cycliste ne dépasse jamais la route connue) ; reprise automatique quand la route est de nouveau connue à 500 m.
- **Journal et FIT :** positions et altitude réelles (lat, lon de `LiveRoute`) ; carrefours et choix dans le journal de séance ; FIT inchangé dans sa forme.
- **Fin :** `close` au générateur, attente de `closed` (5 s au plus).

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/live_route.py`, `core/src/openride_core/worldgen_client.py`, `core/tests/test_live_route.py`, `core/tests/test_open_world_session.py`.
- **Modifiés :** `core/src/openride_core/session.py`, `ipc_server.py`, `config.py`, `launcher.py` (chemin du générateur seulement), `CLAUDE.md` (architecture), `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** l'engine, le compilateur, les contrats.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `(cd core && python -m pytest -q)` passe ; séances classiques inchangées (tests existants).
2. `LiveRoute` : vecteurs de `route_test_vectors.json` découpés en parties de 1 km → mêmes valeurs à 1e-9 près ; nouvelle révision chargée sans que la boucle de 50 Hz attende plus de 1 ms (mesuré dans le test, 1 000 pas).
3. Faux générateur (W15 ou doublure du test) : séance `start_open_world` → `READY` → `RUNNING`, 10 km en temps accéléré, aucune pause.
4. `RIGHT_SHORT` à 150 m d'un carrefour : `choose` envoyé, `state.open_world.next.chosen` change ; à 20 m : rien n'est envoyé et le choix reste.
5. Route qui ne s'allonge plus : pause `world_data` avant la fin connue, reprise quand une révision arrive.
6. Trame `state` valide pour le schéma, taille sous 1 400 octets avec `open_world`.
7. Générateur tué : une relance, puis pause `world_data` s'il retombe.

## 8. Hors périmètre

Affichage (W10 à W12), enregistrement en parcours (W14).
