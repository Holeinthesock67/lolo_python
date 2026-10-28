# Lot P26 – Ciel : avions de ligne et leurs traînées, hélicoptère, parapentes au-dessus des montées, montgolfières

## 1. Objectif

Ce lot répond à la demande du propriétaire du 27 octobre : « ça manque de vie : animaux, oiseaux, véhicules sur terre et dans le ciel ». C'est le cinquième lot de la deuxième vague du décor vivant (P22 à P27, validée le 27 octobre au soir).

Avant ce lot, le ciel n'a que des nuages (P6) et des oiseaux (P11, P23). Ce lot y ajoute, de loin et pas trop souvent :

- des avions de ligne très hauts, avec deux traînées de condensation qui s'élargissent et s'effacent ; il n'y en a pas par ciel couvert ;
- un hélicoptère qui passe à basse altitude, avec le battement de son rotor ;
- des parapentes qui tournent dans une ascendance au-dessus des montées ;
- des montgolfières qui montent, dérivent avec le vent puis se posent, seulement par vent faible.

## 2. À lire

1. `docs/lots/LOT_P6_nuages.md`, `LOT_P8_meteo_legere.md`, `LOT_P17_integration_decor_complet.md`, `LOT_P25_vehicules_au_sol.md` (maillages et shader des véhicules), `LOT_Y1_brouillard_distance_prereglage.md` (distance de la caméra), le lot Y14 (Builder de `people_mesh.gd`).
2. Code : `engine/scripts/living_decor.gd` (montées `climbs`, météo et vent évalués, `step`), `vehicle_mesh.gd`, `shaders/vehicle.gdshader`, `theme_render_params.gd`, `sound_player.gd`, `quality_presets.gd`.

## 3. Prérequis

P6, P8, P17, Y14 et P25 : même fichier `living_decor.gd`, mêmes pièces de `vehicle_mesh.gd` et même shader.

## 4. Travail demandé

- **`sky_mesh.gd`** (nouveau) : maillages construits par code avec le Builder de `people_mesh.gd` et les pièces de `vehicle_mesh.gd` (`_cyl`, `_box`, `_rod`), avec les zones de couleur des véhicules. Chaque engin a l'avant vers -z :
  - `airliner` : biréacteur de 38 m, avec fuselage, ailes en flèche, empennage à la couleur de la compagnie, réacteurs, hublots et feux ;
  - `helicopter` : cabine, verrière, poutre de queue, dérive, patins et feu à éclats ;
  - `rotor` : quatre pales tournant autour de y ;
  - `paraglider` : voile en arc de 11 caissons, suspentes, pilote dans sa sellette ;
  - `balloon` : enveloppe de révolution à fuseaux de deux couleurs, câbles, nacelle et brûleur ; le sol est à y = 0 ;
  - `contrail` : deux rubans croisés par réacteur, de longueur 1 vers +z, que le nœud étire.

  Palettes par sorte : `colors(kind, i)` renvoie [peinture, seconde couleur].
- **`shaders/vehicle.gdshaderinc`** : corps du shader de P25, partagé par `vehicle.gdshader` et par le nouveau `vehicle_far.gdshader`. Ce dernier est sans brouillard (`fog_disabled`) et sans tri des faces arrière, pour les avions lointains. **`shaders/contrail.gdshader`** (nouveau) : ruban blanc sans éclairage ni brouillard, qui s'efface vers son bout et sur ses bords.
- **`sky_traffic_model.gd`** (nouveau, sans nœud) : un horaire déterministe tiré de la graine par cases de temps de séance. Chaque vol est accroché à la place de la caméra au moment où il commence.
  - **Avions de ligne** : une case de 75 s porte un vol une fois sur 0,55. Le vol est de 8,5 à 11 km d'altitude, à 230 m/s, sur 80 km, à 15 km au plus de la caméra, avec une traînée de 2,5 à 9 km trois fois sur quatre. Aucun vol quand la couverture nuageuse du thème dépasse 0,6. Un avion réel serait au-delà de la caméra (Y1). Il est donc dessiné par homothétie autour de la caméra, à `RENDER_M` = 2 500 m au plus, dans sa vraie direction et à sa taille apparente, avec `vehicle_far.gdshader`.
  - **Hélicoptère** : une case de 240 s porte un passage 3 fois sur 10. Il vole de 120 à 250 m au-dessus de la caméra, à 55 m/s, sur 6 km, et passe à 150 à 700 m de la caméra. Son rotor tourne à 5,5 tours/s et son feu clignote.
  - **Parapentes** : de 1 à 4 voiles au-dessus de 6 montées sur 10 parmi celles de 80 m de dénivelé au moins. Elles sont à 250 à 600 m du sommet sur le côté et à 120 à 400 m au-dessus. Chacune tourne sur son cercle de 35 à 70 m, à 9 m/s, monte et descend de 15 m. On les voit à moins de 5 km.
  - **Montgolfières** : une case de 900 s porte un envol 6 fois sur 10, de 1 à 3 ballons, à 0,9 à 2,5 km de la caméra. Chaque ballon monte en 2 min à 250 à 800 m, dérive dans le sens du vent à 3 m/s × (0,5 + force du vent), puis se pose au bout de deux cases. Le brûleur s'allume 3 s toutes les 20 s.
  - **Météo** : rien ne vole sous la pluie (`rain` ≥ 0,1) ni dans la brume (`fog_boost` ≥ 0,5). Pas de parapente au-delà d'une force de vent de 0,6, ni de montgolfière au-delà de 0,35.
  - **Budget** : au plus `budget` engins, et au plus `MAX_AT_ONCE` de chaque sorte (4 avions, 2 hélicoptères, 8 parapentes, 3 montgolfières). L'ordre de priorité est l'hélicoptère, puis les montgolfières, puis les avions de ligne, puis les parapentes, et les plus proches d'abord. L'horloge est figée en pause.
