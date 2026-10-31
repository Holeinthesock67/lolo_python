# Lot P32 – Circulation à droite : le cycliste dans la voie de droite, chacun à droite dans son sens

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Circulation à droite : le cycliste dans la voie de droite, véhicules et cyclistes du décor à droite dans leur sens, outil de test `decor_place` et scène `voies` | GDScript + Python | P25, P28 | Petite | **Livré le 29 octobre** (demande du 29 octobre : « roulent à droite de la route et pas au milieu ») ; complément du 31 octobre : bots côte à côte en peloton, plus de superposition (trouvée par `course_bots`) |

## 1. Objectif

Demande du propriétaire du 29 octobre : « les véhicules dont les cyclistes roulent à droite de la route et pas au milieu ». Jusqu'ici, le cycliste (caméra, avatar) roulait sur la ligne médiane et tout le décor de la route se plaçait par rapport à lui : la voiture en face passait près du bord gauche, celle qui double se rabattait devant lui au milieu, les cyclistes du décor se partageaient les bords autour de l'axe.

## 2. À lire

`docs/lots/LOT_P13_*`, `LOT_P25_vehicules_au_sol.md`, `LOT_P28_cyclistes_route.md` ; code : `engine/scripts/road_builder.gd`, `traffic_model.gd`, `road_cyclists_model.gd`, `bots_view.gd`, `main.gd`.

## 3. Prérequis

P25 et P28 livrés.

## 4. Travail demandé

