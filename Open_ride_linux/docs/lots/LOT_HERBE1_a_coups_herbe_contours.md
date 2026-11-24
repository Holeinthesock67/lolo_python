# Lot HERBE1 – À-coups de l'herbe près de la mer et des villes (zones d'exclusion indexées)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| À-coups de l'herbe : zones sans herbe (bâtiments, eau, mer) indexées par cases, temps vérifié à chaque touffe | GDScript | P5, Y22, U8, W23 (#907) | Petite | **Livré le 20 novembre** (PR #929) |

## 1. Constat

Banc r907 du 19 novembre (mer du monde ouvert, scénario `w23_mer`, départ Biarritz, sondes dans `sondes907_r907_vs_main.tar.gz`) : la cause « herbe » fait 245, 485 et 821 images de plus de 33 ms en low, medium et high, 12, 47 et 46 images de plus de 50 ms, du départ (0 m) jusqu'au bout de la balade (1 240 m). L'étape « herbe » de la sonde prend 22 à 35 ms par image (pire 69 ms), alors que son budget est de 2,5 ms (5 ms pour le tronçon de la caméra). Sur main (même départ, sans mer), la même étape ne dépasse jamais 10 ms et n'apparaît dans aucune saccade.

Cause : `grass_tufts.gd` (et `ground_details.gd`) testait chaque place contre **tous** les contours chargés (bâtiments et plans d'eau), sommet par sommet (`Geometry2D.is_point_in_polygon`), sans même regarder leur rectangle englobant. La mer de #907 ajoute des aires `sea` d'un carré de 1 km avec la côte détaillée des tuiles vectorielles (des milliers de sommets) : une place coûtait plus d'une milliseconde. Le temps n'étant vérifié que toutes les `BATCH` (16) places, l'image dépassait son budget de 16 places, et le remplissage ne suivait plus (fenêtre jamais pleine en medium et high).

## 2. Travail

- `engine/scripts/exclusion_zones.gd` (nouveau) : zones sans décor posé au sol, une seule règle pour l'herbe et les détails de sol. Grille de cases de 32 m calculées à la demande ; une case garde, pour chaque contour qui la touche, le contour entier s'il est petit (48 sommets au plus) ou son découpage par la case (`Geometry2D.intersect_polygons`, pair-impair comme `is_point_in_polygon`), lui-même tiré du découpage par une case large de 256 m (gardé). Les contours sont rangés par case large selon leur rectangle. Coût d'une place indépendant de la taille des contours ; même réponse que le test direct.
- `living_world.gd` : une seule instance de zones par version des contours (`shapes_version`), partagée par l'herbe et les détails de sol ; un nouveau départ sur les mêmes contours garde les cases déjà calculées.
- `grass_tufts.gd` : temps vérifié avant chaque place (et non plus toutes les 16) : le budget de l'image (2,5 ms, 5 ms pour les tronçons urgents) tient quel que soit le coût d'une place.
- `ground_details.gd` : mêmes zones.

## 3. Mesures cloud (Godot 4.7.2 sans écran, même machine, mer de 8 803 sommets à 40 m de la route et 1 470 bâtiments, 600 images à 15 m/s)

| Qualité | Avant : pire / moyenne par image, touffes, tronçons en attente | Après |
| --- | --- | --- |
| low | 8,5 ms / 2,23 ms, 3 319, 0 | 3,8 ms / 0,20 ms, 3 323, 0 |
| medium | 10,2 ms / 6,02 ms, 6 451, 6 | 3,8 ms / 0,94 ms, 17 190, 0 |
| high | 11,2 ms / 7,76 ms, 6 117, 8 | 4,9 ms / 1,91 ms, 37 740, 0 |

Avant, en medium et high, la fenêtre d'herbe n'était jamais remplie (6 et 8 tronçons en attente sur 9). Écart de touffes en low (4 de plus après) : `is_point_in_polygon` se trompe parfois sur un si grand contour (rayon qui passe par un sommet), le découpage donne la bonne réponse (vérifié sur la côte exacte).

## 4. Tests

- `engine/tests/unit/test_exclusion_zones.gd` : même réponse que le contour (L concave de 6 et 2 400 sommets, à cheval sur plusieurs cases larges, coordonnées négatives), contours qui se chevauchent, entrée `{points, rect}`, cases calculées à la demande, coût par place avec 24 000 sommets comparable à 6.
- `engine/tests/unit/test_grass_tufts.gd` (`_test_fill_with_sea`) : mer de 8 803 sommets et 1 470 bâtiments, en low, medium et high : pire image d'herbe sous 9 ms, fenêtre remplie, aucune touffe dans la mer (côte exacte).

## 5. Recette PC

File `scripts/file_bancs/herbe_high.toml` (outil `file_bancs.py`) : `w23_mer` en medium, high puis low avec la sonde, sur la branche avec #907 assemblée (cache séparé : #907 change le schéma du cache) et sur #907 seule (même cache séparé) ; puis non-régression `w17_cap` (monde ouvert sans mer, cache réel) en low, medium et high, contre main. Juger : saccades « herbe », images de plus de 50 et 100 ms, budgets GPU (8, 13, 16 ms), captures de l'herbe au bord de la mer et en ville validées par le propriétaire.

## 6. Livraison

Fusionné le 20 novembre 2026 (PR #929 : herbe sans à-coups près de la mer et des villes (zones d'exclusion indexées par cases)). Détail des écarts et de la recette : description de la PR.
