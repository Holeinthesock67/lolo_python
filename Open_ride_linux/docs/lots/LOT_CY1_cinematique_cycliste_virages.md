# Lot CY1 – Cinématique du cycliste dans les virages

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Vélo du joueur et des bots qui regarde où il va et se penche dans les virages : trajectoire lissée dans la voie, cap de cette trajectoire, roulis d'équilibre | GDScript | Q2, AS2, VD4, Y18 | Petite | En PR (8 novembre) |

**Statut : en PR (8 novembre)**, captures low, medium et high à valider par le propriétaire avant fusion.

## 1. Constat

Séance D du 8 novembre, propriétaire : « le joueur cycliste prend les virages bizarrement », « pourquoi pas retravailler la cinématique du cycliste ». Cas extrême : parcours `essai-vent-carre`, virages à angle droit dessinés avec 3 points par coin.

Cause, dans le code d'avant ce lot (`main.gd` `_step_avatar`, `bots_view.gd`) :

- la **position** du vélo suit la courbe de Catmull-Rom qui passe par les points tous les 10 m (`route_data.sample`), qui tourne d'un coup au coin ;
- son **cap** est la colonne `heading_deg` du compilateur (`pipeline._heading` : écart des voisins puis moyenne sur 3 points), qui tourne sur environ 40 m, à cheval sur le coin ;
- le décalage dans la voie (1,2 m à droite de l'axe) suit ce cap moyenné : avant un virage à droite, le vélo s'écarte vers l'extérieur puis revient.

Mesuré sur un carré à 3 points par coin (`tests/unit/test_rider_pose.gd`) : le vélo tourne 20 m avant le coin et roule en **crabe jusqu'à 29,5°** (écart entre le cap affiché et la direction réellement suivie), et il reste **toujours droit**, sans s'incliner. Sur la démonstration (épingles de 150 m), l'écart reste de quelques degrés : c'est surtout l'inclinaison qui manque.

## 2. Règles (pas d'exception)

Une seule pose pour tout cycliste posé sur la route, le joueur comme les bots : `engine/scripts/rider_pose.gd`, sans état, qui ne dépend que de la route, de `s`, de l'écart à l'axe et de la vitesse.

- **Trajectoire lissée** : moyenne des points de la voie (`sample_point + bank_right × écart`, même coupe que `road_builder.gd`) sur ± 4 m, un point tous les 2 m. En ligne droite, rien ne change ; dans un angle droit de 3 points, le vélo coupe le virage d'au plus 0,7 m.
- **Cap** : direction de cette trajectoire lissée (corde sur ± 2 m). Crabe au plus 1,6° sur le carré (29,5° avant).
- **Roulis** : inclinaison d'équilibre `atan(v² κ / g)` vers l'intérieur du virage, κ courbure de la trajectoire lissée (écart de cap sur ± 2 m). Bornée à ± 30° du relèvement de la piste : sur une route plate, au plus 30° ; dans un virage relevé de vélodrome à la vitesse de course, le vélo reste à peu près perpendiculaire à la piste comme au lot VD4 ; arrêté ou en ligne droite, il est droit (à l'arrêt sur 42° de relèvement : 12°, relèvement − 30°).
- **Parcours ouvert** : avant le départ et après l'arrivée, la voie est prolongée tout droit dans l'axe du bout ; la grille de départ des bots (lot AS2) n'a plus de cas à part et la moyenne ne se tasse pas aux extrémités.
- **Bots** : même pose, avec leur vitesse (`v`, ajoutée aux sorties de `bots_view_model.view()`) et leur écart à l'axe.
- **Caméras de séance alignées sur le vélo** : elles prennent le cap du vélo, lissé en 0,35 s (`RiderPose.follow_yaw`, par l'écart le plus court, repris tel quel après un saut de plus de 90° ou une reprise). Avec le cap moyenné de la route, la caméra tournait 20 m avant le virage et voyait le vélo de travers (premières captures). Leur position, leur part du relèvement des pistes (VD4) et la caméra des menus ne changent pas.
- **Coût** : une vingtaine de lectures de la route par cycliste et par image. `route_data.sample_xyzh` (point et cap seuls, mêmes calculs que `sample`, sans dictionnaire) : environ 46 µs par pose dans le nuage, 0,6 ms pour le joueur et 12 bots.

## 3. Fichiers

| Fichier | Rôle |
| --- | --- |
| `engine/scripts/rider_pose.gd` | Nouveau : `pose(route, s, écart, v)` → `{pos, yaw, roll, kappa}`, `lane_point`, `lean_roll` |
| `engine/scripts/route_data.gd` | `sample_xyzh(pos)` : point et cap seuls, sans allocation de dictionnaire |
| `engine/scripts/main.gd` | Avatar du joueur posé par `RiderPose.pose` (position, cap, roulis) ; cap des caméras de séance = cap du vélo lissé (`CAMERA_YAW_TAU_S` 0,35 s) |
| `engine/scripts/bots_view.gd`, `bots_view_model.gd` | Bots posés par `RiderPose.pose` ; `v` dans la vue des bots ; cas à part de la grille de départ retiré |
| `engine/tests/unit/test_rider_pose.gd` | Carré à angles droits : crabe d'avant (> 20°) et d'après (< 3°), écart à la voie, continuité tous les 10 cm, signe et borne du roulis, piste relevée, grille de départ, lissage du cap des caméras, `sample_xyzh` = `sample`, coût |
| `engine/tests/make_corner_world.py`, `engine/tests/tours/virages.json` | Parcours d'essai `essai-virages` (escalier de 5 côtés de 200 m, 3 points par coin) et tour visuel de ses virages à 30 km/h |
| `engine/tests/tour_visuel.py` | Clé `v_kmh` d'un point : vitesse annoncée sans faire avancer le cycliste |

## 4. Vérification

- `engine/tests/unit/test_rider_pose.gd` et la suite de l'engine (`run_engine_tests.sh`). Images de référence `tests/golden/xvfb/low/{vue_fixe,pente_0pct,pente_4pct}.png` refaites (`visual_check.py --update-golden`) : en vue subjective sur la démo, la caméra suit maintenant la tangente de la trajectoire au lieu du cap de la colonne (en retard d'un demi-pas dans les courbes), d'où quelques degrés de lacet.
- Captures avant et après, low, medium et high (planches dans les fichiers du projet, `captures/cy1-cinematique/`) : `python3 engine/tests/make_corner_world.py --out DOSSIER` puis `engine/tests/tour_visuel.py --world DOSSIER/essai-virages.world --tour engine/tests/tours/virages.json --quality Q`. À valider par le propriétaire avant fusion.
- Sur le vélo (10 min au plus) : `essai-vent-carre` et la démonstration (épingles), vue proche et éloignée, avec des bots.

## 5. Suites possibles (hors de ce lot)

- **Coins du parcours arrondis au compilateur** : la chaussée elle-même se tord aux angles droits de 3 points (coupe posée sur le cap moyenné, bords en zigzag visibles sur les captures). Arrondir les coins plus serrés qu'un rayon minimal (par exemple 8 m) avant le ré-échantillonnage réglerait la route, le décor et la trajectoire d'un coup ; touche la sortie du compilateur, donc à faire dans un lot à part.
- Coureurs du décor (P28, `road_cyclists_model.gd`) : toujours posés avec le cap de la route, sans roulis.
