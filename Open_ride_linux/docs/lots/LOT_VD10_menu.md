# Lot VD10 – Menu

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : filtre des pistes, écran Prêt du vélodrome et options d'épreuve | GDScript | VD6 | Petite | Prêt (version 4.0) |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Plan validé par le propriétaire le 6 novembre (lot VD0).

## 1. Objectif

Rendre le vélodrome accessible depuis les menus, sans ligne de commande.

## 2. À lire

§8 du plan ; `engine/scripts/menu_flow.gd` ; `core/src/openride_core/catalog.py`.

## 3. Travail demandé

- Filtre « Vélodrome » et fiches des pistes dans la liste des parcours.
- Écran Prêt : épreuve, puis options (tours, distance, bots, adversaire de poursuite).
- Banc des menus complété (scénario vélodrome).

## 4. Critères d'acceptation

1. Tout se lance depuis le menu ; banc des menus vert.
2. Guide d'utilisation mis à jour (`test_docs_coherence.py`).

## 5. Fichiers touchés

- `menu_flow.gd`, `catalog.py`, `docs/GUIDE_UTILISATION.md`.

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 6, 12 et 14 ms) et ses captures sont validées par le propriétaire avant la fusion.
