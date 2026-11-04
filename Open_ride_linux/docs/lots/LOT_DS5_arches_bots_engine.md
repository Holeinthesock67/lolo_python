# Lot DS5 – Engine : arche d'élimination, bots qui se rangent, sons

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série DS : engine, arche d'élimination, bots éliminés qui se rangent, jingles d'élimination | GDScript | DS2, DS4 | Moyenne | **Livré le 3 novembre** (version 2.0), captures à valider |

Série DS (mode « Dernier survivant », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/2.0/PLAN_SERIE_DS.md`.

## 1. Objectif

Afficher les arches que le core envoie (la prochaine et celle qu'on vient de passer, deux au plus), faire ranger les bots éliminés, jouer les sons d'élimination et de victoire.

## 2. À lire

`docs/2.0/PLAN_SERIE_DS.md` §5 et §7 ; maquettes validées de DS4 ; `engine/scripts/segment_markers.gd` et `engine/scripts/segment_markers_model.gd` ; `docs/lots/LOT_T17_jingles_evenements.md`.

## 3. Travail demandé

- Style d'arche `elim` dans les portiques, fusion avec une ligne de sprint ou de sommet confondue.
- Bot éliminé : glisse vers le bas-côté, s'efface ; aucune physique côté engine.
- Jingles synthétisés comme les autres, un par image au plus.

## 4. Critères d'acceptation

1. Captures en `low`, `medium` et `high` validées par le propriétaire avant fusion.
2. Coût de l'arche mesuré (appels de dessin, triangles) ; tests unitaires du modèle sans affichage.

## Livraison

Livré le 3 novembre 2026 (version 2.0, PR unique DS1 à DS7). Portique `elim` dans `engine/scripts/segment_markers.gd` (`set_survivor_arches`, tube à bandes rouges et noires, bandeau rouge foncé « ÉLIMINATION », frise et ligne en damier ; un portique de segment à moins de 25 m n'est pas doublé et prête son titre au sous-titre ; préchauffé quand le mode est préparé) ; la prochaine arche et celle qu'on vient de passer, positions tirées de `state.s` + `survivor.d_m` (`survivor_hud_model.arches_to_draw`). Bot éliminé (`bots[].out`) : glisse vers le bas-côté dans `bots_view_model.gd`, le core le retire au bout de 10 s. Jingles `jingle_elim` et `jingle_winner` (`event_sounds_model.gd`). Tests : `engine/tests/unit/test_survivor_hud.gd`. Reste : captures `low`, `medium`, `high` (`engine/tests/captures_ds/`) et coût de l'arche au banc du PC.
