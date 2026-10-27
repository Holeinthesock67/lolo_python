# Lot U1 – Contrat : couche `biome`, côte et mer, surface de la route, thème 2.0 en pack de biomes, configuration et IPC (version 3.0)

## 1. Objectif

**Version 3.0.** Fixer, avant tout code de la série U, les ajouts au format `.world`, au format des thèmes, à la configuration et à l'IPC que les autres lots implémentent : poids de biome par tuile, variante régionale, mer et côte, surface de la route (option « gravel »), thème 2.0 décrit comme un pack de biomes, réglages `[render] biome` et `[gravel]`. C'est une décision du propriétaire, comme N1, P1 et W1 : le lot rédige les ajouts, le propriétaire les valide en fusionnant.

**Lot interne (décision du propriétaire).**

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` (en entier, surtout §6, §7, §10 et §11), `docs/lots/LOT_U0_decisions_biomes.md` (identifiants des biomes), `docs/lots/00_INDEX.md` (paragraphe « Série U »).
2. `docs/contracts/world_format_v1.md` §2, §4, §5, §8, §9 et §10 ; schémas `docs/contracts/world/manifest.schema.json`, `route.schema.json`, `water.schema.json`, `theme.schema.json`.
3. `docs/contracts/ipc_v1.md` §8 (révisions) et `docs/contracts/ipc/hello_ack.schema.json` ; `docs/SPECIFICATION_GENERALE.md` §6.
4. Contrats des lots qui précèdent : `LOT_P1_contrat_vent_decor.md` (thème 1.2, `[wind] max_grade_offset_pct`), `LOT_P20_packs_textures_performance.md` (`texture_levels`), `LOT_W1_contrat_monde_vivant.md` (§4.5 classes de route).

## 3. Prérequis

Version 2.0 publiée : séries P (P1, P18, P20) et W (W1) fusionnées. **Numérotation :** l'IPC prend la première révision libre à la fusion de U1 (1.6 si W1 a pris la 1.5) ; le format `.world` prend le mineur libre suivant celui de W1 (1.3 si W1 a pris la 1.2) ; le thème passe en 2.0 (changement de structure, lecture des 1.x garantie).

## 4. Travail demandé

### 4.1 Couche `biome` (`world_format_v1.md`, nouvelle section)

- **Fichiers :** `biome/near/tile_<ix>_<iz>.json` et `biome/far/tile_<ix>_<iz>.json`, mêmes indices et mêmes tuiles que la couche terrain (§5) ; une tuile terrain sans fichier de biome prend le biome par défaut du manifeste.
- **Contenu d'une tuile :** `version` (`"1.0"`), `biomes` : liste de 1 à 4 identifiants (ceux du lot U0), `grid` : 17 (16 × 16 cases de 62,5 m en proche, de 312,5 m en lointain, bords partagés avec les voisines comme le terrain), `weights` : une grille 17 × 17 d'entiers de 0 à 255 par biome de la liste, rangée par ligne comme les altitudes ; en chaque point la somme des poids vaut 255. `variant` : identifiant de variante régionale (§4.3) ou `null`.
- **Manifeste :** `layers.biome` : `present`, `version`, `default_biome` (`temperate_grassland` si rien n'est forcé), `forced` (identifiant ou `null`, option `--biome`), `sources` (par exemple `["esa_worldcover_2021", "osm", "dem", "latitude"]`), `shares` (part de chaque biome sur le parcours, en %), `tiles` (comme le terrain).
- **Un parcours sans couche `biome` garde le rendu actuel** (thème 1.x ou biome par défaut du thème 2.0).

### 4.2 Mer et côte

- Couche eau (§8) : nouvelle sorte de surface `sea` (polygones de mer refermés sur le bord de l'étendue du terrain), à côté des lacs et rivières.
- Nouvelle couche facultative `coast` : `coast/chunk_<k>.json` par tronçon de 1 km comme les bâtiments, lignes de côte (OSM `natural=coastline`) avec la sorte du rivage (`sand`, `shingle`, `rock`, `cliff`) et polygones de plage (`natural=beach`, `natural=sand` au bord de la mer) ; schéma `coast.schema.json`.

### 4.3 Variantes régionales

- Énumération fermée, extensible par ajout : roches et terres (`gres_rose`, `calcaire_blanc`, `granite_gris`, `schiste_sombre`, `basalte`, `laterite_rouge`, `craie`) et architecture (`tuile_ronde`, `ardoise`, `tuile_plate`, `pierre_seche`, `toit_plat_blanc`, `bois`). Une variante de tuile est un couple `{"ground": …, "roofs": …}`.
- La table d'ébauche qui choisit la variante (lot U4) travaille à grosse maille (1° au plus fin) : aucune coordonnée précise n'est écrite dans le dépôt.

### 4.4 Surface de la route (option « gravel »)

- `route.json` : colonne facultative `surface`, une valeur par point parmi `paved` (défaut), `compacted`, `gravel`, `dirt`. Une route sans colonne est entièrement `paved`.
- **Surface imposée (décision U-Q8 du 27 octobre) :** `[gravel] mode` = `compacted`, `gravel` ou `dirt` fait rouler et afficher **tout le parcours** dans cette surface, quelle que soit sa colonne `surface` ; c'est le moyen de faire du gravel sur une trace habituelle, revêtue de bout en bout. `auto` suit la colonne `surface` (portions non revêtues réelles d'OSM, monde ouvert) ; `off` roule tout en bitume.
- Manifeste : `route.surface_source` (`osm` ou `none`) et part de chaque surface dans `stats` quand la fiche existe.
- Monde ouvert : nouvelle classe de route `g` (voies non revêtues : `highway=track`, `path` non revêtu, `surface` non revêtue), admise par le graphe et le navigateur **seulement** quand `[gravel] mode` n'est pas `off` ; les parties de route (`route/part_<k>.json`) portent la même colonne `surface`.

### 4.5 Thème 2.0 : pack de biomes (`world_format_v1.md` §9, `theme.schema.json`)

- `version` `"2.0"`, `default_biome`, `biomes` : un objet par identifiant, chacun avec `ground` (jusqu'à trois couches `{name, color, texture, normal, scale_m}` choisies par la pente et l'altitude comme aujourd'hui), `vegetation` (`species` : liste `{kind, weight}`, `max_density_per_ha`, `treeline_m`), `water` (`color`, `turbidity`), `sky` (`fog_density`, `haze`, `light_tint`), `ambience` et `fauna` (mêmes clés que le thème 1.2), `seasons` (`calendar` parmi `four`, `wet_dry`, `polar`, `none` ; décalage et durée des saisons en mois).
- `variants` : un objet par variante régionale (`rock_color`, `soil_color`, `walls`, `roofs`, textures facultatives).
- `surfaces` : `gravel`, `dirt`, `compacted` (couleur, texture facultative, largeur), pour le ruban du lot U22.
- `texture_levels` de P20 inchangé ; textures cherchées dans le niveau choisi, puis à la racine.
- **Thème 1.x :** toujours lu ; il décrit le biome `temperate_grassland` (et tous les biomes absents d'un thème 2.0 incomplet prennent ses valeurs).

### 4.6 Configuration (SRS §11) et IPC

- `[render] biome` : `"auto"` (défaut) ou un identifiant ; force le biome de tout le parcours au rendu, sans recompiler.
- `[gravel]` : `mode` parmi `off` (défaut), `auto`, `compacted`, `gravel`, `dirt` (§4.4), `factor_compacted` (2,0), `factor_gravel` (2,5), `factor_dirt` (3,0), bornes 1 à 3.
- **IPC (révision libre suivante, 1.6 provisoire) :** deux clés facultatives dans `hello_ack.config` : `biome` (chaîne) et `gravel` (chaîne, valeur de `[gravel] mode`). Aucun nouveau message : le menu passe par `list_settings` et `set_setting` (O3, O4). Aucun champ de plus dans `state` : l'engine lit la surface dans la route.

## 5. Fichiers concernés

- **Modifiés :** `docs/contracts/world_format_v1.md` (sections et journal), `docs/contracts/world/manifest.schema.json`, `route.schema.json`, `water.schema.json`, `theme.schema.json`, `docs/contracts/ipc_v1.md` (§8 et journal), `docs/contracts/ipc/hello_ack.schema.json`, `docs/SRS_v1.1.md` §11, `docs/SPECIFICATION_GENERALE.md` (§5.3 et §6), `docs/3.0/PLAN_SERIE_U.md` (renvoi vers ce contrat).
- **Nouveaux :** `docs/contracts/world/biome.schema.json`, `coast.schema.json`, exemples (une tuile de biome à 3 biomes, un thème 2.0 minimal à deux biomes), `compiler/tests/test_contract_biome.py` (validation des exemples, thème 1.0 par défaut toujours valide).
- **Interdits :** tout code de production.

## 6. Modifications de contrat autorisées

Celles du §4, et elles seules : ajouts compatibles pour l'IPC (`v` reste 1) et le format `.world` (le majeur reste 1) ; thème 2.0 avec lecture des 1.x garantie.

## 7. Critères d'acceptation

1. Chaque exemple est valide pour son schéma ; `engine/themes/default/theme.json` (1.x) reste valide ; un manifeste sans `layers.biome` et une route sans `surface` restent valides.
2. Une tuile dont la somme des poids diffère de 255 en un point est refusée par le schéma ou par le test.
3. Exemple de tuile de biome proche : moins de 8 Ko.
4. Journal des changements à jour dans les contrats touchés ; `pytest` passe dans `core/` et `compiler/`.
5. Le propriétaire a validé la numérotation, les identifiants et les questions U-Q6 à U-Q13 du plan §11.

## 8. Hors périmètre

Tout code. U2 à U22 implémentent ce contrat.
