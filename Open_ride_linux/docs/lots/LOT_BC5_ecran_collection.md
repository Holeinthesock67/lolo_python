# Lot BC5 – Écran Collection au menu

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série BC : ligne « Collection » de l'accueil, album par familles, carte agrandie, « Voir la séance » vers l'historique, cartes vues envoyées au core | GDScript | BC2, BC3 (validé), BC4 | Moyenne | Prêt après validation de BC3 |

Série BC (version 5.0, badges et cartes à collectionner, demande du propriétaire du 7 novembre 2026). Plan de la série : `docs/5.0/PLAN_SERIE_BC.md`.

## 1. Objectif

Afficher la collection selon les maquettes validées de BC3.

## 2. Critères d'acceptation

1. Navigation complète au Click et au clavier (guide d'utilisation et `test_docs_coherence.py` à jour).
2. Une carte agrandie envoie `collection_seen` ; son point « nouvelle » disparaît.
3. Banc des menus en low, medium et high, captures validées avant fusion.
