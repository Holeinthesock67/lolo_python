# Lot R30 – Route du Cyber-Rogue moins éblouissante

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Route du Cyber-Rogue moins éblouissante : la surface du ruban ne garde que 12 % de l'éclat, les arêtes gardent la couleur de pente | GDScript | R10, R27 | Petite | En revue, **version 2.0** |

## 1. Constat

Essai du propriétaire du 22 novembre : la route jaune (pente de +1,5 à +4 %, code couleur du lot R10) éblouit.

## 2. Cause

Le shader du ruban (`ribbon.gdshader`) émettait la couleur de pente sur toute la surface à 25 % de l'éclat des
arêtes. Le jaune (`grade_up`, F0E03C) multiplié par l'intensité du préréglage (2,0 en medium, 2,4 en high) couvrait
le bas de l'écran.

## 3. Règle

Une seule part d'éclat pour la surface, `SURFACE_SHARE` (`ribbon_colors.gd`) = 0,12, passée au shader
(`surface_share`) ; les arêtes gardent tout l'éclat. Les cinq couleurs de pente ne changent pas : la pente se lit
toujours à la couleur, et toujours aussi par les mots du HUD.

## 4. Choix

Planche de trois variantes (25 %, 12 %, 6 %) en medium et high : `rogue-r30/PLANCHE_R30_variantes_route.png` des
fichiers du projet. Variante recommandée : 12 %.

## 5. Tests

- `test_ribbon_colors.gd` (20), `test_neon_palette.gd` (179).
- Galerie du Cyber-Rogue en low, medium et high ; essai vélo de 10 minutes.
