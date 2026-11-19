# Lot N22 – Décor chargé devant à rebours : portiques, herbe, détails du sol, gags WTF

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 1.x série N : fenêtres d'affichage dans le sens de la marche après un demi-tour | GDScript | N17 | Petite | **Livré le 15 novembre** (PR #889), **version 1.x** |

## 1. Objectif

Audit du décor dans les deux sens (8 novembre, points 8, 9, 10 et 13) : après un demi-tour (N17), plusieurs fenêtres
d'affichage regardaient encore vers la fin du parcours. À rebours, un portique n'apparaissait qu'à 30 m (`BEHIND_M`),
l'herbe ne couvrait que 40 m devant la caméra et les rochers 60 m, et les gags du mode WTF tombaient derrière le
cycliste, du mauvais côté.

## 2. Travail fait

- `main.gd` : `_set_direction(dir)` donne le sens de la marche (`follow.direction`) à tout ce qui pose le décor devant
  la caméra : tronçons et tuiles (N17), portiques, décor vivant, gags WTF ; remis à 1 dans les menus.
- `segment_markers.gd` : fenêtre `AHEAD_M` devant et `BEHIND_M` derrière dans le sens de la marche, portiques
  d'élimination compris.
- `grass_tufts.gd`, `ground_details.gd` (par `living_world.gd`) : `CHUNKS_BEHIND` derrière et `CHUNKS_AHEAD` devant
  dans le sens de la marche ; tronçons pris du plus proche au plus loin, priorité et urgence comptées dans ce sens.
- `wtf/wtf_scene.gd` : `ds` devant et `lateral` à droite du cycliste, cap retourné à rebours.

## 3. Critères d'acceptation

1. Tests de l'engine au vert (`test_segment_markers_model.gd`, `test_grass_tufts.gd`, `test_ground_details.gd`,
   `test_wtf_scene.gd`).
2. Captures avant/après en low, medium et high (`vitrine_portiques.gd`, vues `loin_sprint` et `rebours_loin_sprint` : portique à 150 m) validées par le propriétaire.
3. Banc GPU sur le PC en low, medium et high : attendu neutre (même nombre de tronçons, seulement placés de l'autre côté).

## Livraison

Fusionné dans `main` : PR #889 (15 novembre). Statut relevé par la mise à jour de la documentation du 19 novembre 2026.
