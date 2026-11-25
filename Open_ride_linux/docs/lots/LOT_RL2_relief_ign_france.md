# Lot RL2 : relief IGN RGE ALTI pour la France (plus tard)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Relief au sol IGN RGE ALTI (1 à 5 m) en France pour le monde ouvert, FABDEM ailleurs et en repli | Python | RL1 | Moyenne | À faire, plus tard (demande du propriétaire du 25 novembre) |

## But
En France, remplacer FABDEM (30 m, sol nu calculé) par le RGE ALTI de l'IGN (relief au sol mesuré, lidar et
photogrammétrie, 1 à 5 m, licence ouverte Etalab 2.0) : rues, ponts et talus au mètre près, pentes urbaines justes.

## Pistes (à vérifier avant de coder)
- Source : service WMS/WCS de la Géoplateforme (`data.geopf.fr`, couche RGE ALTI), ou dalles téléchargées
  (`RGEALTI` 5 m par département, archives `.7z` de plusieurs Go) ; le service d'altimétrie par points ne convient
  pas aux grilles. Préférer des dalles à la demande par carré de 1 km, mises en cache.
- Repère : Lambert 93 et altitudes NGF-IGN69 ; FABDEM est en EGM2008 : écart de quelques décimètres à corriger
  à la frontière des deux sources pour éviter une marche.
- Fournisseur `IgnRgeAltiProvider` (emplacement déjà réservé dans `elevation.py`), choisi par point : dans
  l'emprise de la France métropolitaine (polygone embarqué, pas de liste de lieux), FABDEM sinon.
- Nom du relief dans les versions des carrés : refaits d'eux-mêmes, comme au lot RL1.
- Même règle pour tous les lieux de France ; tests synthétiques, banc multi-zones (#1057).
