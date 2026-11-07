# Lot BC6 – Annonce au bilan et badge dans l'historique

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série BC : encart d'une carte nouvelle au bilan de fin de séance (« + N autres »), petit badge sur la séance dans l'historique (O28), message de première ouverture | Python + GDScript | BC2, BC3 (validé) | Petite | Prêt après validation de BC3 |

Série BC (version 5.0, badges et cartes à collectionner, demande du propriétaire du 7 novembre 2026). Plan de la série : `docs/5.0/PLAN_SERIE_BC.md`.

## 1. Objectif

Annoncer une seule carte à la fois, au bon moment : au bilan, jamais pendant la séance.

## 2. Critères d'acceptation

1. Bilan sans carte nouvelle identique à aujourd'hui.
2. Trois cartes gagnées dans la séance : une seule montrée, la plus rare, et « + 2 autres dans la Collection ».
3. Ajout compatible du message `history` pour le badge ; captures validées.
