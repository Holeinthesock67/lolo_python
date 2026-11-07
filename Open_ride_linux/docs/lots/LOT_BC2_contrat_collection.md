# Lot BC2 – Contrat IPC de la collection

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série BC : commandes `list_collection` et `collection_seen`, message `collection`, annonce facultative `summary.collection` (une carte, nombre des autres) | Python | BC1 | Petite | Prêt |

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
