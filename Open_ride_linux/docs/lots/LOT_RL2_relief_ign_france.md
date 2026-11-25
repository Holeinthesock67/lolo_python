# Lot RL2 : relief IGN RGE ALTI pour la France

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Relief au sol IGN RGE ALTI (pas de 5 m) en France pour le monde ouvert, FABDEM ailleurs et en repli, Copernicus en dernier | Python | RL1 | Moyenne | En revue, **version 6.0** (lancé par le propriétaire le 25 novembre) |

## But
En France, remplacer FABDEM (30 m, sol nu calculé) par le RGE ALTI de l'IGN (relief au sol mesuré, lidar et
photogrammétrie, licence ouverte Etalab 2.0) : rues, ponts et talus au mètre près, pentes urbaines justes.

## Règle (une seule, tous les lieux)
- `elevation.IgnRgeAltiProvider` : carrés de 1 km en Lambert 93 (EPSG:2154), grille de 201 × 201 points au pas de
  5 m (bords communs aux voisins), demandés au WMS raster de la Géoplateforme (`data.geopf.fr/wms-r/wms`, couche
  `ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES`, format `image/x-bil;bits=32`, ordre des octets deviné et contrôlé),
  cache `~/.cache/openride/dem/ign_rge_alti/<L93_kkkk_kkkk>.f32`.
- Cadre grossier de la France métropolitaine et de la Corse (`IGN_BBOX`, degrés) : hors du cadre, aucune demande.
  Dans le cadre mais hors de France : carré tout vide, marque `.absent`. Pixels vides (mer, frontière) : repli.
  Hors ligne ou échec réseau : repli, sans marque. Aucune liste de lieux.
- Chaîne du monde ouvert : IGN → FABDEM (RL1) → Copernicus. `openride-worldgen --relief ign` par défaut
  (`fabdem`, `copernicus` ; `--ign-url` pour les tests). `world-measure` aussi ; le préchargement en avance reste
  celui des tuiles d'un degré du repli, les carrés IGN de 1 km sont demandés en roulant.
- Nom du relief (`ign_rge_alti`) dans les versions des carrés : refaits d'eux-mêmes, sans WORLDGEN_VERSION.

## Limites connues
- Altitudes NGF-IGN69 contre EGM2008 pour FABDEM : quelques décimètres d'écart à la frontière, absorbés par le
  garde-fou d'altitude (changement de pente borné). À mesurer au lot RL3 (zone frontalière).
- Service réel injoignable depuis le cloud (hors de la liste du réseau) : nom de la couche, format BIL et ordre des
  octets à confirmer sur le PC (`pytest -m network tests/test_ign_rge_alti.py`). Si le format est refusé, tout se
  rabat sur FABDEM sans erreur (« IGN : carré … illisible » au journal).
- Une demande par carré de 1 km traversé (environ 160 Ko) : temps de génération à mesurer au banc (RL3).
- Parcours compilés inchangés : lot RL4.

## Tests
- `compiler/tests/test_ign_rge_alti.py` (faux WMS local) : noms et adresse, BIL dans les deux ordres, réponse
  fausse, interpolation dans un carré, cache relu sans demande, hors du cadre sans demande, carré vide marqué,
  pixels vides en repli, hors ligne et réseau coupé, chaîne par défaut IGN → FABDEM et nom dans les versions ;
  test `-m network` du service réel.

## Suite
- RL3 : essais du monde ouvert en France et hors de France. RL4 : parcours déjà générés revérifiés à la fin.
