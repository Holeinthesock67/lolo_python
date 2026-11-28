# Lot AC6 – Premier affichage du monde à froid : une doublure de shader par image

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| À-coups (fil du 24 novembre) : au premier lancement à shaders froids, la première tuile proche et ses arbres ne sont plus dessinés d'un coup ; une doublure minuscule de chaque shader nouveau est dessinée une image à la fois avant le départ | GDScript | PI1, PI2, AC2 | Petite | **En revue** |

## 1. Objectif

Au tout premier lancement (installation, mise à jour du pilote : caches de shaders vides), les bancs rAC (DB1 low,
medium, high) et rACow (monde ouvert ea1_lac medium) du 23 novembre gardent avant le premier mètre une ou deux
images de **5,4 à 6,6 s** : la première tuile proche et ses arbres sont dessinés pour la première fois, avec 22 à 49
pipelines compilés dans la même image (étapes « tuile near:0:0 », « arbres near:0:0 », puis tuiles voisines). Cette
famille existe sur main sans AC2 (r940b, pi2). Shaders en cache, elle disparaît.

## 2. Cause (essais au cloud, Godot 4.7.2, Vulkan logiciel, 24 novembre)

24 matériaux de shaders différents :

| Cas | Image la plus longue |
| --- | --- |
| objets ajoutés et dessinés dans la même image (ce que fait `world_streamer.integrate`) | 5,1 s (26 pipelines de surface + 25 spécialisés) |
| objets ajoutés cachés, puis montrés tous ensemble 20 images plus tard | 0,5 s à la création (pipelines de surface en fond), puis 4,3 s au premier dessin (25 spécialisés) |
| doublures ajoutées cachées, puis montrées **une par image** | 30 à 720 ms par image ; le premier vrai dessin ne compile plus rien |

