# OpenRide Linux – Format .world v1

21 octobre 2026

## 1. Objet et principes

Un `.world` est un parcours compilé, prêt à être lu par openride-core et openride-engine. Il est produit par openride-compiler à partir d'un GPX et contient tout ce qu'il faut pour rouler et pour afficher, sans accès au réseau.

**Principes**

- **Un dossier, pas un fichier :** chaque couche est un fichier ou un sous-dossier indépendant, ce qui permet d'ajouter ou de régénérer une couche sans toucher aux autres.
- **Une seule couche obligatoire :** `route`. Toutes les autres sont facultatives et l'engine ignore celles qui manquent.
- **Le monde ne contient ni couleurs ni textures :** elles viennent du thème choisi au lancement (§9). Un parcours compilé reste valable quel que soit le thème.
- **Format ouvert et lisible :** JSON pour tout ce qui est structuré, binaire plat pour les grilles d'altitude, afin que Python et GDScript lisent les fichiers sans bibliothèque spéciale.
- **Versionné :** une version pour le format et une pour chaque couche (§10).

## 2. Conteneur : structure, manifeste, versions

Chaque parcours est un dossier `<nom>.world/` dans `~/.local/share/openride/routes/`.

```text
col-du-galibier.world/
  manifest.json            obligatoire : identité, repère, liste des couches
  route.json               obligatoire : couche route
  terrain/
    near/tile_<ix>_<iz>.f32    grilles proches, 10 m
    far/tile_<ix>_<iz>.f32     grilles lointaines, 50 m
  buildings/chunk_<k>.json     facultative
  vegetation/chunk_<k>.json    facultative
  poi/chunk_<k>.json           facultative
  water/chunk_<k>.json         facultative
  roads/chunk_<k>.json         facultative, depuis 1.5 : routes voisines (§8 ter)
  segments.json                facultative, depuis 1.3 : sprints et montées (§8 bis)
  biome/
    near/tile_<ix>_<iz>.json   facultative, depuis 1.6 : poids de biome des tuiles proches (§8 quater)
    far/tile_<ix>_<iz>.json    facultative, depuis 1.6 : poids de biome des tuiles lointaines
  coast/chunk_<k>.json         facultative, depuis 1.6 : lignes de côte et plages (§8 quinquies)
```

Les couches vivent par morceaux : `<k>` est l'indice du tronçon de route de 1 km (`k` = partie entière de `s` / 1000, `s` étant la position du point de route le plus proche de l'objet). Le terrain, lui, est découpé en tuiles fixes dans le repère du monde (§5).

**Le manifeste `manifest.json`** est lu en premier. Il donne :

- `format`, `format_version` (§10), `name`, date de création, version du compilateur ;
- la source (nom du GPX et somme SHA-256) ;
- l'origine et la projection (§3) ;
- pour chaque couche : `present` (vrai ou faux), `version`, et ses paramètres propres ;
- depuis la version 1.1 : `route.alt_source`, origine de l'altitude de la route (`gpx` ou nom de la source MNT, par exemple `copernicus_glo30`).
- champs facultatifs du lot O15 (ajout compatible, sans changer `format_version`) :
  - `stats`, la fiche calculée par `route_stats.py` : `version` (1), `distance_m`, `gain_m` et `loss_m` (variations de plus de 1 m seulement), `alt_min_m`, `alt_max_m`, `max_grade_pct` (sur 100 m), `climbs` (nombre de montées d'au moins 500 m et 20 m), `main_climb` (`start_m`, `length_m`, `gain_m`, `avg_grade_pct`, `category` de `4` à `HC` d'après longueur × pente moyenne : 8 000, 16 000, 32 000, 64 000, 80 000 ; ou `null`), `duration_200w_s` et `durations_s` (durées estimées de 100 à 400 W par pas de 25 W, cycliste et vélo de 84 kg), `difficulty` (1 à 5). Un lecteur qui ne la trouve pas, ou la trouve d'une autre version, la recalcule depuis `route.json` ;
  - depuis la version 1.3 (lot T1) : `layers.segments`, couche facultative en un seul fichier : `present`, `version`, `file` (`segments.json`), `count` (nombre de segments) et `manual_count` (segments venus du fichier manuel) ;
  - `library`, la fiche saisie copiée du fichier `<trace>.toml` posé à côté de la trace : `name`, `description`, `region` (texte libre, jamais de coordonnées), `tags` (étiquettes en minuscules), `credits`.

**Écriture atomique.** Le compilateur écrit dans un dossier temporaire voisin puis le renomme ; un `.world` incomplet n'est jamais visible. `add-layer` fait de même couche par couche.

## 3. Repère et conventions

Tous les fichiers utilisent le même repère local en mètres, identique à celui de Godot.

| Élément | Convention |
| --- | --- |
| Origine | Premier point de la route : (x, z) = (0, 0) |
| Axe x | Vers l'est |
| Axe y | Vers le haut ; valeur = altitude absolue en mètres (pas de décalage) |
| Axe z | Vers le sud (le nord est donc −z) |
| Projection | UTM de la zone de l'origine (WGS84) via `pyproj`, translatée pour que l'origine soit (0, 0) |
| Précision | Erreur d'échelle de l'ordre de 0,1 % au plus pour un parcours de quelques centaines de kilomètres de côté |
| Pente | `grade_pct` = 100 × variation d'altitude / distance horizontale, positif en montée ; l'angle est arctan(`grade_pct` / 100) |
| Cap | Degrés dans le sens horaire depuis le nord, de 0 à 360 |
| Distance `s` | Mètres le long de la route, mesurés en horizontal dans ce repère |
| Nombres | `float32` pour les grilles binaires, nombres JSON ailleurs ; binaires en petit-boutiste |

Le manifeste donne `lat`, `lon`, `alt_m` de l'origine et la zone UTM (par exemple `32T`) pour que chaque lecteur puisse repasser en coordonnées géographiques.

## 4. Couche route (obligatoire)

Le fichier `route.json` décrit la route par colonnes, un point tous les 10 m de distance horizontale. Le point `i` est à `s` = `i` × `ds_m`, sauf le dernier qui est placé à `length_m` exactement.

```json
{
  "version": "1.0",
  "ds_m": 10,
  "n": 2846,
  "length_m": 28450.0,
  "type": "open",
  "lat": [45.0900, 45.0901],
  "lon": [6.0600, 6.0601],
  "alt_m": [1120.5, 1120.9],
  "x": [0.0, 7.1],
  "z": [0.0, -7.0],
  "grade_pct": [4.0, 4.2],
  "heading_deg": [45.0, 45.4]
}
```

