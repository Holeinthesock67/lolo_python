# Lot U3 – Compilateur : côte, mer et plages

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Compilateur : côte, mer et plages | Python | U1 | Moyenne | En PR, **version 3.0** (issue #333, lancé le 8 novembre) |

## 1. Objectif

**Version 3.0.** Écrire la mer (sorte d'eau `sea`) et la couche `coast` du contrat U1 pour les parcours qui longent la côte : polygones de mer fermés à partir des lignes de côte OSM, sorte du rivage et plages.

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §6, `docs/lots/LOT_U1_contrat_biomes.md` §4.2, `docs/contracts/world_format_v1.md` §8 (eau).
2. Code : `compiler/src/openride_compiler/osm_layers.py` (couche `water`), `osm.py`, `terrain.py`, `frame.py`, `cli.py`.

## 3. Prérequis

U1 livré.

## 4. Travail demandé

- Requête Overpass `natural=coastline` dans l'emprise du terrain proche et lointain ; assemblage des segments en lignes continues (la mer est à droite du sens de la ligne, convention OSM).
- Fermeture des polygones de mer sur le rectangle de l'étendue : découpe de l'emprise par les lignes de côte, choix des morceaux du côté mer ; îles gardées comme trous.
- Sorte du rivage par point : `cliff` si `natural=cliff` à moins de 30 m ou si la pente du MNT dépasse 45° près de la ligne ; `sand` près d'une `natural=beach` (`surface=sand`) ; `shingle` (`surface=pebblestone` ou `shingle`) ; sinon `rock`.
- Plages : polygones `natural=beach` et `natural=sand` touchant la côte.
- Altitude de la mer : 0 m (ou la valeur la plus basse du MNT au bord si elle est négative) ; le terrain sous la mer n'est pas modifié.
- Sous-commande `add-layer coast` et intégration à `build` ; `verify` contrôle la fermeture des polygones.

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/coast.py`, `compiler/tests/test_coast.py` (côtes de test synthétiques, sans réseau).
- **Modifiés :** `compiler/src/openride_compiler/osm_layers.py` (sorte `sea` de la couche eau), `cli.py`, `verify.py`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** core, engine, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `pytest` passe dans `compiler/`, réseau coupé.
2. Côte droite synthétique qui coupe l'emprise : un polygone de mer du bon côté, aire à 1 % près.
3. Île au large : trou dans le polygone de mer.
4. Baie fermée par deux segments mal ordonnés : lignes recollées, un seul polygone.
5. Falaise de test (pente de 60°) : rivage `cliff` ; plage `natural=beach` : rivage `sand`.
6. Parcours sans côte : couche `coast` absente (`present: false`), couche eau inchangée.

## 7 bis. Premier essai sur le PC (r790, 9 novembre)

- GPU sous les budgets : 5,39 / 8,86 / 10,52 ms en low, medium et high.
- Pire image de 142 ms en medium et high (limite 100 ms). Cause : la mer était écrite carré de 1 km par carré
  (214 aires) ; les tronçons 1 et 4 en portaient une centaine chacun, et l'engine les préparait en 20 à 23 s
  (bateaux du lot P29 cherchés dans chaque aire, faune, maillage de l'eau). Les tuiles proches et leurs arbres
  arrivaient alors pendant la sortie au lieu du chargement.
- Correction : les carrés tout en mer d'un même tronçon sont regroupés en blocs rectangulaires (`merge_cells`,
  aires `sea_<ix>_<iz>_b<l>x<h>`) ; seuls les carrés traversés par la côte restent un par un. Côté engine,
  `boat_model.gd` ne parcourt plus la route quand sa boîte englobante est plus loin que le bord déjà trouvé
  (même résultat). Sur une côte synthétique de 11 km : 205 aires deviennent 122, et le travail des bateaux
  est divisé par 17.
- r790b (9 novembre) : 56 aires de mer, mais tâches `osm` 1 et 4 toujours à 20 s et pire image 124 / 149 ms :
  la mer n'était pas la cause. r790c, avec le détail de la tâche (`osm_eau`, `osm_bateaux`, `osm_veg_poi`,
  `osm_faune`, `osm_circulation` dans `taches.csv`) : plus de 99 % dans `osm_circulation`, les tracteurs des
  champs (lot P25). `field_rows` coupait chaque rang de 9 m avec tous les côtés du champ ; les champs OSM du
  Pas-de-Calais font plusieurs km et des milliers de points. Chaque rang ne regarde plus que les côtés qu'il
  peut couper (même résultat, test sur un champ de 4 000 points). Défaut antérieur à U3, révélé par ce parcours.
- Tracé : la route D940 tirée d'OSM fait 11,3 km entre Wissant et Sangatte ; l'essai la coupe à 8 km depuis
  Wissant (`couper_gpx.py` de la fiche d'essai).

## 8. Hors périmètre

Marées, vagues et rendu (U9), courbes bathymétriques.
