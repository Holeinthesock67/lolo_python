# Lot U23 – Engine : constructions et faune propres à chaque biome

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Engine : constructions et faune propres à chaque biome | GDScript + shader | U5, U12, Y8 | Moyenne | En PR, **version 4.0** (demande du propriétaire du 6 novembre, lancée le 7 novembre) |

## 1. Objectif

Demande du propriétaire (6 novembre, 14 h 40) : « adapter les constructions (bâtiments) et la faune aux biomes », lancée le 7 novembre (« Lance aussi les constructions et faunes différentes par biome »).

Avant ce lot, la table `BIOME_STYLES` de `building_styles.gd` (Y8) existait mais n'était branchée nulle part : tous les bâtiments OSM prenaient le style `tuile_plate`, quel que soit le biome. Le lot U14 (variantes régionales de la tuile) laisse explicitement hors périmètre « les bâtiments modélisés par région (églises, chalets) ». La faune de U12 couvrait 13 biomes sur 16, sans rien au pôle ni sur les volcans, sans grand mammifère propre à la jungle ni éléphant en savane.

## 2. Lecture retenue

« Constructions différentes par biome » = un **style d'habitat** par biome, posé sur les bâtiments OSM existants (pas de nouveaux bâtiments, pas de maillage modélisé à la main) : matières des murs et du toit, pente, débord, teintes. Cela garde les contours, les hauteurs et le nombre de bâtiments d'OSM, donc le coût GPU des bâtiments ne bouge pas (même nombre de triangles, même matériau unique).

« Faune différente par biome » = compléter les biomes que U12 laissait vides ou pauvres, avec les mêmes comportements (troupeau, bête qui fuit) et les mêmes budgets `living(preset)`.

## 3. Ce qui est fait

**Bâtiments**
- `osm_streamer.gd` : avec un modèle de biome actif (couche biome du parcours ou `--biome=`), chaque bâtiment reçoit la clé `style` au centre de son contour, par `biome_model.gd` `building_style_at(x, z)` : variante `roofs` de la tuile (U4) si elle existe, sinon style du biome dominant. Sans couche biome ni forçage : rien ne change (tous les parcours d'aujourd'hui).
- `building_styles.gd` : sept styles d'habitat propres aux biomes (`BIOME_ONLY_STYLES`) :

| Biome | Style | Habillage |
| --- | --- | --- |
| alpine | `chalet` | rez-de-chaussée en moellons, étage en madriers de mélèze, lauzes, pente de 24°, débord de 1,2 m |
| boreal_forest, tundra, polar | `bois_peint` | bardage peint (rouge de Falun, ocre, blanc, gris bleu), tôle sombre, débord de 0,5 m |
| sand_desert, rock_desert | `pise` | terre crue lissée et fissurée, toit plat couleur de terre |
| savanna | `case` | terre crue, chaume en pointe (quatre pans, 40°), débord de 0,7 m ; huttes et greniers aussi |
| jungle | `paillote` | bois, chaume à 38°, débord de 1 m |
| volcanic | `basalte` | pierre sombre, ardoise |
| wetland | `chaumiere` | chaux blanche, chaume à 50° |

  Les biomes tempérés, la Méditerranée, la steppe et le littoral gardent leur style de Y8 (`tuile_plate`, `tuile_ronde`, `pierre_seche`, `ardoise`). Chaque style peut porter son débord (`overhang_m`) et ses palettes (`palettes`, qui remplace aussi le cas particulier de `toit_plat_blanc`).
- `building.gdshader` : deux matières de mur (terre crue `WALL_ADOBE`, chalet `WALL_CHALET`) et une matière de toit (chaume `ROOF_THATCH`). Le code d'habillage (UV2.y) passe à 16 matières de mur : mur + 16 × ouvertures + 128 × toit + 1 024 × partie + 2 048 × égout (plus grand code sous 2^24).

**Faune** (`fauna_renderer.gd`, `fauna_placer.gd`) : six espèces construites par code, de 800 à 1 100 triangles :

| Biome | Ajout |
| --- | --- |
| savanna | éléphants (2 à 6, à plus de 150 m de la route), antilopes (6 à 16) ; le chevreuil P11 devient une antilope |
| steppe | antilopes (saïgas) ; le chevreuil P11 devient une antilope |
| polar | bœufs musqués, ours blancs (1 ou 2, à plus de 150 m) |
| tundra | bœufs musqués avec les rennes |
| volcanic | chèvres ; le bétail des prés devient des chèvres |
| mediterranean | chèvres avec les moutons |
| jungle | singes près de la route |

