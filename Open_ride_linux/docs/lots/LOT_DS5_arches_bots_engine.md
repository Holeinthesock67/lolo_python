# Lot DS5 – Engine : arche d'élimination, bots qui se rangent, sons

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série DS : engine, arche d'élimination, bots éliminés qui se rangent, jingles d'élimination | GDScript | DS2, DS4 | Moyenne | Prêt (version 3.0 proposée) |

Série DS (mode « Dernier survivant », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/3.0/PLAN_SERIE_DS.md`.

## 1. Objectif

Afficher les arches que le core envoie (la prochaine et celle qu'on vient de passer, deux au plus), faire ranger les bots éliminés, jouer les sons d'élimination et de victoire.

## 2. À lire

`docs/3.0/PLAN_SERIE_DS.md` §5 et §7 ; maquettes validées de DS4 ; `engine/scripts/segment_markers.gd` et `engine/scripts/segment_markers_model.gd` ; `docs/lots/LOT_T17_jingles_evenements.md`.

## 3. Travail demandé

- Style d'arche `elim` dans les portiques, fusion avec une ligne de sprint ou de sommet confondue.
- Bot éliminé : glisse vers le bas-côté, s'efface ; aucune physique côté engine.
- Jingles synthétisés comme les autres, un par image au plus.

## 4. Critères d'acceptation

1. Captures en `low`, `medium` et `high` validées par le propriétaire avant fusion.
2. Coût de l'arche mesuré (appels de dessin, triangles) ; tests unitaires du modèle sans affichage.
