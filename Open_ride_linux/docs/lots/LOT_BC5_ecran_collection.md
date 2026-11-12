# Lot BC5 – Écran Collection au menu

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série BC : ligne « Collection » de l'accueil, album par familles, carte agrandie, « Voir la séance » vers l'historique, cartes vues envoyées au core | GDScript | BC2, BC3 (validé), BC4 | Moyenne | Livré le 8 novembre (PR #783, avec BC6) ; captures low, medium et high à valider pendant la recette BC7 |

Série BC (version 5.0, badges et cartes à collectionner, demande du propriétaire du 7 novembre 2026). Plan de la série : `docs/5.0/PLAN_SERIE_BC.md`.

## 1. Objectif

Afficher la collection selon les maquettes validées de BC3.

## 2. Critères d'acceptation

1. Navigation complète au Click et au clavier (guide d'utilisation et `test_docs_coherence.py` à jour).
2. Une carte agrandie envoie `collection_seen` ; son point « nouvelle » disparaît.
3. Banc des menus en low, medium et high, captures validées avant fusion.

## Réalisation

- `engine/scripts/collection_view_model.gd` (sans nœud) : ligne de l'accueil (« 17 / 42 cartes · 2 nouvelles »), première ouverture, album (une carte par élément du menu, trois familles à l'écran), carte agrandie (gagnée, à gagner avec son avancement, de saison avec ses éditions).
- `engine/scripts/collection_view.gd` : vignettes rondes dans l'anneau de leur rareté, silhouette sombre des cartes à gagner, point orange des nouvelles ; visuels de BC4 lus dans `engine/assets/collection/` (disque et pictogramme s'il en manque un).
- `menu_flow.gd`, `menu_model.gd`, `menu_view.gd`, `main.gd`, `ipc_client.gd` : ligne « Collection » après « Historique », `list_collection` au lancement et à l'ouverture, `collection_seen` à l'agrandissement d'une carte nouvelle et à la première ouverture, « Voir la séance » par `history_session` (même bilan que l'historique, retour à la carte).
- Couleurs de rareté dans `ui_theme.gd` (table des couleurs de données).
- Écart aux maquettes : le point « nouvelle » de l'accueil devient le texte « · 2 nouvelles » (les lignes du menu n'ont pas de point) ; la ligne « Condition » de la carte agrandie n'est pas affichée (le message `collection` ne la donne pas, la ligne d'ambiance la dit).
- Tests : `engine/tests/unit/test_collection_menu.gd` ; captures `collection_*` de `engine/tests/visual_check.py --menus` (faux core : vrai catalogue, 17 cartes gagnées à des dates fictives).

