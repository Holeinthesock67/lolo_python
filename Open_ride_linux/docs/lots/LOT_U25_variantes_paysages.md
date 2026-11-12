# Lot U25 – Paysages en variantes : canyons rouges, fjords, îles volcaniques, rizières

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Paysages célèbres posés en variantes des biomes existants (canyons, fjords, îles volcaniques, rizières), partie 1 : contrat, pose, sol et arbres | Python, GDScript | U4, U14, U24 | Moyenne | En PR le 12 novembre, **version 6.0** |

## 1. Objectif

Étude des biomes de la 6.0 (`/mnt/project-files/plans/ETUDE_BIOMES_V6.md`, §4), ordre validé par le
propriétaire le 12 novembre (« ok 1 à 4 ») : canyons rouges, fjords, îles volcaniques et rizières ne sont
pas de nouveaux biomes mais des **variantes de biomes existants**, peu coûteuses. Principe « pas d'exception » :
un paysage qui ne change que la végétation, les toits, la roche ou le sol n'a pas besoin d'un identifiant de
biome (ni d'un menu, ni d'un nom dans l'IPC ; son sol prend un emplacement de paysage du shader, pas un biome).

## 2. Ce qui change (partie 1)

- **Contrat** (Format `.world` v1 §8 quater et §9, ajout compatible) : la variante d'une tuile devient
  `{"ground", "roofs", "landscape"}`. `landscape` est facultatif (absent = `null`, tuiles d'avant ce lot) et
  vaut `canyon`, `fjord`, `ile_volcanique` ou `rizieres`. Toit `bois_peint` ajouté (style d'habitat du Nord
  du lot U23, devenu variante du contrat). Thème 2.0 : section `landscapes`,
  `{"<paysage>": {"biomes": {"<biome de base>": <bloc partiel>}}}`.
- **Pose** : même mécanisme que les variantes régionales du lot U4, déjà commun au compilateur
  (`biomes.build_biome_layer`) et au monde ouvert (`worldgen/biome_tiles.py` du lot W17, en PR, qui appelle la
  même fonction), donc **aucune règle dupliquée** :
  `regional.assign_variants` et des zones à grosse maille (degrés entiers) de `data/regional_variants.toml`.
  Pas de nouvelle table : `data/biome_zones.toml` (lot Atlantique) décide du biome, cette table-ci de la
  variante.

  | Paysage | Zones (degrés entiers) | Biomes de base (thème par défaut) | Autres membres |
  | --- | --- | --- | --- |
  | `canyon` | plateau du Colorado, 34–41° N, 114–106° O | désert de roche, désert de sable, steppe | `gres_rose` |
  | `fjord` | côte ouest de la Norvège 58–65° N, 4–10° E ; Nordland et Lofoten 65–71° N, 10–20° E | côte, forêt boréale, forêt tempérée, prairie, alpin, toundra | `schiste_sombre`, `bois_peint` |
  | `ile_volcanique` | Canaries, Madère, Açores | volcanique, prairie, forêt tempérée, méditerranéen, steppe | `basalte` |
  | `rizieres` | Asie du Sud-Est et sud de la Chine, 11° S–27° N, 95–126° E | cultures, zone humide | — |

  Une tuile lointaine prend la variante majoritaire (les trois membres ensemble) de ses tuiles proches.
- **Engine** : `biome_model.params(biome, …, variant)` fusionne le bloc du biome dans le paysage, section par
  section (une clé donnée remplace celle du biome, un tableau est remplacé en entier) ; un biome que le
  paysage ne décrit pas reste tel quel. `variant_at(x, z)` donne la variante d'un point (aussi utilisée par
  `building_style_at`). La végétation suit le paysage de la tuile : `VegetationPlacer.look_at` (arbres
  proches, `assign_species`), densité de la tuile (`tree_renderer.gd`) et bouquets lointains
  (`forest_impostors.gd`, plafond de densité qui compte les paysages).
- **Sol du paysage** (demande du propriétaire du 12 novembre : « Fjord c'est très jaune le sol ») : le shader
  des terrains (`terrain_biomes.gdshader`) a un emplacement de sol par biome, puis un par couple
  (paysage, biome de base) dont le thème décrit `ground` (au plus 16, `BiomeTextures.landscape_slots`) ; une
  tuile du paysage renvoie ses biomes vers ces emplacements (`slot_of`). Sans rides de sable : le sol du
  paysage remplace celui du biome. Le changement de sol se fait au bord de la tuile de 1 km où commence la zone
  (les zones font au moins 1°, une bordure par zone). Thème par défaut :

  | Paysage et biome | Sol plat | Roche des pentes | Règle |
  | --- | --- | --- | --- |
  | fjord : côte, prairie, forêt boréale, alpin | herbe rase, pré, mousse, pelouse (verts) | gneiss sombre `#4a4d50` | pente 18°, neige dès 1 100 m |
  | canyon : désert de roche, steppe | sable rouge, armoise | grès rouge `#a3452a` | pente 16° et 18° |
  | île volcanique : prairie, méditerranéen | herbe sèche sur cendres, cendres et genêts | basalte `#3d3b3a` | pente 20° |
  | rizières : cultures, zone humide | rizière verte, rizière inondée | diguette, berge | pente 22° |

- **Thème par défaut** : blocs `vegetation` des quatre paysages (densité maximale 450 arbres/ha, sous le
  plafond de 600 de la forêt tempérée) ; couleurs de la variante `bois_peint`.

  | Paysage | Arbres |
  | --- | --- |
  | `canyon` | pins (pins pignons), cyprès (genévriers), arbustes ; 25 à 30 arbres/ha |
  | `fjord` | bouleaux et épicéas, quelques pins ; plus de palmiers ni de pins parasols sur la côte ; limite des arbres 700 m sur la côte, 900 m ailleurs |
  | `ile_volcanique` | pinède canarienne (pins) jusqu'à 2 100 m, laurisylve (chênes verts, fougères arborescentes) en forêt, palmiers en méditerranéen |
  | `rizieres` | palmiers et roseaux, sans rangs de vigne |

- **Compilateur** : `--variant GROUND,ROOFS[,LANDSCAPE]` (exemple `gres_rose,,canyon`) ; `verify` accepte la
  variante à deux ou trois membres ; rapport `variantes (…) : gres_rose/—/canyon 12, …`.

## 3. Licences

Aucun fichier extérieur : la table est écrite à la main au degré près, les arbres sont les espèces
construites par code du lot U7. Rien à attribuer.

## 4. Critères

1. La table livrée pose chaque paysage sur un point de chacune de ses zones et rien hors des zones
   (`test_regional.py::test_shipped_landscapes`).
2. Le schéma accepte une tuile sans `landscape` et avec chacun des quatre ; il refuse un paysage inconnu ;
   énumérations identiques entre schémas, compilateur et thème par défaut (`test_contract_biome.py`).
3. Dans l'engine, une côte en fjord n'a plus ni palmiers ni pins parasols et a plus de bouleaux que
   d'épicéas, et son sol est l'herbe verte et le gneiss sombre (`test_biome_textures.gd`) ; un biome qui n'est pas une base du paysage ne change pas (`test_biome_model.gd`,
   `test_vegetation_biomes.gd`).
4. Un thème au paysage inconnu, vide ou à l'espèce inconnue est refusé (`test_theme_loader.gd`).
5. Chaque toit du contrat a son style de bâtiment (`test_building_mesh.gd`).
6. **À faire sur le PC** (via le fil de fusion) : recompiler un col de chaque paysage (Trollstigen, Teide,
   Utah Highway 12, Hai Van) avec `add-layer … biome`, captures en low, medium et high validées par le
   propriétaire, banc GPU en low, medium et high (budgets 8, 13 et 16 ms) : la côte de fjord passe de 80 à
   250 arbres/ha, la pinède du Teide de 10 à 120.

## 5. Partie 2 (lot suivant, rendu)

- Canyons : strates colorées dans la couche de pente (bandes d'altitude).
- Rizières : plans d'eau en gradins dans le relief (le plus coûteux de la série).
- Fjords : cascades sur les falaises.
- Ciel, eau, ambiance et faune des paysages : le contrat les accepte déjà (`landscapes` a la forme d'un bloc
  de biome) ; l'engine les appliquera quand chaque section passera par la variante de la tuile.

## Livraison

Partie 1 le 12 novembre 2026 (branche `claude/project-thread-ugu7bi`, PR #851) : contrat, table, thème par
défaut, engine (sol, végétation, toits), tests compilateur et engine. Captures cloud :
`/mnt/project-files/captures/u25-paysages-2026-11-12/v2-sol/`. Captures et bancs PC à faire.
