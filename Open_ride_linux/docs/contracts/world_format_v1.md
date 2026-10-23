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
```

Les couches vivent par morceaux : `<k>` est l'indice du tronçon de route de 1 km (`k` = partie entière de `s` / 1000, `s` étant la position du point de route le plus proche de l'objet). Le terrain, lui, est découpé en tuiles fixes dans le repère du monde (§5).

**Le manifeste `manifest.json`** est lu en premier. Il donne :

- `format`, `format_version` (§10), `name`, date de création, version du compilateur ;
- la source (nom du GPX et somme SHA-256) ;
- l'origine et la projection (§3) ;
- pour chaque couche : `present` (vrai ou faux), `version`, et ses paramètres propres ;
- depuis la version 1.1 : `route.alt_source`, origine de l'altitude de la route (`gpx` ou nom de la source MNT, par exemple `copernicus_glo30`).

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

**Règle d'interpolation, identique en Python et en GDScript (précisée le 23 octobre 2026) :**

- Abscisses des points : `s_i = i × ds_m` pour `i < n − 1`, et `s_{n−1} = length_m`.
- Pour une position `s` : un parcours `loop` la ramène modulo `length_m`, les autres la bornent à `[0, length_m]`. Le segment `[i, i+1]` qui contient `s` donne `u = (s − s_i) / (s_{i+1} − s_i)` ; au point final, `i = n − 2`.
- `grade_pct`, `lat`, `lon`, `alt_m` : interpolation linéaire en `u`.
- Cap : `h_i + u × d`, où `d` est l'écart le plus court de `h_i` vers `h_{i+1}` (dans ]−180, 180]), ramené dans [0, 360).
- Position `(x, alt_m, z)` : Catmull-Rom centripète (Barry-Goldman, α = 0,5) sur `P_{i−1}, P_i, P_{i+1}, P_{i+2}`, distances mesurées en 3D. Nœuds `t0 = 0`, `t1 = t0 + |P_i − P_{i−1}|^0,5`, `t2 = t1 + |P_{i+1} − P_i|^0,5`, `t3 = t2 + |P_{i+2} − P_{i+1}|^0,5` (toute distance inférieure à 1e-6 m vaut 1e-6 m), paramètre `t = t1 + u × (t2 − t1)`, puis :
  `A1 = (t1−t)/(t1−t0)·P_{i−1} + (t−t0)/(t1−t0)·P_i`, `A2 = (t2−t)/(t2−t1)·P_i + (t−t1)/(t2−t1)·P_{i+1}`, `A3 = (t3−t)/(t3−t2)·P_{i+1} + (t−t2)/(t3−t2)·P_{i+2}`, `B1 = (t2−t)/(t2−t0)·A1 + (t−t0)/(t2−t0)·A2`, `B2 = (t3−t)/(t3−t1)·A2 + (t−t1)/(t3−t1)·A3`, `C = (t2−t)/(t2−t1)·B1 + (t−t1)/(t2−t1)·B2`.
- Extrémités d'un parcours ouvert : points fantômes `P_{−1} = 2·P_0 − P_1` et `P_n = 2·P_{n−1} − P_{n−2}`. Boucle : indices circulaires sur les `n − 1` points distincts (le voisin avant `P_0` est `P_{n−2}`, le voisin après `P_{n−1} = P_0` est `P_1`). `out_and_back` se lit comme `open`.
- Près d'un segment plus court que `ds_m`, la spline centripète avance à vitesse légèrement non uniforme : c'est attendu.

**Vecteurs de test :** `docs/contracts/world/route_test_vectors.json`, générés par l'implémentation de référence (`python -m openride_core.tools.route_vectors`) et vérifiés en GDScript (`engine/tests/test_route_vectors.gd`). Schémas : `docs/contracts/world/manifest.schema.json` et `route.schema.json`.

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

**Terrain lointain.** Il masque le bord du terrain proche. Les tuiles lointaines recouvrent le terrain proche ; l'engine dessine le proche par-dessus, légèrement relevé de quelques centimètres pour éviter le scintillement.

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

- `kind` : `wood` (forêt), `scrub` (broussailles), `orchard` (verger) ; d'autres valeurs sont ignorées.
- `density` : de 0 à 1, proportion du maximum fixé par le thème. Les arbres sont placés de façon déterministe : la graine dérive de `id`, donc le paysage est identique d'une séance à l'autre.
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

- `kind` : `church_bell`, `river`, `livestock`, `village`, `viewpoint` ; une valeur inconnue est ignorée.
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
- `areas` : plans d'eau, avec `level_y` pour l'altitude de la surface.
- Ces deux couches arrivent au sprint 6 ; le format est figé dès maintenant pour qu'un parcours compilé plus tôt puisse recevoir ces couches plus tard.

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

## 10. Règles de lecture et compatibilité

**Ordre de lecture.** Un lecteur ouvre d'abord `manifest.json`, vérifie `format` et `format_version`, puis charge les couches dont `present` est vrai.

**Couches absentes ou inconnues**

| Cas | Comportement |
| --- | --- |
| `route.json` absent ou invalide | Erreur `route_invalid` ; le parcours n'est pas proposé |
| Couche terrain absente | L'engine dessine le ruban de route sur un sol plat bas, dans le brouillard |
| Couche bâtiments, végétation, poi ou eau absente | Ignorée sans message |
| Couche inconnue dans le manifeste | Ignorée |
| Tuile de terrain manquante | Remplacée par le niveau lointain ou, à défaut, par un sol plat à l'altitude de la route |
| Champ inconnu dans un fichier | Ignoré |

**Versions**

- `format_version` suit le schéma `majeur.mineur`. Un ajout de champ ou de couche augmente le mineur ; un changement de structure, de repère ou d'unité augmente le majeur.
- Un lecteur refuse un `.world` dont le majeur est supérieur au sien, et accepte tout mineur du même majeur.
- Chaque couche a sa propre version dans le manifeste, ce qui permet de régénérer une couche avec un nouvel algorithme sans toucher aux autres.

**Validation.** `openride-compiler verify <nom>.world` contrôle : la structure et le manifeste, le nombre de valeurs de chaque tableau de la route, la cohérence entre `length_m` et les points, les tailles des tuiles de terrain (et, depuis 1.1, la présence des tuiles listées, l'égalité des bords partagés et l'absence de `NaN` à moins de 25 m de la route), et les sommes de contrôle SHA-256 optionnelles du manifeste. Des schémas JSON de chaque fichier sont publiés dans `docs/contracts/world/`.

**Régénération.** Le compilateur peut refaire une couche (`add-layer`) depuis ses caches bruts sans télécharger de nouveau ; refaire la route oblige à refaire les couches qui en dépendent (terrain, bâtiments, végétation, poi, eau).

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
| 1.1 | 23 octobre 2026 | Publication du schéma JSON des thèmes `docs/contracts/world/theme.schema.json`, du thème par défaut `engine/themes/default/theme.json` et de la sous-commande `openride-compiler theme-check` (§9, lot H7) |
| 1.1 | 23 octobre 2026 | Publication des schémas JSON `buildings.schema.json` et `vegetation.schema.json` (§6 et §7), compteurs `count`, `ignored_count` et `osm_date` dans le manifeste de ces couches, validation `verify` et sous-commande `add-layer buildings\|vegetation` (lot I3) |
| 1.1 | 23 octobre 2026 | Publication des schémas JSON `poi.schema.json` et `water.schema.json` (§8), compteurs `count` / `lines_count` / `areas_count` / `ignored_count` et `osm_date` dans le manifeste, validation `verify` et sous-commande `add-layer poi\|water` (lot I4) |
