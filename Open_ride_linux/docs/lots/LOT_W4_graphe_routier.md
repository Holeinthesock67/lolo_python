# Lot W4 – Graphe routier local : arêtes, carrefours, classes, ponts et tunnels

## 1. Objectif

Construire, depuis la base locale (W3 ou W13), le graphe des routes qu'un cycliste peut prendre dans une emprise donnée : nœuds aux carrefours et aux impasses, arêtes avec leur géométrie, leur classe et leurs portions de pont ou de tunnel. Le navigateur (W6), les profils (W5) et le générateur (W7, W8) travaillent sur ce graphe.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_W.md` §5.4, `LOT_W1_contrat_monde_vivant.md` §4.2 et §4.5, `LOT_W3_extrait_regional_sqlite.md` §4.1.
2. Code : `compiler/src/openride_compiler/frame.py`, `worldgen/osmdb.py`.

## 3. Prérequis

W3 livré (schéma de la base). Les tests n'ont besoin que d'une base écrite par le test lui-même.

## 4. Travail demandé

Module `worldgen/graph.py` :

- `RoadGraph.build(db, bbox, frame)` : lit `roads_in(bbox)` avec `road_class` différent de `x`, projette dans le repère `frame` (x vers l'est, z vers le sud, mètres).
- **Nœuds :** un nœud OSM devient nœud du graphe s'il est partagé par au moins deux voies admises, s'il termine une voie, ou s'il est au bord de l'emprise (nœud `frontier`, à compléter quand l'emprise s'agrandit). Identifiant : celui du nœud OSM (négatif pour les nœuds synthétiques de W13).
- **Arêtes :** portion de voie entre deux nœuds du graphe ; champs `id` (`"<osm_id>:<index>"`, stable), `a`, `b`, `points` (x, z), `length_m`, `road_class`, `oneway`, `spans` (liste `[s_début, s_fin, "bridge" | "tunnel"]` le long de l'arête), `name`.
- **Sens unique :** une arête `oneway` ne se parcourt que dans son sens (`oneway=-1` inversé) ; les pistes cyclables à double sens restent ouvertes.
- `out_edges(node, arriving_heading_deg)` : branches au départ d'un nœud, avec leur cap initial (moyenne sur les 20 premiers mètres) et l'angle relatif (positif à droite, dans ]−180, 180]) ; demi-tour exclu.
- **Impasses :** `dead_end(edge, depth_m=2000)` vrai si, depuis l'arête, aucun chemin sans retour ne fait 2 km dans le graphe connu ; les nœuds `frontier` comptent comme ouverts.
- **Agrandir :** `extend(db, bbox)` ajoute ce qui touche une nouvelle emprise sans renuméroter (identifiants stables).
- **Ronds-points :** un anneau `junction=roundabout` est réduit à un nœud unique à son centre pour les choix (une seule décision par rond-point), sa géométrie restant celle de l'anneau pour le profil.
- **Fusion de petits nœuds :** deux carrefours à moins de 15 m l'un de l'autre (îlots, bretelles courtes) forment un seul choix.

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/worldgen/graph.py`, `compiler/tests/test_world_graph.py`.
- **Modifiés :** `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** tout le reste.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest` passe dans `compiler/`.
2. Graphe en croix (deux voies qui se coupent) : 5 nœuds, 4 arêtes ; depuis le sud, `out_edges` donne gauche (−90°), tout droit (0°) et droite (+90°) à 1° près.
3. Voie à sens unique : non proposée à contresens.
4. Pont sur 100 m au milieu d'une arête de 1 km : `spans` = `[[450, 550, "bridge"]]` à 1 m près.
5. Impasse de 300 m : `dead_end` vrai ; boucle de 3 km : faux ; voie qui sort de l'emprise : faux.
6. Rond-point à 4 sorties : un seul nœud de choix, 3 branches depuis une entrée.
7. `extend` sur une emprise voisine : identifiants des arêtes déjà connues inchangés.
8. Construction sur 100 km² de routes synthétiques (grille de 200 m) en moins de 2 s sur la machine de test (mesure affichée, seuil indicatif).

## 8. Hors périmètre

Altitude et profil (W5), choix de branche (W6).