- **Places en travers de la chaussée** (`road_builder.gd`, seule source) : écart à l'axe, positif à droite du sens du parcours, sur la chaussée de 6 m. Cycliste `RIDER_LATERAL_M` = 1,2 m (voie de droite, 1,8 m du bord), bots `BOT_LATERAL_M` = 2,1 m (à sa droite, vers le bord), milieu de voie `LANE_CENTER_M` = 1,5 m (la voie d'en face à −1,5 m).
- **Cycliste** (`main.gd` `_rider_point`) : la caméra (toutes les vues), l'avatar et la vue des menus partent de cette place.
- **Véhicules de la route** (`traffic_model.gd`) : en face, milieu de leur voie (`oncoming_lateral`, plus loin si l'écart de 1,5 m au cycliste le demande : camion, autocar) ; qui doublent : voie de droite derrière le cycliste, à 1,5 m au moins de lui en le doublant (`lane_lateral`, compté depuis sa place), puis retour à droite.
- **Cyclistes du décor** (`road_cyclists_model.gd`) : en face sur le bord gauche (leur droite), devant et plus lents sur le bord droit, ceux qui doublent passent à sa gauche puis se rabattent à droite. `MIN_GAP_M` passe de 1,2 à 0,7 m d'épaule à épaule (un cycliste qui en double un autre) : avec le cycliste dans la voie de droite, 1,2 m ne laisse plus de place sur le bord.
- **Pas de collision** (demande du 29 octobre : « les véhicules ne doivent pas rentrer en collision, et entre véhicules entre eux ; un véhicule doit attendre avant de dépasser si obstacle en face ») :
  - véhicules (`traffic_model.gd`) : ne naissent pas sur un autre usager ; ne doublent le cycliste que si rien ne vient en face (véhicule ou cycliste du décor) ; contournent un cycliste du décor ou un bot à 1,5 m au moins (même sens) ou 0,5 m (en face), et restent derrière (`HOLD_GAP_M`) tant qu'ils ne peuvent pas le faire ou que la voie d'en face n'est pas libre ;
  - cyclistes du décor (`road_cyclists_model.gd`) : ne naissent pas à moins de 60 m d'un véhicule ni de 30 m d'un autre groupe ; un groupe qui en rattrape un autre (ou un bot) le double vers l'axe si la voie d'en face est libre, sinon reste derrière ; un cycliste ne se décale jamais vers un autre à moins de `SIDE_CLEAR_M` (0,8 m d'axe à axe) quand ils se chevauchent, il attend qu'il soit passé.
- **Routes voisines** (`road_traffic_model.gd`) : inchangées, déjà à droite sur les routes à deux voies ; un chemin à une voie reste roulé au milieu.
- **Outil de test** (message `_test` `decor_place`, hors contrat) : pose une voiture (`vehicle` : `kind`, `dir`, `rel_m`, `kmh` ; dans le même sens et tout près, posée en train de doubler) ou un groupe de cyclistes (`cyclists` : `case`, `rel_m`, `size`, `abreast`) près du cycliste. `test_info` du décor donne `road_users` (sorte, sens, écart à l'axe, distance), `rider_lateral` (écart de la caméra à l'axe, mesuré) et `contacts` (compteur de contacts, ci-dessous).
- **Outils de test des collisions** : `test_traffic_model.gd` roule 30 km avec véhicules, cyclistes du décor et un bot sur 16 graines et compte les contacts (véhicules entre eux, véhicule et cycliste, cyclistes entre eux) et les dépassements à moins de 1,5 m ; dans le jeu, `living_decor.gd` compte à chaque image les paires qui se touchent à moins de 300 m (`contacts`, `last_contact`), relevé par `sim_bench.py` (« décor : aucun contact sur la route ») et `visual_check.py` (scènes `decor_vivant` et `voies`).

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/road_builder.gd`, `main.gd`, `bots_view.gd`, `traffic_model.gd`, `road_cyclists_model.gd`, `living_decor.gd` ; `engine/tests/visual_check.py` (scène `voies`, contacts), `sim_bench.py` (contacts) ; tests `test_traffic_model.gd`, `test_road_cyclists_model.gd`, `test_bots_view_model.gd`, `test_living_decor.gd` ; `engine/tests/README.md`, `docs/OUTILS_DE_TEST.md`, `docs/RECETTE_P27.md`, index.
- **Interdits :** le core, les contrats, la position des bots dans le core (seul leur affichage bouge).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `test_traffic_model.gd` : chaque véhicule à droite dans son sens hors dépassement, à 1,5 m au moins du cycliste dans la voie de droite, chaque sorte en face sur sa droite.
2. `test_road_cyclists_model.gd` : en face à gauche de l'axe, devant à droite du cycliste, jamais à moins de 0,7 m de lui ni d'un bot.
3. `visual_check.py`, scène `voies` : cycliste dans la voie de droite, usagers en face à gauche de l'axe, cyclistes devant à sa droite, utilitaire qui double à 1,5 m au moins sur sa gauche.
4. `test_traffic_model.gd`, roulage mêlé de 16 graines : 0 contact entre véhicules, 0 véhicule sur un cycliste, 0 contact entre cyclistes (bots et cycliste compris), 0 dépassement à moins de 1,5 m. `test_living_decor.gd` : compteur de contacts à 0.
5. `visual_check.py`, scène `voies` : une voiture arrive en face, l'utilitaire posé en train de doubler attend derrière (`voies_attente`), puis double ; compteur de contacts à 0.
6. `test_docs_coherence.py` passe.

## 8. Hors périmètre

Le cycliste ne se déporte pas pour doubler (sa place est fixe) ; les places ne suivent pas encore `road.width_m` du thème (6 m partout aujourd'hui).

## 9. Livraison

- `visual_check.py` en `1280x720:low` dans le cloud : 543/543 vérifications, dont la scène `voies` (cycliste à +1,20 m de l'axe ; voiture en face à −1,63 m, cycliste en face à −2,50 m ; deux cyclistes devant à +2,50 m ; utilitaire qui double à −1,72 m, 1,50 m d'écart). Captures avant et après : `voies_face`, `voies_depassement`.
- Collisions (29 octobre, après validation des voies) : roulage mêlé de `test_traffic_model.gd`, 16 graines de 30 km : 0 contact (véhicules, cyclistes du décor, bot, cycliste), 0 dépassement à moins de 1,5 m, 281 attentes derrière un cycliste du décor ; `visual_check.py` en low, medium et high : l'utilitaire attend derrière tant que la voiture arrive en face, puis double à 1,50 m ; compteur de contacts à 0 dans `decor_vivant` et `voies`. Captures : `voies_attente`, `voies_depassement`.
- Images de référence de `run_visual_tests.sh` sur le PC : la caméra a bougé de 1,2 m, relancer une fois avec `--update-golden`.

## 10. Complément : bots côte à côte (31 octobre)

Défaut trouvé par le scénario `course_bots` du banc (lot Z2, X33) : tous les bots étaient posés à `BOT_LATERAL_M`. Quatre bots partis avec le cycliste se superposaient à l'écran (24 contacts comptés). Le propriétaire a demandé la correction le 31 octobre.

- **Places en travers** (`bots_view_model.gd`) : chaque bot vise une des `LATERAL_SLOTS`, espacées de 0,9 m : +2,1 m (sa place habituelle), puis vers l'axe et la voie d'en face. Il ne prend jamais la ligne du cycliste. Il choisit la première place libre, sans autre bot à moins de 2 m devant ou derrière. Il ne traverse pas la ligne de quelqu'un pour changer de place (le cycliste compte jusqu'à 10 m). Il garde sa place tant qu'elle reste libre et revient vers le bord dès que c'est possible, en glissant à 1,2 m/s au plus. Le champ `lateral` de `view()` sert à `bots_view.gd`. `places()` sert à `living_decor.gd`, qui les passe aux cyclistes du décor (`road_cyclists_model.gd` reçoit maintenant des places `{s, lateral}` et non plus des abscisses), aux véhicules et au compte des contacts.
- **Tests** : `test_bots_view_model.gd` (peloton de quatre au départ : quatre places, aucun contact ; le premier garde le bord ; près du cycliste, aucun bot ne se rabat sur lui ; glissement sans saut ; peloton étiré : retour au bord). `test_road_cyclists_model.gd` et `test_traffic_model.gd` passent des places.
- **Banc** : `sim_bench.py --scenario course_bots` en low, medium et high : 0 contact sur 11 captures dans chaque qualité (24 avant la correction). Planche avant/après du peloton au départ dans le dossier du projet (`bots-peloton/`).

