# Lot JP4 : niveau de terrain « horizon » (version 6.0, série JP)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Niveau de terrain « horizon » (500 m, 40 km, courbure de la Terre) pour voir le Fuji depuis Hakone ; format .world 1.8 | Python, GDScript, JSON | JP1 | Moyenne | En PR le 12 novembre, **version 6.0** |

Plan : `docs/6.0/PLAN_SERIE_JP.md`. Dépend de JP1 (fusionné, #832).

## But

Voir les grands sommets au-delà du brouillard : le mont Fuji est à 20–30 km de Hakone, alors que le terrain
lointain s'arrête à 5 km de la route. Le niveau est générique : tout parcours compilé en 1.8 en profite.

## Compilateur

- Format `.world` 1.8 (ajout compatible) : tuiles `terrain/horizon/tile_<ix>_<iz>.f32`, 101 × 101 float32, maille
  de 500 m, tuiles de 50 km, bande de 40 km autour de la route ; `terrain.horizon_cell_m` au manifeste.
- Courbure de la Terre avec réfraction (k = 7/6) : chute d²/(2·R·7/6) par rapport au point de route le plus proche
  (≈ 54 m à 30 km), appliquée aux seules tuiles d'horizon.
- `--no-horizon` (build, add-layer) pour s'en passer ; `verify` contrôle les trois niveaux.
- La couche des biomes reste sur les niveaux proche et lointain.

## Engine

- `engine/scripts/horizon_view.gd` : tuiles lues et maillées dans une tâche de fond, posées d'un coup ; pas d'ombre.
  Relief exagéré (`relief_k`) plein jusqu'à 5 km de la route, ramené au relief réel à 15 km (le Fuji garde 3 776 m).
- `engine/shaders/horizon.gdshader` : sans éclairage du moteur (lambert simple), ne dessine qu'au-delà de 4,5 km, couleurs
  unies sol / roche / neige du thème du biome de départ, brume propre calée chaque image sur le brouillard.
- La caméra voit jusqu'à 45 km tant que des tuiles d'horizon sont affichées.
- `--horizon=on|off` (défaut on) ; parcours d'avant la 1.8 : rien n'est créé.

## Critères

1. Tests compilateur (niveau, courbure, manifeste) et `engine/tests/unit/test_horizon_view.gd` verts.
2. Suite engine verte.
3. Captures low / medium / high (col d'Otome vers le Fuji) validées par le propriétaire.
4. Banc GPU trois qualités sur le PC (JP7) : coût visé + 0,2 à 0,5 ms ; low coupé à 20 km si le budget de 8 ms
   n'est pas tenu.

## Limites connues

- Au cloud (Vulkan logiciel), une bande bleu sombre (terrain lointain dans le brouillard) sépare la route de
  l'horizon, avec ou sans ce lot : à juger sur le PC.
