# Lot RL4 : revérifier à la fin les parcours déjà générés au nouveau relief

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Parcours compilés déjà générés (Annecy et les autres, puis le pack Cols célèbres) revérifiés et, si utile, recompilés au relief IGN / FABDEM | Python, essais PC | RL1, RL2, RL3 | Moyenne | À faire, **à la fin de la version 6.0, avant J9** (demande du propriétaire du 25 novembre) |

## Constat
RL1 et RL2 ne changent que le monde ouvert. Les parcours compilés gardent l'altitude de leur trace (GPX lissé) et
un terrain Copernicus : maisons posées sur un sol qui compte les toits, talus faux en ville et en forêt.

## Étapes
1. Inventaire sur le PC des parcours compilés déjà générés (`openride-compiler list`) : tour du lac d'Annecy
   (pack « Tours célèbres », #943), parcours importés du joueur, démonstrations des biomes.
2. Compilateur : même chaîne de relief que le monde ouvert pour la couche terrain (IGN en France, FABDEM ailleurs,
   Copernicus en dernier repli), nom de la source dans `terrain.sources` du manifeste ; altitude de la route
   inchangée quand elle vient du GPX.
3. Pour chaque parcours : couche terrain refaite (`add-layer … terrain`) dans une copie, `verify`, pentes et
   dénivelé comparés à l'ancien (`compare-garmin` quand une référence existe), captures des passages en ville et en
   forêt ; remplacement seulement après accord du propriétaire.
4. **Pack Cols célèbres en dernier** (demande du 25 novembre) : construction du pack au nouveau relief dans un
   dossier à part, contrôle longueur et dénivelé des 21 cols contre les références (tolérance du lot O16),
   pentes des lacets (lot PK2), puis remplacement du pack installé avec sauvegarde.

## Résultat attendu
Aucun parcours livré ou généré ne garde un terrain faux ; pentes et dénivelés des cols toujours dans les références.
