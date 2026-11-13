# Lot W21 – Portiques des montées et arches de bonus dans le monde ouvert

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Portiques et lignes des montées et sprints trouvés en roulant, arches de bonus sur toute la balade | Python, GDScript | W20 | Moyenne | En revue (13 novembre) |

## 1. Objectif

Suite de W20, demandée par le propriétaire le 13 novembre (« Oui » au lot W21). En monde ouvert, W20 chronomètre les montées et sprints trouvés en roulant, mais la scène ne les montre pas : pas de portique au départ ni à l'arrivée, pas de ligne au sol. Et les arches de bonus s'arrêtaient après les 3 premiers kilomètres, la longueur de la route au départ.

## 2. Travail fait

- **Core** (`open_world_segments.py`, `session.py`) :
  - `live_layer` et `write_live_layer` : à chaque changement de la liste des segments retenus, le core écrit `segments.json` dans le dossier de séance (schéma de la couche segments du §8 bis, `s` en distance de la route du générateur). Écriture atomique hors de la boucle à 50 Hz.
  - Les segments finis plus de 2 km derrière sortent du fichier, qui reste petit.
- **Arches sans fin** (`powerups.py`, `classic.py`) : `ArchSchedule` d'une route sans fin (monde ouvert, `open_ended`) compte une arche tous les 5 km, sans liste de positions. Le core et l'engine placent les arches au même pas.
- **Engine** :
  - `live_world.gd` relit `segments.json` au plus toutes les 2 s, ne garde que les segments qui tiennent dans la route chargée, et garde l'ancienne liste si le fichier est illisible. Les segments repartent avec chaque nouvelle route.
  - `segment_markers.gd` : `refresh` recalcule portiques, panneaux et arches, et ne reconstruit que les éléments qui changent (clé `mark_key`). Après un choix de branche, seuls ceux au-delà de la partie réécrite sont refaits.
  - `segment_hud_model.gd` : `merge_segments` ajoute les noms sans effacer un résultat affiché.
  - `main.gd` : `_refresh_live_markers` met à jour marques, sons des portiques et HUD ; journal de test `world_segments n=… marks=…`.
- **Tests** : `core/tests/test_open_world_segments.py` (couche et arches sans fin), `engine/tests/unit/test_live_segments.gd` (15 vérifications : relecture, fichier corrompu, segment trop long, clés des marques).

## 3. Contrats

Aucune révision IPC (la 1.17 reste libre). Le format `.world` reste en 1.8 : une ligne au journal et un paragraphe au §13 de `world_format_v1.md` disent que le core écrit `segments.json` dans le dossier d'un monde vivant.

## 4. Critères d'acceptation

1. `pytest` passe dans `core/` ; `test_live_segments.gd` et les tests de l'engine passent.
2. Captures low, medium et high sur un monde vivant simulé : portique de la montée visible devant, lignes au sol, arche de bonus au-delà de 3 km. **Captures à valider par le propriétaire avant fusion.**
3. Recette PC (avec W16 et W20) : une balade près de Sarre-Union, portiques visibles sur les montées annoncées par le HUD.

## 5. Hors périmètre

- Montées des bots à profil (`attach_segments`) sur les segments trouvés en roulant.
- Distance restante jusqu'à l'arrivée sur le HUD (il faudrait la révision IPC 1.17).

## Livraison

Branche `claude/project-thread-49nsz6-w21`, empilée sur W20 (#874), elle-même sur W19 (#873) : fusionner #873, puis #874, puis celle-ci.
