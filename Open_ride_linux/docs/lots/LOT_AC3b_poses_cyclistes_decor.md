# Lot AC3b : à-coups du décor vivant, poses des cyclistes du décor

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| À-coups de main : étape « decor » de DB1, cyclistes du décor moins chers à poser sans changer leur apparence | GDScript | AC3 | Petite | En cours (banc PC DB1 low, medium, high à faire) |

Fil « Supprimer les à-coups des arbres (AC3) » (21/11), sur la mesure du lot AC3 (`LOT_AC3_sous_etapes_decor.md`).

## Constat
- Banc rNUIT20 : l'étape `decor` (tout `living_decor.step`) des images lentes de DB1 grandit avec la distance :
  médiane de 3 à 4 ms le premier kilomètre, 10 à 14 ms au-delà de 5 km en medium et high (20 ms au plus en high).
  Même pente sur `demo_long` ; plate (2 à 3 ms) sur le récif, qui n'a pas de cyclistes du décor sous l'eau.
- Ce ne sont pas les arbres : `arbres` est une étape à part, en tâche de fond depuis W22.
- Banc cloud du 21/11 (sans écran, DB1 medium à 50 km/h, 7 min, chaque sous-étape chronométrée) : seule la partie
  `cyclistes` grandit avec la distance (0,05 ms par image au départ, 0,5 à 2 ms ensuite), avec des pics de 3 à
  44 ms ; dans ces pics : la pose des avatars (`avatar_view.apply_pose`, une trentaine de pièces déplacées par
  cycliste et par image) et la construction d'un niveau de détail neuf. Faune, ciel et bateaux : pics isolés.
- Sans écran, Godot n'a pas de vrai serveur de rendu : déplacer un nœud y coûte bien moins que sur le PC. Le banc PC
  dira si `cyclistes` est bien la partie des images « decor » de 50 à 64 ms en high.

## Correction (apparence inchangée)
1. `avatar_view.gd apply_pose` : le haut du corps (buste, bassin, cou, bras, mains, tête, lunettes, cheveux, casque,
   dossard) ne dépend que de la position (assis ou en danseuse), pas de l'angle du pédalier (`AvatarMesh.pose`) :
   replacé seulement quand la position change (`_place_upper`) ; jambes, chaussures, pédalier, roues et balancement
   à chaque pose. Vaut pour tous les avatars (cyclistes du décor, bots, joueur, garage).
2. `road_cyclists_renderer.gd` : un cycliste hors du champ de la caméra (sphère de 2,5 m, `in_view`) et sans ombre
   portée (niveau de détail 1 ou 2) n'est pas reposé ; il l'est dès son retour dans le champ, à la même image.
   Le niveau 0 (ombre portée) est toujours posé.
3. `road_cyclists_renderer.gd _avatar` : un seul niveau de détail construit par image ; un autre cycliste garde
   jusqu'à l'image suivante son niveau prêt le plus proche (comme pendant la préparation des pièces).

## Tests
- `engine/tests/unit/test_avatar_pose_cache.gd` : niveaux 0, 1 et 2, 120 poses (assis, danseuse, assis) identiques à
  un haut du corps reposé à chaque image ; haut du corps replacé 2 fois au lieu de 120.
- `engine/tests/unit/test_road_cyclists_model.gd` (`_test_view_skip`) : champ de la caméra (devant, derrière, bord,
  sans caméra) ; cyclistes derrière la caméra au niveau 1 pas reposés, tous reposés dès que la caméra les regarde ;
  un seul niveau construit par image, les autres le reçoivent aux images suivantes.

## Mesure cloud (sans écran, DB1 medium, 50 km/h, 7 min ; indicative)
| | Moyenne `cyclistes` par image | Pics > 2 ms | Pire pic |
| --- | --- | --- | --- |
| Avant | 0,42 ms | 47 | 33 ms |
| Après | 0,35 ms | 56 | 12 ms |

Le nombre de pics ne baisse pas au cloud : la machine partagée y ajoute ses propres pauses de 3 à 5 ms (pics sans
pose ni construction). Seul le banc PC tranche.

## Recette PC
Catégorie : rendu. DB1 `demo-biomes-paysages` (nominal, 50 km/h, 1150 s) en low, medium et high, shaders chauds,
sonde ouverte. Attendu : dans `saccades.csv`, sous-étape `decor cyclistes` nettement plus courte qu'avant (lire la
tête 7b8a4b81 de #953 pour l'avant) ; moins d'images lentes « decor » ; budgets GPU 8 / 13 / 16 ms inchangés.
Si une autre sous-étape porte les images de 50 à 64 ms en high, elle sera le lot suivant.
