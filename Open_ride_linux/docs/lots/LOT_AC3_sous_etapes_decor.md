# Lot AC3 : sous-étapes du décor dans la sonde

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| À-coups de main : sous-étapes du décor vivant notées dans la sonde (météo, faune, cyclistes, circulation, ciel et bateaux, spectateurs, passants), pour nommer les images lentes « decor » de DB1 | GDScript | AC1, X15 | Petite | En cours (PR #953, banc PC à faire) |

Fil global « Supprimer les à-coups récurrents de main » (21/11), repris du fil PI1 (« pose des arbres sur DB1 »).

## Constat
- Banc rNUIT20, DB1 high : 12 images de 50 à 64 ms par séance dont la cause est l'étape `decor` (13 à 18 ms),
  de 3,9 à 13,2 km. `decor` couvre tout `living_decor.step` : on ne sait pas quelle partie prend le temps.
- Ce n'est pas la pose des arbres (`arbres` a sa propre étape, et W22 l'a passée en tâche de fond).

## Changement (mesure seulement, pas de changement du jeu)
`living_decor.gd step` note ses parties dans la sonde avec l'étape `decor` et un identifiant : `meteo`,
`lumieres_sol_feuilles`, `faune`, `eoliennes_drapeaux_epaves_eau`, `cyclistes`, `circulation`, `ciel_bateaux`,
`spectateurs`, `passants_sons`. L'étape globale `decor` de `main.gd` reste : la cause ne change pas, la liste des
étapes de `saccades.csv` dit quelle partie a pris le temps. Sans sonde ouverte : un test de booléen par partie.

## Recette PC
Catégorie : logique (passe avec la recette de #953) : le banc DB1 high de #953 donne la partie en cause ; la
correction viendra ensuite, sur cette mesure.
