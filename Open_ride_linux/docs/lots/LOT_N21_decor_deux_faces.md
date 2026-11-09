# Lot N21 – Décor lisible dans les deux sens de marche : faces arrière

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 1.x série N : bornes, panneau de col et portiques lisibles après un demi-tour | GDScript | N17 (aucun code de N17 requis) | Petite | En PR : engine seul, captures low/medium/high à valider (8 novembre), **version 1.x** |

## 1. Objectif

Suite du demi-tour (lot N17) : le décor du bord de route était posé et imprimé pour le seul sens du parcours. Audit du
8 novembre (`/mnt/project-files/audits/AUDIT_DECOR_DEUX_SENS_2026-11-08.md`, points 1, 2 et 5) : à rebours, on voyait le
dos vide des bornes kilométriques, du panneau de col et des bandeaux de portique, et la séance finissait sous le dos
du portique bleu « Départ ». Ce lot traite ces faces arrière ; les autres points de l'audit sont les lots N22 à N25.

## 2. Travail fait

- **Bornes kilométriques** (`roadside_props.gd`) : « km » et le numéro sur les deux faces, comme une vraie borne.
- **Panneau de col** (`roadside_model.gd`, `roadside_props.gd`) : posé des deux côtés de la route, un par sens de marche
  (`side` 1 à droite face à l'aller, -1 à gauche face au retour). Les panneaux d'approche (« Sommet à 3 km ») restent à
  droite seulement : ils décrivent la montée de l'aller (montées du retour : lot N24).
- **Portiques** (`segment_markers.gd`) : bandeau imprimé des deux côtés (`back_lines`) ; le dos du portique de départ d'un
  parcours en ligne annonce « Arrivée » (à rebours, la séance finit au départ). Les panneaux de segment gardent une seule
  face : rien ne se chronomètre à rebours (N17).

## 3. Critères d'acceptation

1. Tests de l'engine au vert (`test_roadside_model.gd`, `test_segment_markers_model.gd`).
2. Captures avant/après en low, medium et high (`vitrine_portiques.gd` vues `rebours_*`, `vitrine_rendu.gd` vue
   `borne_dos`) validées par le propriétaire.
3. Banc GPU sur le PC en low, medium et high : attendu neutre (deux Label3D de plus par portique proche, un panneau
   de col de plus par sommet).

## 4. Hors périmètre

Fenêtres d'affichage à rebours (N22), circulation et cyclistes du décor à rebours (N23), montées du retour (N24), arches
de bonus à rebours (N25), ponts, tunnels, glissières et signalisation (nouvelle série).
