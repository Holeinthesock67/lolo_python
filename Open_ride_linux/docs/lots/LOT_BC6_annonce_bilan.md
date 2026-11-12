# Lot BC6 – Annonce au bilan et badge dans l'historique

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série BC : encart d'une carte nouvelle au bilan de fin de séance (« + N autres »), petit badge sur la séance dans l'historique (O28), message de première ouverture | Python + GDScript | BC2, BC3 (validé) | Petite | En PR avec BC5 (captures low, medium et high à valider) |

Série BC (version 5.0, badges et cartes à collectionner, demande du propriétaire du 7 novembre 2026). Plan de la série : `docs/5.0/PLAN_SERIE_BC.md`.

## 1. Objectif

Annoncer une seule carte à la fois, au bon moment : au bilan, jamais pendant la séance.

## 2. Critères d'acceptation

1. Bilan sans carte nouvelle identique à aujourd'hui.
2. Trois cartes gagnées dans la séance : une seule montrée, la plus rare, et « + 2 autres dans la Collection ».
3. Ajout compatible du message `history` pour le badge ; captures validées.

## Réalisation

Livré dans la même PR que BC5 (un seul passage sur le PC pour les captures des deux lots).

- Annonce au bilan : `collection_view_model.gd` (`announce_view`) lit `summary.collection` (lot BC2) ; `collection_view.gd` dessine l'encart sous les éléments du bilan (« NOUVELLE CARTE », visuel, titre et édition, rareté, « + N autres dans la Collection »). Rien sur le bilan d'une séance de l'historique, rien pendant la séance ; sans carte nouvelle, le bilan est inchangé.
- Badge dans l'historique : liste facultative `cards` des éléments de `sessions` du message `history` (ajout compatible, révision 1.8 du contrat) ; une collection qui ne se calcule pas laisse l'historique sans badge. Côté engine, trophée doré et « · n cartes » sur la séance.
- Message de première ouverture : fait par BC5.
- Tests : `core/tests/test_historique_menu.py` (cartes posées sur leur séance, collection en panne) ; `engine/tests/unit/test_collection_menu.gd` (annonce, badge) ; capture `bilan_carte` de `engine/tests/visual_check.py --menus`.