Thème par défaut : densités `fauna` relevées là où elles valaient 0 et empêchaient ces groupes (`polar.deer` 0,3, `volcanic.livestock` 0,3, `jungle.deer` 0,5 ; les rôles P11 correspondants restent retirés par `BIOME_SPECIES`).

### Étape 2 : cases rondes, yourtes, pilotis

Demandée par le propriétaire le 07/11 (« Lance tout ») : les formes propres laissées hors périmètre de l'étape 1, sans coût GPU mesurable.

- `building_styles.gd` : forme `SHAPE_CONE` et deux clés de style. `round` (part, longueur au plus `max_m`, pente du cône, matières propres) : petites maisons et dépendances dont le rectangle orienté fait au plus 1,6 fois sa largeur. `stilts` (part, hauteur du plancher) : maisons seulement.

| Style | Rondes | Pilotis |
| --- | --- | --- |
| `case` (savane) | 85 % des maisons et huttes jusqu'à 10 m, chaume conique à 40° | non |
| `paillote` (jungle) | 35 % jusqu'à 9 m, chaume à 42° | 70 % des maisons, plancher à 1,5 m |
| `yourte` (steppe, nouveau) | 55 % jusqu'à 9 m : feutre clair (murs et cône à 24°, matière lisse des toits plats) | non |

  La steppe passe de `pierre_seche` à `yourte` : ses maisons plus grandes restent en pierre (85 %) ou en bois sous ardoise. `pierre_seche` reste la variante régionale U1.
- `building_mesh.gd` : le contour d'une case ronde devient un polygone régulier de 12 côtés, de même aire, centré sur le rectangle orienté (rayon borné par ses demi-côtés). Le toit est le minimum de 12 plans (`cone_planes`), avec le même débord et le même découpage que les toits à pans. Jamais de case ronde pour un contour à cour intérieure. Une maison sur pilotis a son plancher relevé, ses murs partent du plancher (sans socle), son dessous est en voliges (dessin des dessous de débord) et un poteau de bois carré de 0,22 m est posé sous chaque angle (12 au plus). Les tirages viennent du hachage de l'identifiant (`ROUND_SALT`, `STILTS_SALT`).
- Murs : un segment n'est plus coupé qu'aux points où le plan le plus bas change vraiment. Les coupures entre deux plans qui ne sont pas le toit à cet endroit ne changeaient pas la forme et doublaient des murs. Le test de 500 maisons passe ainsi de 30 208 à 26 880 sommets, pour une forme identique.
- Une case ronde fait au plus 400 triangles (test). Les côtés de 1,5 m environ ne portent pas de fenêtres ni de porte.

## 4. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe (`test_building_mesh.gd`, `test_fauna_mesh.gd`, `test_fauna_biomes.gd` étendus).
2. Sans couche biome ni forçage : bâtiments et faune identiques à avant (tests de L1, Y8, P11, U12 inchangés).
3. Vitrine (`tests/vitrine_rendu.gd`, vues `styles_biomes`, `styles_biomes_pres`, `styles_biomes_pres2`, `faune_biomes` ; étape 2 : `habitat_rond`, `habitat_pilotis`, `habitat_yourtes`) : captures low, medium et high validées par le propriétaire avant fusion.
4. Budgets GPU 8 / 12 / 14 ms (low / medium / high) tenus sur le PC (GTX 1060) : banc demandé au fil « Fusionner les PR et séquencer les mesures », par exemple `vitrine_biomes` ou un parcours `--biome=` de U19 (alpine, savanna, sand_desert) contre main. Le nombre de triangles des bâtiments ne change pas ; le shader des bâtiments gagne trois branches ; chaque nouvelle espèce ajoute un MultiMesh vide tant qu'elle n'est pas dans le biome.

## 5. Hors périmètre (suite possible)

- Formes propres encore absentes : toits de tourbe, minarets, échelle ou escalier des pilotis, porte des cases rondes.
- Variantes régionales de couleur des murs et des toits (`variants.*.walls/roofs` du thème) : lot U14.
- Sons des nouvelles espèces (barrissement, grognement), animaux qui traversent.