- **`sky_traffic_renderer.gd`** (nouveau) : `MAX_AT_ONCE` nœuds par sorte, tous créés au démarrage. Il y a un matériau par nœud : couleurs, feux et brûleur. La traînée et le rotor sont des nœuds enfants. Deux lecteurs 3D sur le bus Ambience font le battement du rotor (audible à 1,5 km) et le grondement lointain des avions (à 4 km).
- **`sound_player.gd`** : deux sons synthétisés, `helicopter_rotor` (battement à 6 Hz et sifflement de turbine) et `airliner_rumble` (souffle grave filtré). On peut les remplacer par `~/OpenRide/Sounds/<sorte>.ogg`, comme les autres.
- **`living_decor.gd`** : il crée le modèle et l'affichage, règle le budget et passe les montées du parcours, la couverture nuageuse du thème, le vent et la météo évalués. Il fait la mise à jour dans `step`. `test_info` donne `aircraft`.
- **`quality_presets.gd`** : clé `aircraft` de `LIVING`, 4, 8 et 12 en `low`, `medium` et `high`.

## 5. Fichiers concernés

- **Nouveaux :**
  - `engine/scripts/sky_mesh.gd`, `sky_traffic_model.gd`, `sky_traffic_renderer.gd` ;
  - `engine/shaders/vehicle.gdshaderinc`, `vehicle_far.gdshader`, `contrail.gdshader` ;
  - `engine/tests/unit/test_sky_traffic_model.gd`, `engine/tests/render/test_sky_render.gd`.
- **Modifiés :**
  - `engine/shaders/vehicle.gdshader` (corps déplacé dans `vehicle.gdshaderinc`), `engine/scripts/living_decor.gd`, `quality_presets.gd`, `sound_player.gd` ;
  - `engine/tests/unit/test_living_decor.gd`, `test_quality_presets.gd`, `test_sound_player.gd`, `engine/tests/perf_budgets.json` (ligne `sky_traffic_frame`), `engine/tests/README.md` ;
  - `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** `people_mesh.gd`, `crowd_renderer.gd`, `sky_clouds.gd`, le compilateur, le core, les contrats.

## 6. Modifications de contrat autorisées

Aucune : ni IPC, ni format `.world`, ni thème, ni touche. Le ciel est désactivé avec le reste par `[render] living = false`.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Les maillages sont à leur taille (avion de 35 m d'envergure et 39 m de long, voile de 11,5 m, ballon de 18 m), avec 1 500 triangles au plus et des faces dans le sens de leurs normales.
3. Deux heures de ciel clair par vent faible donnent :
   - de 35 à 75 avions de ligne, de 3 à 16 passages d'hélicoptère et au moins une montgolfière ;
   - jamais plus que `MAX_AT_ONCE` de chaque sorte à la fois ;
   - des avions dessinés à 2 500 m au plus, dans leur vraie direction et à plus de 9° au-dessus de l'horizon ;
   - un hélicoptère de 120 à 250 m au-dessus de la caméra.

   Le ciel est le même avec la même graine et différent avec une autre.
4. Les parapentes sont au-dessus des montées assez hautes, jamais sur une bosse de 40 m, et tournent sur leur cercle. Les montgolfières dérivent avec le vent. Par grand vent, il n'y a ni parapente ni montgolfière. Rien ne vole sous la pluie ni dans la brume. Par ciel couvert, il n'y a pas d'avion de ligne.
5. Avec un budget de 1, il y a un seul engin, et c'est l'hélicoptère quand il passe. Avec un budget nul, il n'y a rien. Le ciel est figé en pause. Aucun nœud n'est créé après le démarrage. Les traînées s'allongent et le rotor tourne. Modèle et affichage tiennent sous `sky_traffic_frame` par image.
6. Rendu : dans un brouillard épais, un avion avec `vehicle_far.gdshader` garde sa couleur alors que le même avec `vehicle.gdshader` est noyé. Une traînée est opaque au réacteur et s'efface vers son bout et sur ses bords.

**Sur le PC cible (le propriétaire) :** une séance de 30 min en `medium` sur un parcours avec une montée, par beau temps, doit montrer au moins un avion de ligne et ses traînées, un parapente près du sommet et peut-être un hélicoptère ou une montgolfière, sans engin qui apparaît d'un coup ni qui traverse un nuage bas de façon choquante. La perte doit rester sous 0,5 image/s en `low`. P27 fera la mesure complète.

## 8. Hors périmètre

- Feux de navigation de nuit (P19, version 2.0), avions qui décollent ou atterrissent, ombre au sol des engins du ciel.
- Avion de tourisme, planeurs, drones : plus tard si le propriétaire les demande.
- Ciel du Cyber-Rogue (série R, scène à part).

## 9. Livraison

- Mesures sur la machine partagée (Godot 4.3 sans écran) : modèle et affichage du ciel en 0,21 à 0,24 ms par image en `high`.
- Tests : `test_sky_traffic_model.gd` (25 vérifications), `render/test_sky_render.gd` (4), `test_living_decor.gd` (33), `test_quality_presets.gd` (25), `test_sound_player.gd` (16).
- Reste à faire sur le PC cible : la séance décrite au §7.
