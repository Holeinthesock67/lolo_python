# Lot N24 – Montées du retour : panneaux, chiffres peints, spectateurs et parapentes

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 1.x série N : décor des montées du retour (après un demi-tour) | GDScript, Python | N23 | Moyenne | **Livré le 15 novembre** (PR #892), **version 1.x** |

## 1. Objectif

Audit du décor dans les deux sens (8 novembre, points 13 à 15) : `climb_detector.gd` ne cherchait que les montées
de l'aller. Après un demi-tour (N17), les descentes de l'aller deviennent des montées, sans panneau d'approche, sans
chiffre peint, sans spectateurs ni parapentes, et les cyclistes du décor à rebours n'y montaient pas (N23).

## 2. Travail fait

Un seul détecteur : les montées du retour sont celles du parcours retourné (`route_mirror.gd`, lot N23), ramenées
dans le repère du parcours (`ClimbDetector.detect_back`, `dir` −1, pied après le sommet).

- Panneaux d'approche « Sommet à 3, 2, 1 km » (`roadside_model.gd`) : aussi pour les montées du retour, sur le
  bas-côté gauche (la droite du cycliste à rebours), tournés vers lui. Panneau du sommet : un seul quand le sommet du
  retour est celui de l'aller (à moins de 150 m). Torii et lanternes du Japon : à l'aller seulement.
- Chiffres des kilomètres restants peints sur la chaussée : ceux du retour sur l'autre voie, tournés d'un
  demi-tour (chiffre négatif pour `road_markings.gdshader`), lisibles par le cycliste qui roule à rebours.
  Panneaux et chiffres existent dans les deux sens, comme sur une vraie route.
- Spectateurs (`crowd_model.gd`) et parapentes (`sky_traffic_model.gd`) : seulement sur les montées du sens suivi
  (choix recommandé, 14 novembre). À l'aller rien ne change ; après un demi-tour, la foule du retour (préparée avec
  celle de l'aller) et les parapentes des sommets du retour remplacent ceux de l'aller ; un second demi-tour les
  rend. Pas de foule dans les descentes, pas de coût GPU en plus.
- Cyclistes du décor à rebours (`road_cyclists_model.gd`, `road_cyclists.py`) : montées du retour dans le repère
  retourné (plus de cyclistes en montée, comme à l'aller).
- Banc simulé : scénario `montees_retour` (village, 400 W, demi-tour par Y à 495 s après la descente, puis
  remontée à rebours jusqu'au sommet du retour).

## 3. Critères d'acceptation

1. Tests de l'engine (`test_decor_rebours.gd`, `test_climb_detector.gd`, `test_roadside_model.gd`,
   `test_crowd_model.gd`, `test_sky_traffic_model.gd`, `test_living_decor.gd`, `test_road_cyclists_*.gd`) et du
   core (`test_decor_rebours.py`, `test_road_cyclists.py`) au vert.
2. Captures du banc `montees_retour` en low, medium et high (panneau d'approche du retour, chiffre peint, foule du
   sommet du retour), validées par le propriétaire.
3. Banc GPU sur le PC en low, medium et high : attendu neutre (une seule foule à la fois, mêmes budgets).

## Livraison

Fusionné dans `main` : PR #892 (15 novembre). Statut relevé par la mise à jour de la documentation du 19 novembre 2026.
