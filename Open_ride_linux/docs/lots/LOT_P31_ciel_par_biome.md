# Lot P31 – Ciel par biome : montgolfières et parapentes variés, paramoteurs des pays plats

## 1. Objectif

Demande du propriétaire du 28 octobre : « Des montgolfières et parapentes seraient cool ». Le lot P26 en dessine déjà, mais on en voit peu :

- les parapentes ne volent qu'au-dessus des montées de 80 m de dénivelé au moins : sur un parcours de plaine, il n'y en a jamais ;
- les montgolfières ont toutes la même enveloppe à fuseaux ;
- le ciel est le même partout, alors que la série U donne un biome à chaque point du monde.

Ce lot rend le ciel propre au biome, ajoute les paramoteurs (la voile des pays plats, qui passe à basse altitude près de la route) et quatre motifs d'enveloppe aux montgolfières.

## 2. À lire

`docs/lots/LOT_P26_ciel.md`, `docs/3.0/PLAN_SERIE_U.md` (biomes du lot U0, modèle de biome du lot U5) ; code : `engine/scripts/sky_traffic_model.gd`, `sky_traffic_renderer.gd`, `sky_mesh.gd`, `living_decor.gd`, `biome_model.gd`, `fauna_placer.gd` (`_pick_biome`), `sound_player.gd`.

## 3. Prérequis

P26 et U5 livrés.

## 4. Travail demandé

- **Ciel par biome** (`sky_traffic_model.gd`, table `BIOME_SKY`) : pour chacun des seize biomes, la part des montées assez hautes qui portent des parapentes (`para`), leur nombre au plus par montée (`para_max`, de 1 à 6), la chance par case d'un envol de montgolfières (`balloon`) et d'un passage de paramoteur (`paramotor`).
  - Montagne, volcans, côtes et Méditerranée : beaucoup de voiles (jusqu'à 6 en montagne) ; savane, volcans (Cappadoce), déserts de roche et campagnes : montgolfières ; plaines, campagnes, déserts de sable et côtes : paramoteurs ; ciel polaire vide (sauf les avions de ligne).
  - Le biome est tiré selon les poids de `biome_model.gd` (même tirage que la faune du lot U12) : au sommet de la montée pour les parapentes, à la place de la caméra au début de la case pour les montgolfières et les paramoteurs.
  - Sans couche biome ni forçage, le biome par défaut (`temperate_grassland`) garde les chances de P26 pour les parapentes et les montgolfières : seuls les paramoteurs s'ajoutent.
- **Paramoteurs** : une case de 300 s porte un passage selon le biome, seul ou en duo (3 fois sur 10, le second à droite, au-dessus et derrière). Ils volent à 11 m/s, de 60 à 250 m au-dessus de la caméra, en ligne droite sur 3 km qui louvoie de 60 m (cap et inclinaison suivent la courbe), et passent à 100 à 500 m d'elle. Pas de paramoteur au-delà d'une force de vent de 0,5, ni sous la pluie ou dans la brume. Priorité dans le budget : après les avions de ligne, avant les parapentes ; au plus 2 à la fois.
- **Maillages** (`sky_mesh.gd`) : `paramotor` = voile et pilote du parapente, moteur, cage ronde et hélice floue (disque), 612 triangles de plus que la voile seule. Montgolfière : `build("balloon", style)` avec quatre motifs (`BALLOON_STYLES` : fuseaux, ceinture, damier, spirale), même maillage à la zone de couleur près.
- **Affichage** (`sky_traffic_renderer.gd`) : 2 nœuds de paramoteur créés au démarrage ; une montgolfière prend le maillage de son motif quand elle change d'engin (même matériau : rien à recompiler).
- **Son** (`sound_player.gd`) : `paramotor_buzz`, bourdonnement d'un moteur deux-temps (120 Hz et harmoniques) dans un souffle d'hélice, audible à 1 km ; remplaçable par `~/OpenRide/Sounds/paramotor_buzz.ogg`.
- **Branchement** (`living_decor.gd`) : le ciel prend le modèle de biome du `world_streamer` quand il est actif (couche biome ou forçage), sinon aucun.
- **Vitrine de rendu** (`tests/vitrine_rendu.gd`) : vues `ciel` (grand angle) et `ciel_proche` (téléobjectif) avec trois montgolfières, deux parapentes et un paramoteur posés à la main, affichés par `sky_traffic_renderer.gd` ; option `--views` pour ne capturer que certaines vues.

## 5. Fichiers concernés

- **Nouveau :** ce cahier.
- **Modifiés :** `engine/scripts/sky_traffic_model.gd`, `sky_traffic_renderer.gd`, `sky_mesh.gd`, `living_decor.gd`, `sound_player.gd` ; `engine/tests/unit/test_sky_traffic_model.gd`, `test_living_decor.gd`, `test_sound_player.gd`, `engine/tests/vitrine_rendu.gd`, `engine/tests/README.md` ; `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** `people_mesh.gd`, les shaders du ciel, le compilateur, le core, les contrats.

## 6. Modifications de contrat autorisées

Aucune : ni IPC, ni format `.world`, ni thème, ni touche. Le budget `aircraft` de `LIVING` ne change pas.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier ; le ciel tient sous `sky_traffic_frame` par image.
2. Sans couche biome : en deux heures de ciel clair par vent faible, au moins 2 paramoteurs, jamais plus de 2 à la fois, toujours de 60 à 250 m au-dessus de la caméra (le second du duo jusqu'à 12 m plus haut) ; montgolfières d'au moins 3 motifs.
3. Biomes forcés : en montagne plus de voiles au-dessus des montées que sans biome et aucun paramoteur ; en campagne au moins 4 paramoteurs en deux heures ; plus de montgolfières en savane qu'en montagne ; rien dans le ciel polaire sauf les avions de ligne et l'hélicoptère.
4. Duo de paramoteurs : le second exactement à sa place derrière le premier.
5. Quatre motifs d'enveloppe de même nombre de triangles et de zones de couleur différentes ; chaque montgolfière affichée avec le maillage de son motif ; aucun nœud créé après le démarrage ; son du paramoteur branché.

**Sur le PC cible (le propriétaire) :** une séance de 10 min en `medium` sur un parcours de plaine par beau temps doit montrer au moins un paramoteur (il passe une fois sur trois toutes les 5 min) et l'entendre passer ; les montgolfières n'ont plus toutes la même enveloppe.

## 8. Hors périmètre

- Planeurs, ULM, avions de tourisme et drones : plus tard si le propriétaire les demande.
- Montgolfières de forme spéciale (animal, bouteille), envols groupés de fête : plus tard.
- Ombre au sol des engins du ciel.

## 9. Livraison

- Mesures sur la machine partagée (Godot 4.3 sans écran) : modèle et affichage du ciel en 0,20 ms par image en `high` (0,18 ms avant ce lot).
- Tests : `test_sky_traffic_model.gd` (34 vérifications), `test_living_decor.gd` (41), `test_sound_player.gd` (18).
- Captures avant et après de la vitrine (`ciel`, `ciel_proche` en `low`, `medium` et `high`) jointes à la PR.
- Reste à faire sur le PC cible : la séance décrite au §7.