Chaque tableau compte exactement `n` valeurs.

| Champ | Contenu |
| --- | --- |
| `type` | `open`, `loop` (le dernier point coïncide avec le premier et `s` reboucle) ou `out_and_back` |
| `alt_m` | Altitude lissée (Savitzky-Golay, fenêtre de 11 points, ordre 2) |
| `alt_raw_m` | Altitude brute avant lissage, facultative |
| `grade_pct` | Pente calculée sur `alt_m` par différences centrées sur 20 m, limitée à ± 25 % |
| `heading_deg` | Cap lissé sur environ 30 m |
| `x`, `z` | Position dans le repère du monde (§3) |
| `surface` | Facultative, depuis 1.6 (lot U1) : surface de chaque point, parmi `paved`, `compacted`, `gravel` et `dirt` (portions non revêtues réelles, d'après OSM) ; une route sans cette colonne est entièrement `paved` |

**Surface de la route (depuis 1.6).** La colonne `surface` ne sert qu'à l'option « gravel » (série U, lots U20 à U22). Le réglage `[gravel] mode` de la configuration (SRS §11, ajouté avec l'IPC du lot U16) décide de ce qu'on en fait : `off` roule et affiche tout en bitume, `auto` suit la colonne, `compacted`, `gravel` ou `dirt` imposent cette surface à tout le parcours, colonne ignorée, trace revêtue comprise (décision U-Q8 du 27 octobre 2026). Le manifeste donne `route.surface_source` (`osm` ou `none`, absent = `none`) et, quand la fiche `stats` existe, `stats.surface_pct`, la part de chaque surface en %.

**Règle d'interpolation, identique en Python et en GDScript (précisée le 23 octobre 2026) :**

- Abscisses des points : `s_i = i × ds_m` pour `i < n − 1`, et `s_{n−1} = length_m`.
- Pour une position `s` : un parcours `loop` la ramène modulo `length_m`, les autres la bornent à `[0, length_m]`. Le segment `[i, i+1]` qui contient `s` donne `u = (s − s_i) / (s_{i+1} − s_i)` ; au point final, `i = n − 2`.
- `grade_pct`, `lat`, `lon`, `alt_m` : interpolation linéaire en `u`.
- Cap : `h_i + u × d`, où `d` est l'écart le plus court de `h_i` vers `h_{i+1}` (dans ]−180, 180]), ramené dans [0, 360).
- Position `(x, alt_m, z)` : Catmull-Rom centripète (Barry-Goldman, α = 0,5) sur `P_{i−1}, P_i, P_{i+1}, P_{i+2}`, distances mesurées en 3D. Nœuds `t0 = 0`, `t1 = t0 + |P_i − P_{i−1}|^0,5`, `t2 = t1 + |P_{i+1} − P_i|^0,5`, `t3 = t2 + |P_{i+2} − P_{i+1}|^0,5` (toute distance inférieure à 1e-6 m vaut 1e-6 m), paramètre `t = t1 + u × (t2 − t1)`, puis :
  `A1 = (t1−t)/(t1−t0)·P_{i−1} + (t−t0)/(t1−t0)·P_i`, `A2 = (t2−t)/(t2−t1)·P_i + (t−t1)/(t2−t1)·P_{i+1}`, `A3 = (t3−t)/(t3−t2)·P_{i+1} + (t−t2)/(t3−t2)·P_{i+2}`, `B1 = (t2−t)/(t2−t0)·A1 + (t−t0)/(t2−t0)·A2`, `B2 = (t3−t)/(t3−t1)·A2 + (t−t1)/(t3−t1)·A3`, `C = (t2−t)/(t2−t1)·B1 + (t−t1)/(t2−t1)·B2`.
- Extrémités d'un parcours ouvert : points fantômes `P_{−1} = 2·P_0 − P_1` et `P_n = 2·P_{n−1} − P_{n−2}`. Boucle : indices circulaires sur les `n − 1` points distincts (le voisin avant `P_0` est `P_{n−2}`, le voisin après `P_{n−1} = P_0` est `P_1`). `out_and_back` se lit comme `open`.
- Près d'un segment plus court que `ds_m`, la spline centripète avance à vitesse légèrement non uniforme : c'est attendu.

**Vecteurs de test :** `docs/contracts/world/route_test_vectors.json`, générés par l'implémentation de référence (`python -m openride_core.tools.route_vectors`) et vérifiés en GDScript (`engine/tests/unit/test_route_vectors.gd`). Schémas : `docs/contracts/world/manifest.schema.json` et `route.schema.json`.

Le core lit cette couche pour la pente, les coordonnées géographiques et la longueur ; l'engine pour la position et l'orientation de la caméra.

## 5. Couche terrain

Le terrain est une grille d'altitudes dans le repère du monde, en deux niveaux de détail. Il est découpé en tuiles fixes plutôt qu'en bandes le long de la route, parce que les épingles à cheveux des cols replieraient une bande sur elle-même.

| Niveau | Dossier | Maille | Taille d'une tuile | Étendue autour de la route |
| --- | --- | --- | --- | --- |
| Proche | `terrain/near/` | 10 m | 1 000 m × 1 000 m, 101 × 101 échantillons | ± 400 m |
| Lointain | `terrain/far/` | 50 m | 5 000 m × 5 000 m, 101 × 101 échantillons | ± 5 km |

**Fichier de tuile `tile_<ix>_<iz>.f32`**

- Valeurs `float32` petit-boutistes, 101 × 101, rangées par ligne : l'échantillon `(i, j)` (colonne `i`, ligne `j`, de 0 à 100) est à `x` = `ix` × T + `i` × maille et `z` = `iz` × T + `j` × maille, où T est la taille de la tuile. `ix` et `iz` peuvent être négatifs.
- Les bords sont partagés avec les tuiles voisines (mêmes valeurs), ce qui évite toute fente.
- La valeur `NaN` marque une donnée absente ; l'engine la remplace par interpolation.
- Seules les tuiles qui touchent l'étendue de la route sont écrites.

**Cohérence avec la route.** Les altitudes sont déjà corrigées par le compilateur : autour du ruban, le terrain suit l'altitude lissée de la route, puis se fond progressivement dans le MNT entre 4 m et 25 m du bord. L'engine n'a donc aucune correction à faire et la route ne flotte pas ni ne s'enterre. Ponts et tunnels sont traités comme du terrain ordinaire en v1.

**Terrain lointain.** Il masque le bord du terrain proche. Les tuiles lointaines recouvrent le terrain proche ; l'engine dessine le proche à son altitude exacte et le lointain 2 m plus bas que ses valeurs, pour éviter le scintillement entre les deux niveaux sans rapprocher le terrain proche de la chaussée.

**Manifeste :** `terrain.sources` indique le MNT utilisé (`copernicus_glo30`, `ign_rge_alti`), avec sa résolution native, pour que le compilateur sache quand régénérer.

Ajouts compatibles de la version 1.1, dans `layers.terrain` :

- `native_resolution_m` : résolution native du MNT, en mètres (30 pour `copernicus_glo30`) ;
- `road_half_width_m` : demi-largeur de chaussée utilisée pour le fondu (3 m par défaut) ;
- `tiles` : liste des tuiles écrites, `{"near": [[ix, iz], …], "far": [[ix, iz], …]}`. `verify` contrôle leur présence. Un lecteur peut s'en servir au lieu de parcourir les dossiers.

## 6. Couche bâtiments

Facultative. Un fichier `buildings/chunk_<k>.json` par tronçon de 1 km, avec la liste des bâtiments d'OpenStreetMap situés à moins de 400 m de la route.

```json
{
  "version": "1.0",
  "buildings": [
    {
      "id": "w123456",
      "outer": [[12.0, -340.5], [20.5, -340.5], [20.5, -332.0], [12.0, -332.0]],
      "holes": [],
      "base_y": 1210.4,
      "height_m": 8.0,
      "roof": "flat",
      "hint": {"building": "house", "colour": null}
    }
  ]
}
```

- `outer` et `holes` : anneaux de points (x, z) dans le repère du monde, `outer` dans le sens antihoraire vu du dessus ; les trous viennent des multipolygones OSM. Le premier point n'est pas répété à la fin.
- `base_y` : altitude du sol au pied du bâtiment (minimum du terrain sous l'empreinte), calculée par le compilateur pour qu'engine et terrain concordent.
- `height_m` : tirée de `height`, sinon de `building:levels` × 3 m, sinon d'une valeur par défaut aléatoire mais stable (dérivée de `id`) entre 4 et 10 m.
- `roof` : `flat` en v1 ; `gabled` est réservé pour plus tard (il demandera une orientation du faîtage, `roof_dir_deg`).
- `hint` : informations OSM brutes ; l'engine choisit les couleurs dans la palette du thème de façon stable à partir de `id`. Le monde ne stocke aucune couleur.
- La triangulation se fait dans l'engine (`Geometry2D.triangulate_polygon`).

## 7. Couche végétation

Facultative. Le fichier `vegetation/chunk_<k>.json` décrit où poser des arbres ; les arbres eux-mêmes sont instanciés par l'engine (`MultiMeshInstance3D`).

```json
{
  "version": "1.0",
  "areas": [
    {
      "id": "w98765",
      "kind": "wood",
      "outer": [[100.0, -200.0], [180.0, -210.0], [170.0, -120.0]],
      "holes": [],
      "density": 0.8
    }
  ]
}
```

- `kind` : `wood` (forêt), `scrub` (broussailles), `orchard` (verger) ; depuis la version 1.5 (lot P22), les terrains ouverts `meadow` (pré, OSM `landuse=meadow`), `farmland` (champ cultivé, `landuse=farmland`) et `grassland` (prairie ou lande, `landuse=grass`, `natural=grassland` ou `natural=heath`), où l'engine place les animaux et les tracteurs mais aucun arbre ; d'autres valeurs sont ignorées.
- `k` : pour un terrain ouvert dont le centre est hors du couloir de 400 m, le sommet du contour le plus proche de la route décide du tronçon (un grand champ qui touche le couloir par un bord reste gardé).
- `density` : de 0 à 1, proportion du maximum fixé par le thème ; toujours 0 pour un terrain ouvert, de plus de 0 à 1 sinon. Les arbres sont placés de façon déterministe : la graine dérive de `id`, donc le paysage est identique d'une séance à l'autre.
- Le manifeste porte `vegetation.source` : `osm` (polygones d'OpenStreetMap) ou `none`.

**Sans polygones.** OpenStreetMap est lacunaire en montagne. Quand la couche est absente ou vide, l'engine peut semer des arbres à partir d'un bruit de densité, en dessous de la limite des arbres fixée par le thème (`treeline_m`). La couverture du sol (ESA WorldCover) pourra alimenter cette couche plus tard sans changer son format.

## 8. Couches points d'intérêt et eau

Deux couches facultatives, chacune en fichiers `chunk_<k>.json`.

**Points d'intérêt (`poi/`)**

```json
{
  "version": "1.0",
  "points": [
    {"id": "n555", "kind": "church_bell", "x": 310.0, "y": 1195.0, "z": -420.0, "radius_m": 300, "name": "Saint-Pierre"}
  ]
}
```

- `kind` : `church_bell`, `river`, `livestock`, `village`, `viewpoint` ; depuis la version 1.2 (lot P1), `wind_turbine` (OSM `power=generator` avec `generator:source=wind`, `height_m` facultatif d'après la balise `height`) et `flag` (OSM `man_made=flagpole`) ; une valeur inconnue est ignorée.
- `radius_m` : distance d'audibilité ou de visibilité.
- L'engine associe un son à chaque `kind` selon le thème ou la configuration audio ; `name` sert à l'affichage éventuel.

**Eau (`water/`)**

```json
{
  "version": "1.0",
  "lines": [{"id": "w31", "kind": "river", "width_m": 6.0, "points": [[0.0, -500.0, 1100.0], [40.0, -460.0, 1098.5]]}],
  "areas": [{"id": "w77", "kind": "lake", "level_y": 1002.0, "outer": [[0.0, 0.0], [90.0, 10.0], [70.0, 80.0]], "holes": []}]
}
```

- `lines` : cours d'eau, points (x, z, y) dans le repère du monde ; `width_m` est la largeur, 2 m par défaut.
- `areas` : plans d'eau, avec `level_y` pour l'altitude de la surface. `kind` : `lake`, `pond`, `reservoir` ; depuis 1.6 (lot U1), `sea` : polygone de mer refermé sur le bord de l'étendue du terrain (`level_y` = 0), dont le rivage est décrit par la couche côte (§8 quinquies).
- Ces deux couches arrivent au sprint 6 ; le format est figé dès maintenant pour qu'un parcours compilé plus tôt puisse recevoir ces couches plus tard.

## 8 bis. Couche segments (depuis 1.3)

Couche facultative en un seul fichier `segments.json` (lot T1, série T) : les sprints et les montées du parcours, dont l'engine affiche le départ, l'arrivée et le nom, et dont le core chronomètre les passages. Le compilateur l'écrit (lot T3) d'après la détection automatique de `segments.py` (T2) et le fichier manuel facultatif `<parcours>.segments.toml` ; `add-layer <nom>.world segments` la refait seule.

```json
{
  "version": "1.0",
  "segments": [
    {"id": "sprint-1", "name": "Sprint 1", "type": "sprint", "s_start": 2400.0, "s_end": 2700.0, "length_m": 300.0, "avg_grade_pct": 0.4, "gain_m": 1.2, "category": null, "source": "auto"},
    {"id": "climb-1", "name": "Côte du village", "type": "climb", "s_start": 5200.0, "s_end": 7600.0, "length_m": 2400.0, "avg_grade_pct": 5.1, "gain_m": 122.4, "category": "3", "source": "manual"}
  ]
}
```

- Chaque élément est `Segment.to_dict()` de `segments.py` : `id` unique dans le parcours, `name` (au plus 48 caractères), `type` (`sprint` ou `climb`), `s_start` et `s_end` en mètres le long de la route (`s_start` < `s_end` ; sur une boucle, pas de segment à cheval sur la ligne), `length_m`, `avg_grade_pct`, `gain_m`, `category` (`4`, `3`, `2`, `1`, `HC` pour une montée, `null` pour un sprint) et `source` (`auto` ou `manual`).
- Au plus 200 segments, triés par `s_start`. Schéma : `docs/contracts/world/segments.schema.json`.
- Un `.world` sans cette couche reste lisible : le core n'y chronomètre rien et l'engine n'affiche aucun segment. Elle ne dépend que de la route : refaire la route oblige à la refaire.

## 8 ter. Couche routes voisines (depuis 1.5)

Couche facultative en fichiers `roads/chunk_<k>.json` (lot P22) : les routes OpenStreetMap du couloir de 400 m autour du parcours, sans la route du parcours elle-même, pour que l'engine y fasse rouler des voitures, des camions et des bus (lot P25). `add-layer <nom>.world roads` la refait seule.

```json
{
  "version": "1.0",
  "lines": [
    {"id": "w4021", "kind": "secondary", "lanes": 2, "oneway": false, "speed_kmh": 80,
     "points": [[120.0, -340.0, 251.3], [145.5, -362.0, 251.9]]}
  ]
}
```

- `kind` : la balise `highway` d'OSM, parmi `motorway`, `trunk`, `primary`, `secondary`, `tertiary`, `unclassified`, `residential` et `track`.
- `lanes` : de 1 à 8, d'après la balise `lanes`, sinon 4 pour `motorway` et `trunk`, 1 pour `track` ou un sens unique, 2 ailleurs.
- `oneway` : vrai pour `oneway=yes` et toute `motorway` ; le sens est celui des points.
- `speed_kmh` : d'après `maxspeed` en km/h (de 5 à 150), sinon 130 (`motorway`), 110 (`trunk`), 80 (`primary`, `secondary`, `tertiary`), 50 (`unclassified`), 30 (`residential`), 20 (`track`).
- `points` : (x, z, y) tous les 25 m au plus, `y` étant le sol sous la route. Une ligne est coupée là où elle passe à moins de 20 m de la route du parcours (croisement ou tronc commun) et là où elle sort du couloir ; chaque morceau reste dans un seul tronçon `k` (identifiant `<id>_<n>` quand une voie OSM en donne plusieurs) et n'est gardé que s'il a au moins deux points et s'éloigne d'au moins 35 m de la route du parcours.
- Schéma : `docs/contracts/world/roads.schema.json`. Un `.world` sans cette couche reste lisible : l'engine garde le trafic de P13 sur la route du parcours.

## 8 quater. Couche biome (depuis 1.6)

Couche facultative (lot U1, série U, version 3.0) : la part de chaque biome en tout point du terrain, que l'engine utilise pour mélanger les sols, la végétation, l'eau, le ciel, les sons et la faune des biomes du thème (§9, thème 2.0). Elle suit les tuiles de la couche terrain (§5) : `biome/near/tile_<ix>_<iz>.json` pour chaque tuile proche, `biome/far/tile_<ix>_<iz>.json` pour chaque tuile lointaine, mêmes indices. Une tuile de terrain sans fichier de biome prend le biome par défaut du manifeste ; un parcours sans couche `biome` garde le rendu d'avant la 3.0 (thème 1.x, ou biome par défaut du thème 2.0).

```json
{
  "version": "1.0",
  "biomes": ["temperate_grassland", "mediterranean", "coast"],
  "grid": 17,
  "weights": [[255, 239, "… 289 valeurs"], [0, 16, "…"], [0, 0, "…"]],
  "variant": {"ground": "calcaire_blanc", "roofs": "tuile_ronde"}
}
```

- `biomes` : de 1 à 4 identifiants distincts, parmi les seize du lot U0 : `temperate_grassland` (prairie et bocage tempérés, biome par défaut), `temperate_forest`, `farmland` (vignobles et grandes cultures), `boreal_forest`, `alpine`, `tundra`, `polar`, `mediterranean`, `steppe`, `savanna`, `sand_desert`, `rock_desert`, `jungle`, `wetland`, `coast` (littoral), `volcanic`.
- `grid` : 17. La tuile est une grille de 17 × 17 points (16 × 16 cases : 62,5 m en proche, 312,5 m en lointain) ; le point `(i, j)` est à `x` = `ix` × T + `i` × T / 16 et `z` = `iz` × T + `j` × T / 16, et les bords sont partagés avec les tuiles voisines, comme le terrain.
- `weights` : une grille par biome, dans l'ordre de `biomes`, de 289 entiers de 0 à 255 rangés par ligne (le point `(i, j)` à l'indice `j` × 17 + `i`). **En chaque point, la somme des poids vaut 255.** Entre les points, l'engine interpole linéairement.
- `variant` : variante régionale de la tuile (§9, `variants`), `null` ou un couple `{"ground": …, "roofs": …}` dont chaque membre peut être `null`. Énumération fermée, étendue seulement par ajout : roches et terres `gres_rose`, `calcaire_blanc`, `granite_gris`, `schiste_sombre`, `basalte`, `laterite_rouge`, `craie` ; architecture `tuile_ronde`, `ardoise`, `tuile_plate`, `pierre_seche`, `toit_plat_blanc`, `bois`. La table qui la choisit (lot U4) travaille à grosse maille, 1° au plus fin : aucune coordonnée précise n'est écrite dans le dépôt.
- Taille : moins de 8 Ko par tuile proche (exemple à 3 biomes : 2,8 Ko).

**Manifeste, `layers.biome` :** `present`, `version`, `default_biome` (`temperate_grassland` si rien n'est forcé), `forced` (identifiant imposé par l'option `--biome` du compilateur, ou `null`), `sources` (par exemple `["esa_worldcover_2021", "osm", "dem", "latitude"]`), `shares` (part de chaque biome sur le parcours, en %), `tiles` (`{"near": [[ix, iz], …], "far": […]}`, comme le terrain).

**Validation.** Schéma `docs/contracts/world/biome.schema.json` ; la somme de 255 en chaque point et le nombre de grilles égal au nombre de biomes, que le schéma ne peut pas exprimer, sont contrôlés par `verify` (contrôle ajouté par le lot U2, qui écrit la couche ; `compiler/tests/test_contract_biome.py` le fait déjà sur l'exemple). Exemple : `docs/contracts/world/examples/biome_tile_near_3_biomes.json`.

## 8 quinquies. Couche côte (depuis 1.6)

Couche facultative en fichiers `coast/chunk_<k>.json` (lot U1) : le rivage de la mer (OSM `natural=coastline`) et les plages (`natural=beach`, `natural=sand` au bord de la mer), que l'engine utilise pour la mer animée et les plages (lot U9). La mer elle-même est une aire `sea` de la couche eau (§8).

```json
{
  "version": "1.0",
  "lines": [{"id": "c12", "shore": "cliff", "points": [[0.0, 0.0], [120.0, 40.0]]}],
  "beaches": [{"id": "b3", "kind": "sand", "outer": [[0.0, 0.0], [30.0, 0.0], [30.0, 10.0]], "holes": []}]
}
```

- `lines` : lignes de côte, points (x, z) ; la mer est à droite dans le sens des points, comme pour `natural=coastline`. `shore` : `sand`, `shingle` (galets), `rock` ou `cliff` (falaise).
- `beaches` : polygones de plage, `kind` `sand` ou `shingle`, avec trous.
- Manifeste, `layers.coast` : `present`, `version`, `lines_count`, `beaches_count`, `osm_date`. Schéma : `docs/contracts/world/coast.schema.json`.

## 9. Thèmes : palettes, textures, shader triplanaire

Le thème est indépendant du parcours. Il vit dans `~/OpenRide/Themes/<nom>/` et est choisi dans `config.toml` (`render.theme`). Un thème n'agit que sur le décor, jamais sur le coureur.

```text
Themes/alpes-ete/
  theme.json
  textures/
    grass_albedo.png      herbe, répétable
    rock_albedo.png       roche
    rock_normal.png       facultatif
    snow_albedo.png       neige
    road_albedo.png       route
```

```json
{
  "version": "1.0",
  "name": "Alpes été",
  "terrain": {
    "grass": {"texture": "textures/grass_albedo.png", "color": "#6f9a4a", "scale_m": 6.0},
    "rock":  {"texture": "textures/rock_albedo.png",  "color": "#9a9488", "scale_m": 12.0},
    "snow":  {"texture": null, "color": "#f2f5f8", "scale_m": 8.0},
    "slope_threshold_deg": 22,
    "snow_line_m": 2200,
    "blend_sharpness": 4.0
  },
  "road": {"texture": "textures/road_albedo.png", "color": "#4a4a4d", "width_m": 6.0},
  "buildings": {
    "walls": ["#d9c9a3", "#e6d8b8", "#cdb48a"],
    "roofs": ["#a65a3a", "#4d535c"]
  },
  "vegetation": {"treeline_m": 2000, "max_density_per_ha": 400},
  "sky": {"sun_elevation_deg": 40, "fog_density": 0.0008}
}
```

**Règles**

- Toute clé absente prend la valeur par défaut de l'engine ; une texture absente ou `null` est remplacée par la couleur unie `color`. Un thème peut donc commencer par un seul fichier `theme.json`.
- Le shader triplanaire projette les textures en mètres : `scale_m` est la distance au bout de laquelle la texture se répète, quelle que soit la taille de l'image. Textures recommandées : 1 024 × 1 024 ou 2 048 × 2 048, PNG ou JPEG, répétables sans couture.
- Le shader mélange herbe et roche selon la pente (`slope_threshold_deg`), puis ajoute la neige au-dessus de `snow_line_m`.
- Ajouter un thème = ajouter un dossier ; aucune recompilation des parcours n'est nécessaire.
- Les textures normales, rugosité et autres cartes PBR sont des extensions futures du même format.

**Niveaux de textures (lot P20, ajout compatible).** Clé facultative `texture_levels` : liste `{name, max_px, dir}` (côté maximal en puissance de 2, dossier relatif au thème), par exemple `{"name": "1024 px", "max_px": 1024, "dir": "levels/1024"}`. Chaque chemin de texture est cherché d'abord sous le dossier du niveau retenu (`levels/1024/textures/grass_albedo.png`), puis sous ceux des niveaux inférieurs, puis à la racine ; absent partout : couleur unie, avec un avertissement, jamais d'échec de séance. L'engine retient le niveau du préréglage (1 024 px en `low` et `medium`, 2 048 en `high`) ou celui de `[render] texture_level`, sous un budget de mémoire vidéo (512 Mo en `low`, 1 Go en `medium` et `high`, tailles décompressées mipmaps comprises) ; sans `texture_levels` (liste vide par défaut), il réduit les images du thème au même côté. `theme-check` exige dans chaque niveau la même liste d'images, toutes au plus de `max_px` ; `theme-pack DOSSIER --levels 512,1024,2048` fabrique les niveaux.

**Provenance des images (lot P20).** Fichier facultatif `provenance.toml` à la racine du pack, une entrée `[[image]]` par image : `file` (chemin à la racine du pack), `source` (`cc0` ou `gemini`), `date`, `url` et `license` (CC0) ou `prompt` (consigne exacte, Gemini), `tileable`. Une image `gen_…` sans entrée est refusée, une image `gemini` de plus de 1 024 px aussi, une image `tileable` dont les bords opposés ne se raccordent pas aussi (`theme-pack --fix-seams` les fond) ; un pack sans ce fichier et sans image `gen_` est accepté avec un avertissement.

**Décor vivant (thème 1.2, lot P1).** Clés facultatives, ignorées par un engine qui ne les connaît pas ; le thème par défaut donne un été calme.

| Clé | Contenu | Lot qui l'utilise |
| --- | --- | --- |
| `sky.clouds` | `{coverage, speed_factor, color, altitude_m}` : couverture de 0 à 1, facteur de vitesse par rapport au vent, couleur, altitude | P6 |
| `sky.time_of_day` | `{mode, hour, factor}` : `mode` vaut `fixed`, `real` ou `accelerated` ; heure de 0 à 24 ; facteur d'accélération | P7 (version 2.0) |
| `weather` | `{kind, intensity, morning_mist}` : `kind` vaut `clear`, `mist`, `rain` ou `snow` ; intensité de 0 à 1 ; brume de vallée le matin | P8 |
| `season` | `spring`, `summer`, `autumn` ou `winter` | P18 (version 2.0) |
| `wind` | `{speed_kmh, from_deg, gust_pct}` : vent lu quand `[wind] mode = "theme"` (SRS §11), et vent décoratif de l'engine quand `state` ne porte pas de `wind` | P2, P4 |
| `ambience` | `{volume, birds, insects}`, de 0 à 1 | P9 |
| `fauna` | `{birds, livestock, deer}` : densités de 0 à 1 | P11 |

**Thème 2.0 : pack de biomes (lot U1, version 3.0).** Un thème 2.0 (`"version": "2.0"`) décrit plusieurs biomes au lieu d'un seul paysage ; l'engine les mélange selon la couche `biome` du parcours (§8 quater). Les clés 1.x (`terrain`, `road`, `buildings`, `vegetation`, `sky`, `weather`, `season`, `wind`, `ambience`, `fauna`) restent valables et gardent leur sens. Exemple complet : `docs/contracts/world/examples/theme_2_0_two_biomes.json`.

| Clé | Contenu |
| --- | --- |
| `default_biome` | Biome des tuiles sans couche `biome` ; `temperate_grassland` si absent |
| `biomes` | Un objet par identifiant du §8 quater, toutes clés facultatives : `ground`, `vegetation`, `water`, `sky`, `ambience`, `fauna`, `seasons` |
| `biomes.<id>.ground` | `layers` : de 1 à 3 couches `{name, role, color, texture, normal, scale_m}`, `role` valant `flat` (sol des pentes douces), `steep` (au-delà de `slope_threshold_deg`, projection triplanaire) ou `high` (au-dessus de `high_line_m`), chacun au plus une fois ; `slope_threshold_deg`, `high_line_m` (nombre ou `null`), `blend_sharpness`. Même règle de mélange qu'en 1.x : `flat`, `steep` et `high` y sont l'herbe, la roche et la neige |
| `biomes.<id>.vegetation` | `species` : liste `{kind, weight}`, `kind` parmi `oak`, `beech`, `spruce`, `pine`, `birch`, `larch`, `olive`, `holm_oak`, `cypress`, `stone_pine`, `palm`, `acacia`, `baobab`, `cactus`, `tree_fern`, `reed`, `dwarf_shrub`, `vine_row` (lot U7) ; `max_density_per_ha` ; `treeline_m` (nombre ou `null`) |
| `biomes.<id>.water` | `color`, `turbidity` (0 à 1) : teinte des lacs, rivières et de la mer dans ce biome |
| `biomes.<id>.sky` | `fog_density`, `haze` (0 à 1, brume de chaleur ou d'humidité), `light_tint` (teinte de la lumière du soleil) |
| `biomes.<id>.ambience`, `.fauna` | Mêmes clés que le thème 1.2 |
| `biomes.<id>.seasons` | `calendar` parmi `four` (quatre saisons de P18), `wet_dry` (saison sèche, saison des pluies), `polar` (jour et nuit polaires), `none` ; `offset_months` (−6 à 6, décalage par rapport au calendrier de l'hémisphère) ; `durations_months` : durée de chaque saison dans l'ordre du calendrier, somme 12 |
| `variants` | Un objet par variante régionale (§8 quater) : `rock_color` et `soil_color` pour les roches et terres, `walls` et `roofs` (listes de couleurs, même forme que `buildings` en 1.x) pour l'architecture, `textures` facultatives ; l'identifiant d'architecture choisit aussi le style des bâtiments de l'engine (matière et pente des toits, murs) |
| `surfaces` | `compacted`, `gravel`, `dirt` : `{color, texture, width_m}`, ruban des routes non revêtues (lot U22) |

- Une clé absente d'un biome prend la valeur 1.x du thème ; un biome absent de `biomes` prend toutes les valeurs 1.x. **Un thème 1.x décrit donc le biome `temperate_grassland`**, et tous les autres biomes d'un parcours prennent ses valeurs tant que le thème ne les décrit pas.
- Un lecteur 2.0 lit tous les thèmes 1.x ; un engine d'avant la 3.0 refuse un thème 2.0 (majeur inconnu) et garde le thème par défaut.
- Schéma : `docs/contracts/world/theme.schema.json` (versions 1.x et 2.x).

## 10. Règles de lecture et compatibilité

**Ordre de lecture.** Un lecteur ouvre d'abord `manifest.json`, vérifie `format` et `format_version`, puis charge les couches dont `present` est vrai.

**Couches absentes ou inconnues**

| Cas | Comportement |
| --- | --- |
| `route.json` absent ou invalide | Erreur `route_invalid` ; le parcours n'est pas proposé |
| Couche terrain absente | L'engine dessine le ruban de route sur un sol plat bas, dans le brouillard |
| Couche bâtiments, végétation, poi, eau, routes voisines, segments, biome ou côte absente | Ignorée sans message ; sans couche biome, tout le parcours prend le biome par défaut du thème |
| Couche inconnue dans le manifeste | Ignorée |
| Tuile de terrain manquante | Remplacée par le niveau lointain ou, à défaut, par un sol plat à l'altitude de la route |
| Champ inconnu dans un fichier | Ignoré |

**Versions**

- `format_version` suit le schéma `majeur.mineur`. Un ajout de champ ou de couche augmente le mineur ; un changement de structure, de repère ou d'unité augmente le majeur.
- Un lecteur refuse un `.world` dont le majeur est supérieur au sien, et accepte tout mineur du même majeur.
- Chaque couche a sa propre version dans le manifeste, ce qui permet de régénérer une couche avec un nouvel algorithme sans toucher aux autres.

**Validation.** `openride-compiler verify <nom>.world` contrôle : la structure et le manifeste, le nombre de valeurs de chaque tableau de la route, la cohérence entre `length_m` et les points, les tailles des tuiles de terrain (et, depuis 1.1, la présence des tuiles listées, l'égalité des bords partagés et l'absence de `NaN` à moins de 25 m de la route), les sommes de contrôle SHA-256 optionnelles du manifeste et, depuis 1.6 (avec le lot U2), les tuiles de biome (schéma, somme des poids égale à 255 en chaque point, une grille par biome). Des schémas JSON de chaque fichier sont publiés dans `docs/contracts/world/`.

**Régénération.** Le compilateur peut refaire une couche (`add-layer`) depuis ses caches bruts sans télécharger de nouveau ; refaire la route oblige à refaire les couches qui en dépendent (terrain, bâtiments, végétation, poi, eau, routes voisines, segments). Depuis 1.5, la requête OpenStreetMap demande aussi les prés, les champs et les routes : la première régénération d'une couche OSM d'un parcours compilé avant le lot P22 télécharge donc de nouveau ses données (une fois).

## 11. Exemple de manifeste et tailles attendues

```json
{
  "format": "openride-world",
  "format_version": "1.1",
  "name": "col-du-galibier",
  "created": "2026-10-21T20:30:00+02:00",
  "compiler": {"name": "openride-compiler", "version": "0.1.0"},
  "source": {"gpx": "col-du-galibier.gpx", "gpx_sha256": "<somme de contrôle>"},
  "origin": {"lat": 45.0900, "lon": 6.0600, "alt_m": 1120.5, "utm_zone": "32T"},
  "projection": "utm",
  "route": {
    "present": true, "version": "1.0", "file": "route.json",
    "length_m": 28450.0, "ds_m": 10, "n": 2846, "type": "open",
    "grade_clamped_points": 0, "alt_source": "gpx"
  },
  "layers": {
    "terrain":    {"present": true,  "version": "1.0", "sources": ["copernicus_glo30"], "native_resolution_m": 30,
                   "near_cell_m": 10, "far_cell_m": 50, "road_half_width_m": 3.0,
                   "tiles": {"near": [[0, -1], [0, 0]], "far": [[-1, -1], [-1, 0], [0, -1], [0, 0]]}},
    "buildings":  {"present": false},
    "vegetation": {"present": false, "source": "none"},
    "poi":        {"present": false},
    "water":      {"present": false}
  }
}
```

**Tailles indicatives pour un parcours de 30 km** (estimations de calcul ; mesure du 23 octobre 2026 avec le lot B2 : 65 tuiles proches et 24 lointaines, 3,7 Mo au total pour route et terrain)

| Couche | Ordre de grandeur |
| --- | --- |
| Route | 300 à 400 Ko |
| Terrain proche | 2 à 3 Mo (environ 60 tuiles de 41 Ko) |
| Terrain lointain | 1 Mo environ |
| Bâtiments | 0 à 5 Mo selon les villages traversés |
| Végétation | 1 à 5 Mo |
| Total | 5 à 15 Mo environ |

Une tuile de 101 × 101 échantillons `float32` pèse 40 804 octets.

## 12. Journal des changements

| Version | Date | Changement |
| --- | --- | --- |
| 1.0 | 21 octobre 2026 | Première version |
| 1.0 | 23 octobre 2026 | Précision, sans changement de format : règle exacte d'interpolation de la route (§4), vecteurs de test et schémas publiés. Projection `local_equirectangular` tolérée pour les parcours synthétiques de démonstration |
| 1.1 | 23 octobre 2026 | Ajouts compatibles (lot B2) : `route.alt_source` (§2) ; dans `layers.terrain`, `native_resolution_m`, `road_half_width_m` et la liste `tiles` des tuiles écrites (§5) ; `verify` contrôle aussi la présence des tuiles listées, l'égalité des bords partagés et l'absence de `NaN` à moins de 25 m de la route (§10) |
| 1.1 | 23 octobre 2026 | Précision de rendu, sans changement des données (lot E1) : le terrain lointain est dessiné 2 m plus bas, au lieu de relever le proche de quelques centimètres (§5) |
| 1.1 | 23 octobre 2026 | Publication du schéma JSON des thèmes `docs/contracts/world/theme.schema.json`, du thème par défaut `engine/themes/default/theme.json` et de la sous-commande `openride-compiler theme-check` (§9, lot H7) |
| 1.1 | 23 octobre 2026 | Publication des schémas JSON `buildings.schema.json` et `vegetation.schema.json` (§6 et §7), compteurs `count`, `ignored_count` et `osm_date` dans le manifeste de ces couches, validation `verify` et sous-commande `add-layer buildings\|vegetation` (lot I3) |
| 1.1 | 23 octobre 2026 | Publication des schémas JSON `poi.schema.json` et `water.schema.json` (§8), compteurs `count` / `lines_count` / `areas_count` / `ignored_count` et `osm_date` dans le manifeste, validation `verify` et sous-commande `add-layer poi\|water` (lot I4) |
| 1.1 | 26 octobre 2026 | Ajout compatible (lot O15) : champs facultatifs `stats` (fiche calculée) et `library` (fiche saisie `<trace>.toml`) dans le manifeste (§2) ; un `.world` sans eux reste valide et la fiche est recalculée à la lecture |
| 1.2 | 26 octobre 2026 | Ajouts compatibles (lot P1) : points d'intérêt `wind_turbine` (avec `height_m` facultatif) et `flag` (§8) ; thème 1.2 avec `sky.clouds`, `sky.time_of_day`, `weather`, `season`, `wind`, `ambience` et `fauna` (§9) |
| 1.3 | 27 octobre 2026 | Ajout compatible (lot T1, avec la révision 1.4 du contrat IPC) : couche facultative `segments.json` (§8 bis), entrée `layers.segments` du manifeste (`present`, `version`, `file`, `count`, `manual_count`) et schéma `docs/contracts/world/segments.schema.json` ; un `.world` 1.2 reste valide |
| 1.4 | 27 octobre 2026 | Ajout compatible (lot W1, premier mineur libre après T1) : monde vivant du monde ouvert (§13) : `live`, `origin_kind`, `grid` dans le manifeste, `live.json`, route par parties, couches par tuile en coordonnées relatives au coin, `junctions.json` ; schémas `live`, `route_part`, `junctions` |
| 1.5 | 27 octobre 2026 | Ajout compatible (lot P22) : terrains ouverts `meadow`, `farmland` et `grassland` de la couche végétation, de densité 0 (§7) ; couche facultative `roads/` des routes voisines (§8 ter), entrée `layers.roads` du manifeste (`present`, `version`, `count`, `osm_date`) et schéma `docs/contracts/world/roads.schema.json` ; `verify` les contrôle ; un `.world` 1.3 reste valide |
| 1.6 | 28 octobre 2026 | Ajout compatible (lot U1, partie format, série U avancée avant la 3.0 sur décision du propriétaire) : couche facultative `biome/near` et `biome/far` (§8 quater) et entrée `layers.biome` ; couche facultative `coast/` (§8 quinquies) et entrée `layers.coast` ; aire d'eau `sea` (§8) ; colonne facultative `surface` de la route, `route.surface_source` et `stats.surface_pct` (§4) ; thème 2.0 en pack de biomes (§9). Schémas `biome.schema.json` et `coast.schema.json`, exemples dans `docs/contracts/world/examples/`. La partie IPC et configuration du lot U1 (`hello_ack.config.biome` et `.gravel`, `[render] biome`, `[gravel]`) attend le lot U16. Un `.world` 1.5 reste valide |
| 1.6 | 30 octobre 2026 | Ajout compatible au thème (lot P20, sans changement du format `.world`) : clé `texture_levels` et fichier `provenance.toml` des packs (§9) ; sous-commande `theme-pack` |

## 13. Monde vivant (monde ouvert, série W)

Ajout compatible (lot W1, mineur 1.4 de `format_version`, le premier libre après la 1.3 de T1). Un monde vivant est un `.world` que le générateur `openride-worldgen` prolonge pendant la séance (`docs/2.0/PLAN_SERIE_W.md`, `docs/contracts/worldgen_v1.md`). Il se lit comme un parcours compilé, avec les différences ci-dessous ; un lecteur qui ne connaît pas `live` ne doit pas l'ouvrir (il n'est jamais rangé dans `~/.local/share/openride/routes/`).

**Dossier.** `<cache_dir>/seances/<id>.world/`, avec `<id>` = `ow-<AAAAMMJJ-HHMMSS>` et `cache_dir` = `~/OpenRide/Cache/monde` par défaut.

```text
ow-20261026-201500.world/
  manifest.json            live: true, origin_kind: "utm_grid", grid
  live.json                état courant, réécrit à chaque révision
  junctions.json           carrefours à venir
  route/part_<k>.json      route engagée, par parties de 1 km
  terrain/near/tile_<ix>_<iz>.f32, terrain/far/tile_<ix>_<iz>.f32
  buildings/tile_<ix>_<iz>.json, vegetation/…, water/…, poi/…
```

**Origine et grille.** L'origine est le coin de la grille de 5 km de la zone UTM le plus proche du départ : `E0` et `N0` sont des multiples de 5 000 m. Le manifeste porte `live: true`, `origin_kind: "utm_grid"`, `origin` (latitude, longitude et altitude de ce coin, `utm_zone`) et `grid: {"near_m": 1000, "far_m": 5000, "e0": E0, "n0": N0}`. Les tuiles de la séance coïncident donc avec une grille globale : la tuile proche `(ix, iz)` est le carré global `IX = E0 / 1000 + ix`, `IN = N0 / 1000 − iz − 1` (indices de l'est et du nord, en kilomètres) ; même règle à 5 km pour les tuiles lointaines. Toute la séance reste dans la zone UTM du départ. Dans le manifeste, `route` décrit la route à l'ouverture (`file` = `route/`, longueur et nombre de points de la première révision) ; la longueur courante est dans `live.json`.

**`live.json`** (schéma `live.schema.json`), réécrit de façon atomique à chaque révision :

```json
{
  "version": "1.0",
  "revision": 12,
  "route": {"parts": 5, "length_m": 4380.0, "changed_from_part": 3},
  "tiles": {"near": [[0, 0], [1, 0], [1, -1]], "far": [[0, 0], [0, -1]]},
  "layer_tiles": [[0, 0], [1, 0]],
  "status": "ok"
}
```

**Route par parties** (schéma `route_part.schema.json`). `route/part_<k>.json` a les colonnes de `route.json` (§4) plus `s0_m` = 1 000 × `k`. La partie `k` contient les points de `s` = 1 000 `k` à `s` = 1 000 (`k` + 1) inclus, au pas de 10 m (la dernière partie s'arrête à `length_m`) ; le bord est partagé avec la partie suivante. `s` est croissant, `type` vaut `open`. Une partie publiée n'est réécrite qu'au-delà du point de verrouillage du carrefour dont la branche change : `changed_from_part` dit à partir de quelle partie relire. La route assemblée suit la règle d'interpolation du §4.

**Couches par carré.** Le terrain garde le format du §5. Les couches `buildings`, `vegetation`, `water` et `poi` sont rangées par tuile proche, `<couche>/tile_<ix>_<iz>.json`, avec les schémas des fichiers `chunk_<k>.json` (§6 à §8), à une différence près : **les coordonnées horizontales sont relatives au coin de la tuile** (`x − 1 000 ix`, `z − 1 000 iz`) ; les altitudes `y`, `base_y` et `level_y` restent absolues. Ainsi les carrés du cache, communs à toutes les séances, sont liés dans le dossier de séance (liens symboliques) sans être réécrits. Un objet appartient à la tuile qui contient son centre.

**`junctions.json`** (schéma `junctions.schema.json`), réécrit de façon atomique : carrefours à moins de 3 km devant le cycliste.

```json
{
  "version": "1.0",
  "revision": 12,
  "junctions": [
    {"id": "j123456", "s_m": 2410.0, "x": 1520.4, "z": -830.2, "lock_s_m": 2380.0,
     "default": 1, "chosen": 1, "locked": false,
     "branches": [
       {"index": 0, "heading_deg": 275.0, "angle_deg": -85.0, "road_class": "m", "grade_pct_500m": 6.2,
        "dead_end": false, "preview": {"x": [1520.4, 1510.4], "y": [612.0, 612.6], "z": [-830.2, -831.0]}},
       {"index": 1, "heading_deg": 2.0, "angle_deg": 0.0, "road_class": "t", "grade_pct_500m": -1.4,
        "dead_end": false, "preview": {"x": [1520.4, 1520.7], "y": [612.0, 611.9], "z": [-830.2, -840.2]}}
     ]}
  ]
}
```

- `lock_s_m` = `s_m` − 30 : au-delà, `locked` est vrai et le choix est figé.
- `angle_deg` : relatif au cap d'arrivée, positif à droite, dans ]−180, 180] ; au plus 4 branches, demi-tour exclu.
- `road_class` : `p` (primary), `s` (secondary), `t` (tertiary), `m` (unclassified, residential, living_street, road, service hors parkings et allées privées), `c` (piste cyclable, chemin cyclable revêtu), `k` (track revêtue). Jamais d'autoroute, de voie rapide (trunk), de voie non revêtue (décision W-Q2) ni de voie interdite aux vélos.
- `preview` : amorce de 500 m de la branche (51 points au pas de 10 m, positions dans le repère de la séance, altitude du profil), calculée avant que le carrefour soit à moins de 300 m.

**Écriture.** Le générateur écrit chaque fichier dans un fichier temporaire voisin puis le renomme ; `live.json` est écrit en dernier, après les parties, les tuiles et `junctions.json` qu'il annonce.
