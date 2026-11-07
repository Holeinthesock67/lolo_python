# Lot BC2 – Contrat IPC de la collection

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série BC : commandes `list_collection` et `collection_seen`, message `collection`, annonce facultative `summary.collection` (une carte, nombre des autres) | Python | BC1 | Petite | En PR (7 novembre, PR #758) |

Série BC (version 5.0, badges et cartes à collectionner, demande du propriétaire du 7 novembre 2026). Plan de la série : `docs/5.0/PLAN_SERIE_BC.md`.

## 1. Objectif

Donner à l'engine la collection du profil en cours et l'annonce de fin de séance, par ajouts compatibles du contrat (révision libre au moment du lot, `docs/contracts/ipc_v1.md`).

## 2. Spécification

- `list_collection` : le core répond `collection` (cartes du catalogue dans l'ordre, gagnées avec `card_line`, avancement des autres, nombre de cartes, `first_time`), un seul datagramme de 60 000 octets au plus.
- `collection_seen {keys}` : le core ajoute ces clés à `collection_vue.json` (seule écriture de la série).
- `summary.collection` facultatif : `{card, others}` calculé à la fin de la séance, absent si rien de nouveau.
- Calcul dans un fil, jamais dans la boucle à 50 Hz ; cache des faits de la progression.

## 3. Critères d'acceptation

1. Schémas et vecteurs dans `docs/contracts/ipc/`, journal des changements du contrat.
2. Tests : taille du message avec 42 cartes gagnées et 10 éditions de saison ; profil d'essai et profil de joueur séparés ; `collection_seen` avec une clé inconnue refusée (`bad_args`).

## 4. Livraison (7 novembre 2026)

- `docs/contracts/ipc_v1.md` : révision 1.6 (§2 transport 60 000 octets pour `collection`, §3 annonce `summary.collection` au bilan, §4 commandes `list_collection` et `collection_seen`, §4 description et exemple JSON du message `collection`, §8 journal des changements).
- Schémas JSON : nouveau `docs/contracts/ipc/collection.schema.json`, mise à jour de `cmd.schema.json` (`list_collection`, `collection_seen`) et de `state.schema.json` (objet facultatif `summary.collection`).
- Core :
  - `core/src/openride_core/ipc_server.py` : `"collection"` ajouté à `LIST_MESSAGE_TYPES` (limite 60 000 octets), `"list_collection"` ajouté aux requêtes `is_query`.
  - `core/src/openride_core/ipc_lists.py` : `build_collection_message` (cartes dans l'ordre, gagnées avec `card_line`, avancement, `first_time`), `record_collection_seen` (validation et mise à jour de `collection_vue.json`), `compute_summary_collection` (calcul de l'annonce facultative).
  - `core/src/openride_core/session.py` : gestion des commandes `list_collection` et `collection_seen`, calcul de `summary.collection` dans un fil (`asyncio.to_thread`) à la fin de séance sans bloquer la boucle 50 Hz.
- Tests :
  - `core/tests/test_contract_ipc.py` : schéma `collection` vérifié avec les autres schémas du contrat, exemples de contrat v1.6 validés.
  - `core/tests/test_collection_ipc.py` : 10 tests couvrant tous les critères d'acceptation (schémas, taille sous 60 000 octets avec 42 cartes + 10 éditions de saison, séparation stricte entre profil d'essai et profil de joueur, validation et refus `bad_args` de `collection_seen`, commandes IPC dans `CoreSession`, `summary.collection` au bilan).
