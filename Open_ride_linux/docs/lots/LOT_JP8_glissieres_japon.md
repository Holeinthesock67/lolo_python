# Lot JP8 : glissières des routes japonaises (version 6.0, série JP)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Glissières blanches à l'extérieur des virages serrés dans le biome `japan` (garde-fous reportés du lot JP5) | GDScript | JP5 | Petite | En PR le 13 novembre, **version 6.0** |

Plan : `docs/6.0/PLAN_SERIE_JP.md` (§ repères : « garde-fous orange et blancs des routes japonaises »).
Demande du propriétaire le 13/11 (« Oui » aux garde-fous reportés).

## Livraison

- `engine/scripts/roadside_model.gd` : `guardrails(route, biome_at)`.
  - Le virage se mesure par le changement de cap sur une corde de 30 m, tous les 5 m.
  - La règle s'applique dans un biome de `GUARDRAIL_BIOMES` (pour l'instant `japan`), lu tous les 50 m.
  - Tout virage plus serré que 150 m reçoit une glissière du côté extérieur.
  - Elle est prolongée de 15 m de chaque côté ; on ne garde pas les morceaux de moins de 24 m.
  - Chaque morceau est coupé aux tronçons de 1 km.
  - Ce sont des objets `guardrail` (`s`, `s_end`, `side`) de `items()`, rangés par `for_chunk` comme les autres.
- `engine/scripts/roadside_props.gd` : `guardrail_mesh()` construit la glissière le long de la route, en coordonnées du monde.
  - Lisse en W simplifiée : trois bandes doubles faces, de 0,58 à 0,87 m.
  - Poteaux de 0,95 m tous les 4 m.
  - Posée à 0,5 m du bord de la chaussée, en blanc (couleur courante au Japon).
  - Un seul maillage et un seul appel de dessin par morceau.
- Tests : `engine/tests/unit/test_roadside_model.gd`. On vérifie :
  - pas de glissière sur une ligne droite, ni hors du Japon ;
  - virage à droite de 50 m : glissière à gauche, coupée à 1 km ;
  - maillage complet et hauteur de la glissière.
- Vitrine : vue `glissiere`. La glissière se voit aussi dans la vue `torii`.
- `engine/tests/liste_glissieres.gd -- --world DOSSIER.world` : liste les glissières d'un parcours compilé (comme si tout le parcours était au Japon) et donne la liste `--at-m` des planches des bancs.

## Essais

- Captures cloud low / medium / high : `/mnt/project-files/captures/jp8-glissieres-2026-11-13/`, à valider par le propriétaire.
- Coût attendu : quelques centaines de triangles par virage, un appel de dessin par morceau. Banc PC sur Hakone dans les trois qualités, à comparer à r855.