Banc du correctif (12 MultiMesh d'arbres + 12 maillages, ombres, caches vidés) : pire image **4,7 à 6,1 s → 0,6 à
0,7 s**, objets affichés au bout de 6,6 s au lieu de 6,1 s (27 images au lieu d'une).

### Banc PC du 25 novembre (GTX 1060, tête 3061cc09, DB1 low/medium/high à froid, monde ouvert ea1_lac)

- Monde ouvert : les images des tuiles proches passent de 3,7 s et 5,7 s (rACow) à 0,3 à 2,1 s (10 à 11 pipelines).
- Restent 5 à 6,4 s au départ, dans les images qui portent **« spectateurs préchauffage »** (43 pipelines, avec ou
  sans tuile : en monde ouvert, l'image ne porte que deux tronçons de route) et **« passants préchauffage »** avec
  « osm 0 ». Ce sont les préchauffages du plan PI2, où tous les MultiMesh d'une foule sont dessinés dans la même
  image, et le premier tronçon OSM. Ils sont corrigés ailleurs : spectateurs et passants un MultiMesh par image
  (AC5, #985), tronçons OSM (AC2, #953). Aucune des deux PR n'était dans la tête du banc.
- Deux défauts de la première version, corrigés : (1) une tuile seulement cachée compilait encore ses pipelines
  dans l'image de sa création (0,9 à 2,1 s) ; (2) chaque doublure nouvelle relançait l'attente de toutes les autres,
  si bien que la première doublure n'a été dessinée que 13 s après la première tuile (DB1 medium, t = 26,5 s puis
  39,8 s).

### Banc PC du 25 novembre, matin (tête de3ca5b4 + #953 + #985 + #1072, rJ25J)

- DB1 medium à froid : 8,5 s avant le premier mètre. L'image de 8,5 s porte les tuiles proches **et** « osm 0 »
  et « spectateurs 0 » (53 pipelines) ; une autre de 3,8 s porte « osm 4 », « osm 5 » et « spectateurs 3 ».
- Monde ouvert : 6,2 s (29 pipelines) dans l'image qui suit l'étape « préchauffage osm » de #953, qui dessine toutes
  les sortes d'objets OSM dans la même image ; 2,15 s plus tôt pour les tronçons « osm 0 » à « osm 4 ».
- Correction v3 : les tronçons OSM (`osm_streamer.gd`) passent aussi par `hold`, comme les tuiles. Reste hors lot
  le préchauffage OSM de #953 (à faire une sorte par image) et le premier dessin des foules (#985).

### Banc PC du 25 novembre, soir (tête 038d8abf + #953 9cd71915 + #985, w24)

- DB1 à froid : **7,8 s (low), 8,2 s (medium), 8,0 s (high)** dans une seule image juste avant le premier mètre
  (42 à 57 pipelines). Tuiles et « osm 0 » y passent déjà par les doublures (« shaders entrée 1 ») ; c'est la première
  image où le décor vivant est prêt (`prepared`) : cyclistes du décor, circulation, routes voisines, ciel, bateaux,
  objets du bord de route et foules y font tous leur premier dessin (étapes « decor cyclistes », « decor circulation »,
  « decor ciel_bateaux », « spectateurs tri 504 » présentes pour la première fois).
- Correction v4 : `living_decor.gd _warm_first_draw` : quand le décor devient prêt, ses vues nouvelles sont **cachées**
  et leurs objets passent par `shader_warm.warm` (doublures sans retrait, une par image, comptées dans `pending`) ;
  `_warm_check` (chaque image, `step`) rend aux vues leur visibilité quand toutes leurs clés sont dessinées. Faune,
  éoliennes, drapeaux et épaves, déjà dessinés avant, ne sont pas touchés. En séance, rien n'est caché.

## 3. Spécification

| # | Règle |
| --- | --- |
| AC6-1 | `shader_warm.gd` : `keys_of(objet)` donne un couple par surface (MeshInstance3D ou MultiMeshInstance3D, format des sommets, shader, ombres). Deux ShaderMaterial du même shader (un matériau dupliqué par tuile) donnent la même clé. |
| AC6-2 | `hold(objets)` : si un couple n'a jamais été dessiné, les objets sont **retirés de la scène** (leur parent est gardé), et une **doublure** est préparée hors de la scène par couple nouveau (même maillage et matériaux, une instance pour un MultiMesh, mêmes ombres, sans plage de visibilité). |
| AC6-3 | `step(caméra)` : chaque image, au plus une doublure entre dans la scène, cachée (étape « shaders entrée N »), et au plus une autre, entrée deux images plus tôt, est dessinée, minuscule (échelle 0,001), 2 m devant la caméra (étape « shaders doublure N »). L'attente de chaque doublure lui est propre : des tuiles nouvelles à chaque image ne retardent pas les autres. Les objets reviennent sous leur parent quand tous leurs couples sont dessinés (parent disparu : objet libéré). `world_streamer._free_instance` accepte une tuile hors de la scène. |
| AC6-4 | `world_streamer.integrate` passe à `hold` chaque tuile ou tronçon créé et les MultiMesh de ses arbres (`tree_renderer.tile_nodes`). `pending()` s'ajoute à `pending_count()` : le départ attend la fin (start_wait_model, PI2-4). `osm_streamer` passe de même chaque tronçon OSM créé (même nœud `shader_warm`, posé par `main.gd`). |
| AC6-5 | En séance (`session_state` RUNNING, `main.gd`) : `set_active(false)` remet tout dans la scène et plus rien n'est retiré (une tuile retardée pourrait se voir). Créé pendant une séance déjà partie (reprise, tour visuel) : inactif d'emblée. Les couples jetés sont repris au chargement suivant. |
| AC6-6 | Garde-fou : sans caméra, tout revient dans la scène après 3 600 images. Réglage de test `shader_warm` (défaut vrai) pour couper le lot. |
| AC6-7 | Hors lot : spectateurs et passants (AC5, #985), étape « préchauffage osm » de #953 (toutes les sortes dans une image), cyclistes du décor (« cyclistes affichage », AC4), forêts lointaines (préchauffées par PI2), image du chargement lui-même (13 s à froid : écran de chargement, ciel, portiques), arbres « ombre seule ». |
| AC6-8 | `warm(objets)` : mêmes doublures que `hold`, mais les objets restent sous leur parent (le propriétaire les garde cachés) ; renvoie les clés à attendre, `keys_done(clés)` dit quand elles sont dessinées. `living_decor.gd` y passe, quand le décor devient prêt, les objets de la circulation, des routes voisines, des cyclistes du décor, du ciel, des bateaux, du bord de route, des luminaires, des spectateurs et des passants, et cache ces vues jusqu'à la fin. |

## 4. Fichiers

- `engine/scripts/shader_warm.gd`, `engine/tests/unit/test_shader_warm.gd` ;
- `engine/scripts/living_decor.gd` (`_warm_first_draw`, `_warm_check`), `engine/tests/unit/test_living_decor.gd` ;
- `engine/scripts/world_streamer.gd` (`shader_warm`, `integrate`, `pending_count`), `engine/scripts/tree_renderer.gd`
  (`tile_nodes`), `engine/scripts/main.gd` (création, séance), `engine/scripts/osm_streamer.gd` (`shader_warm`) ;
- `engine/tests/tour_visuel.py` : capture redemandée quand l'engine ne répond pas (premier point à shaders froids
  sur le rendu CPU de la CI, la demande UDP se perdait ; le même échec se reproduit sur main au cloud).

## 5. Critères d'acceptation

- Tests unitaires `test_shader_warm` et suite de l'engine verts en CI.
- Recette PC (shaders froids, `--shaders froid`), **avec #953 et #985** dans la pile (sans elles, les images des
  foules et du premier tronçon OSM restent) : DB1 low, medium, high et monde ouvert ea1_lac medium. Avant le
  premier mètre, plus aucune image de plus de 1,5 s portant « tuile near » ou « arbres near ». Les étapes
  « shaders entrée » et « shaders doublure » se suivent dès la première tuile. Le départ n'arrive pas plus de 2 s
  plus tard qu'avant. À shaders chauds, pas de différence notable au départ.

## 6. Livraison

À remplir à la fusion.
