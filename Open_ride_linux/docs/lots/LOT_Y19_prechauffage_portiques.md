# Lot Y19 – Préchauffage des portiques et règle des saccades des essais courts

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série Y (rendu) : un exemplaire de chaque portique et panneau du parcours dessiné au chargement, hors de vue ; saccades d'un essai de moins d'une heure comptées sur une heure | GDScript, Python | T8, X16 | Petite | **En PR** (2.0) ; banc PC à refaire en low, medium et high |

## 1. Objectif

Banc d'endurance 7bx (1er et 2 novembre, village simulé) : deux à-coups de ~130 ms et ~90 ms au premier passage, vers 4 600 m et 4 654 m, une seule fois par lancement. GPU et tuiles stables, seul le fil principal saute. La trace des nœuds créés (2 novembre, medium) place les à-coups exactement 400 m (`AHEAD_M` de `segment_markers.gd`) avant la première arche de bonus (5 000 m) et l'arrivée (5 053 m) : l'arche est créée 1,9 s avant l'à-coup, aucun nœud n'est créé à l'instant même. Hypothèse retenue, non prouvée : premier dessin de ces marques (pipelines des matériaux texturés, glyphes des `Label3D`), seulement au premier tour.

Le banc échouait aussi sur une extrapolation : 2 à-coups en 15 min comptés comme 8,1 par heure contre un seuil de 6.

## 2. Spécification

| # | Règle |
| --- | --- |
| Y19-1 | `segment_markers.gd` : `warm_up(camera)` construit une marque de chaque sorte du parcours (panneau, portique de chaque style, arche de bonus comprise même en ERG), sous la caméra, à 2 m devant elle et réduite à 1/2000 (rien de visible), puis la retire après 3 images (`update`). Les exemplaires ne comptent pas dans le budget des marques ; un nouveau parcours retire le préchauffage en cours. |
| Y19-2 | `main.gd` appelle `warm_up` juste après `set_route` : le premier dessin se fait pendant le chargement et l'écran « START YOUR ENGINES ». |
| Y19-3 | `perf_probe.py`, endurance : un essai de moins d'une heure a droit au seuil d'une heure (6 saccades) au lieu d'un taux extrapolé ; au-delà d'une heure, le taux par heure reste la règle. |

Écarté : rapprocher `AHEAD_M` (les portiques apparaîtraient plus tard à l'écran) ou créer toutes les marques du parcours au départ (nœuds inutiles pendant toute la séance).

## 3. Fichiers

- `engine/scripts/segment_markers.gd`, `engine/scripts/main.gd` ;
- `engine/tests/unit/test_segment_markers_model.gd` ;
- `engine/tests/perf_probe.py`, `core/tests/test_perf_probe.py` ;
- `docs/OUTILS_DE_TEST.md`.

## 4. Critères d'acceptation

1. Cloud : `test_segment_markers_model` et `test_perf_probe.py` passent.
2. PC : banc 7bx (village simulé, 15 min) en low, medium et high, main contre branche : plus d'à-coup au premier passage vers 4 600 m, temps de chargement au départ pas plus long de 0,5 s. Si l'à-coup reste, la trace des nœuds dit quel autre objet apparaît à cet instant.
