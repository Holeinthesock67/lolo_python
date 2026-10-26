# OpenRide 3.0 – Biomes, textures régionales et saisons par biome (série U)

25 octobre 2026. Proposition du propriétaire : pour la 3.0, des biomes (eau, montagne, jungle, savane, désert…), avec des textures différentes selon les régions et les saisons. Ce plan complète la liste, la confronte à l'architecture actuelle et la découpe en lots. **La série U commence après la 2.0** : elle s'appuie sur le décor vivant de la série P (vent, météo, ambiance, faune) et sur les saisons de la 2.0 ([P18](../lots/LOT_P18_saisons.md), intégrées par [P19](../lots/LOT_P19_integration_jour_nuit_saisons.md)). Les cahiers des lots seront rédigés au démarrage de la série et ajoutés à `docs/lots/00_INDEX.md`.

## 1. En résumé

Aujourd'hui, le décor a **un seul paysage par séance** : un thème global (`render.theme`) qui donne trois couches de terrain (herbe, roche, neige) choisies par la pente et l'altitude, une seule palette d'arbres et des bâtiments OSM. La 3.0 rend le paysage **régional** : chaque tuile de terrain reçoit des poids de biome (par exemple 70 % méditerranéen et 30 % littoral), calculés par le compilateur à partir de données réelles ou imposés par le propriétaire, et l'engine mélange les textures, la végétation, les sons, la faune et la lumière de ces biomes. Les saisons de la 2.0 deviennent propres à chaque biome. Le défi principal est le coût sur la GTX 1060 : il faut au plus quatre biomes par tuile, des tableaux de textures compressés et des budgets par préréglage.

## 2. Biomes proposés (liste du propriétaire complétée)

| # | Biome | Terrain et textures | Végétation | Saisons | Ambiance |
| --- | --- | --- | --- | --- | --- |
| 1 | Prairie et bocage tempérés (actuel, par défaut) | Herbe, terre, haies | Feuillus épars, haies, vergers | Quatre saisons (P18) | Oiseaux, insectes, cloches |
| 2 | Forêt tempérée feuillue et mixte | Litière, mousse, fougères | Chênes, hêtres, quelques résineux | Quatre saisons, feuillages d'automne | Pics, pinsons, ruisseaux |
| 3 | Vignobles et grandes cultures | Rangs de vigne, champs en damier, chaumes | Vignes, blé, colza, maïs | Récoltes : vert, jaune, labours | Tracteurs, alouettes |
| 4 | Forêt boréale (taïga) | Mousse, lichen, aiguilles | Épicéas, pins, bouleaux | Hiver long, neige au sol | Vent dans les résineux, corbeaux |
| 5 | Haute montagne alpine | Pelouse rase, éboulis, rocher, glacier, neige | Mélèzes et pins cembro jusqu'à la limite des arbres | Neige variable, fonte | Sonnailles, marmottes, vent |
| 6 | Toundra | Lichen, sol nu, flaques | Arbustes nains | Courte saison verte | Vent, oiseaux de rivage |
| 7 | Polaire (banquise et glacier) | Neige, glace bleue, crevasses | Aucune | Nuit et jour polaires (avec P7) | Vent, craquements de glace |
| 8 | Méditerranéen | Terre ocre, calcaire blanc, garrigue | Oliviers, chênes verts, cyprès, pins parasols | Été sec et jaune, hiver vert | Cigales, vent |
| 9 | Steppe | Herbe rase et sèche, terre claire | Graminées, rares arbustes | Été brûlé, hiver froid | Vent, alouettes |
| 10 | Savane | Herbes hautes jaunes, termitières, latérite rouge | Acacias, baobabs | Saison sèche et saison des pluies | Insectes, oiseaux tropicaux, lointains rugissements |
| 11 | Désert de sable | Sable, dunes, rides de sable | Quelques palmiers dans les oasis | Pratiquement aucune | Vent, sable qui siffle |
| 12 | Désert de roche et canyon | Roche ocre en strates, mesas, reg | Cactus, buissons secs | Pratiquement aucune | Vent, échos |
| 13 | Jungle (forêt tropicale humide) | Sol sombre, racines, lianes | Grands arbres à étages, palmiers, fougères arborescentes | Saison humide et saison moins humide | Chorus dense d'insectes et d'oiseaux, pluie |
| 14 | Zones humides | Marais, tourbières, rizières en terrasses | Roseaux, saules, mangrove sous les tropiques | Selon le climat voisin | Grenouilles, hérons |
| 15 | Littoral | Plages de sable ou de galets, dunes, falaises, mer | Oyats, pins maritimes, palmiers sous les tropiques | Selon le climat voisin | Vagues, mouettes |
| 16 | Volcanique | Basalte noir, champs de lave, scories rouges | Mousses, lichens | Selon le climat voisin | Vent, fumerolles |

L'eau douce (lacs, rivières) existe déjà depuis E4 ; elle prend la teinte du biome (eau claire en montagne, turquoise au littoral tropical, brune en zone humide). Les villages et les villes restent ceux d'OSM ; seuls leurs matériaux changent avec la région (§3).

## 3. Variantes régionales

Un même biome change d'aspect selon la région : c'est surtout la **géologie** (couleur de la roche et de la terre) et l'**architecture** (murs et toits). Une variante régionale est un petit jeu de couleurs et de textures qui s'applique par-dessus le biome :
- **roches et terres :** grès rose (Vosges), calcaire blanc (Provence, Jura), granite gris (Bretagne, Alpes), schiste sombre, basalte (Auvergne, Islande), latérite rouge (tropiques), craie (falaises) ;
- **bâtiments :** tuiles rondes ocre (Sud), ardoise (Nord-Ouest, montagne), tuiles plates brunes (Est), pierre sèche, toits plats blancs (zones arides), bois (Scandinavie) ;
- **choix de la variante :** par une table d'ébauche fondée sur la latitude, la longitude et la géologie simplifiée, calculée par le compilateur et modifiable dans le thème ; aucune coordonnée réelle du propriétaire n'est écrite dans le dépôt.

## 4. Saisons par biome

La 2.0 apporte quatre saisons uniformes (P18). En 3.0, chaque biome a son propre calendrier :
- **tempérés et froids :** les quatre saisons de P18, plus longues ou plus courtes selon le biome (hiver de la taïga, été court de la toundra) ;
- **méditerranéen et steppe :** l'été sec et jaune devient la saison marquante ;
- **savane et jungle :** une saison sèche et une saison des pluies au lieu des quatre saisons ;
- **désert et polaire :** presque aucun changement (le jour et la nuit comptent davantage) ;
- **hémisphère sud :** les saisons sont inversées (déjà prévu dans P18).

## 5. Ce qui se réutilise

| Besoin | Existant | Où |
| --- | --- | --- |
| Tuiles de terrain et altitude | Couche terrain, MNT Copernicus en cache | `compiler/src/openride_compiler/terrain.py`, `compiler/src/openride_compiler/elevation.py` |
| Données OSM | Bâtiments, végétation, eau, points d'intérêt | `compiler/src/openride_compiler/osm_layers.py` |
| Thèmes et leur validation | Schéma, chargeur, paramètres de rendu | `docs/contracts/world/theme.schema.json`, `engine/scripts/theme_loader.gd`, `engine/scripts/theme_render_params.gd` |
| Mélange de textures | Shader triplanaire (herbe, roche, neige) | `engine/shaders/terrain.gdshader` |
| Végétation | Placement déterministe, arbres en `MultiMesh` | `engine/scripts/vegetation_placer.gd`, `engine/scripts/tree_renderer.gd` |
| Sons | Modèle et synthèse | `engine/scripts/sound_model.gd`, `engine/scripts/sound_player.gd` |
| Budgets par préréglage | Table des préréglages | `engine/scripts/quality_presets.gd` |
| Packs de textures | Lot N10 (`theme-list`, `theme-install`) ; niveaux de textures selon les performances en 2.0 (P20) | [LOT_N10_packs_themes.md](../lots/LOT_N10_packs_themes.md), [LOT_P20_packs_textures_performance.md](../lots/LOT_P20_packs_textures_performance.md) |
| Vent, météo, ambiance, faune, saisons | Série P | [00_INDEX.md](../lots/00_INDEX.md) |

## 6. Ce qu'il faut ajouter

**Format `.world` (ajout compatible) :** une couche `biome` par tuile de terrain : grille grossière (par exemple 16 × 16 cases par tuile de 1 km), avec au plus quatre biomes par tuile et leurs poids ; une variante régionale par tuile ; une sorte d'eau `sea` et une couche côte (OSM `natural=coastline`, plages `natural=beach`). Un parcours sans couche `biome` garde le rendu actuel.

**Compilateur :** classification des biomes à partir de l'occupation du sol (ESA WorldCover à 10 m, téléchargée une fois et mise en cache comme le MNT), d'OSM (`natural=sand`, `wetland`, `glacier`, `scrub`, `heath`, `landuse=vineyard`, `farmland`, `orchard`), de l'altitude et d'une zone climatique approchée par la latitude ; option `--biome` pour imposer un biome à tout le parcours.

**Thème 2.0 :** un thème devient un **pack de biomes** : une entrée par biome (couches de sol, palettes de végétation, eau, ciel, sons), des variantes régionales et des calendriers de saisons ; les thèmes 1.x restent lisibles (ils décrivent le biome par défaut).

**Engine :**
- modèle de biome sans affichage : poids par position, transitions douces entre tuiles, paramètres du biome selon la saison et la variante ;
- shader de terrain multi-biome : tableaux de textures (`Texture2DArray`), quatre biomes au plus par tuile, triplanaire conservé pour la roche ;
- végétation par biome : nouvelles espèces construites par code (conifères, palmiers, acacias, baobabs, cactus, oliviers, cyprès, fougères arborescentes, roseaux) ;
- détails de sol : rides de sable et dunes par cartes de normales (le relief reste celui du MNT), rochers épars, herbes hautes de savane ;
- mer : surface animée simple, écume sur la plage ;
- atmosphère : brume de chaleur au désert, humidité en jungle, lumière polaire ;
- sons et faune par biome, à partir des modèles de P9 et P11.

## 7. Décisions

Toutes les questions sont tranchées par le propriétaire le 25 octobre 2026.

| # | Question | Proposition |
| --- | --- | --- |
| U-Q1 | Biome automatique, forcé, ou les deux ? | **Décidé : les deux.** automatique d'après les données réelles, avec un forçage au compilateur et au menu. Raison : les traces du propriétaire sont surtout en zone tempérée ; sans forçage, la plupart des biomes ne se verraient jamais |
| U-Q2 | Télécharger ESA WorldCover dans le compilateur ? | **Décidé : oui**, avec un cache comme le MNT (règle « hors ligne » : seule la compilation accède au réseau, jamais la séance) |
| U-Q3 | D'où viennent les textures ? | **Décidé :** packs téléchargés par `theme-install` (N10), textures libres de droits (CC0, par exemple ambientCG ou Poly Haven), jamais dans le dépôt ; chaque pack téléchargé reste sur le disque et forme peu à peu une bibliothèque, plafonnée à 5 Go (au-delà, le pack utilisé le moins récemment est retiré) ; le dépôt garde des couleurs unies par défaut |
| U-Q4 | Budget sur la GTX 1060 ? | **Décidé (compromis qualité et performance) :** `low` : trois biomes au plus par tuile, textures de 1 024 px ; `medium` : quatre biomes, 1 024 px (réglage conseillé s'il tient 55 images/s) ; `high` : quatre biomes, 2 048 px ; deux cartes compressées par sol (couleur, normale et rugosité regroupées) ; 1 Go de mémoire vidéo au plus pour les textures du décor ; 55 images/s ou plus en `low`, comme la série P, vérifié à la recette U18 |
| U-Q5 | Biomes du premier jalon ? | **Décidé :** les plus utiles sur tes traces : prairie, forêt tempérée, vignobles et cultures, haute montagne, méditerranéen, littoral ; puis les biomes lointains (désert, savane, jungle, polaire, volcanique) |
| U-G1 | Option « gravel » (§10) | **Décidé :** réglage des menus, coupé par défaut |
| U-G2 | Ressenti du gravel sur le vélo ? | **Décidé :** résistance au roulement deux à trois fois celle du bitume, transmise en SIM comme supplément de pente, avec le même plafond que le vent (P1, 4 points par défaut) ; en ERG, seule la vitesse virtuelle change |

## 8. Lots de la série U

| Lot | Contenu | Dépend de | Type |
| --- | --- | --- | --- |
| U0 | Décisions U-Q1 à U-Q5 (prises le 25 octobre 2026), liste définitive des biomes | — | Propriétaire |
| U1 | Contrat : couche `biome`, variante régionale, sorte d'eau `sea` et couche côte (format `.world`), thème 2.0 en pack de biomes, compatibilité avec les thèmes 1.x | U0 | Interne (décision) |
| U2 | Compilateur : classification des biomes (WorldCover en cache, OSM, altitude, latitude), option `--biome` | U1 | Délégable |
| U3 | Compilateur : côte, mer et plages | U1 | Délégable |
| U4 | Compilateur : variante régionale par tuile (table de géologie et d'architecture simplifiées) | U1 | Délégable |
| U5 | Engine : modèle de biome sans affichage (poids, transitions, saison, variante) | U1, P18 | Délégable |
| U6 | Engine : shader de terrain multi-biome à tableaux de textures | U5 | Délégable (tests de rendu), recette visuelle interne |
| U7 | Engine : végétation par biome (nouvelles espèces, densités, limites) | U5 | Délégable |
| U8 | Engine : détails de sol (dunes, rochers épars, herbes hautes) | U6 | Délégable |
| U9 | Engine : mer animée et plages | U3, U6 | Délégable |
| U10 | Engine : atmosphère par biome (brume de chaleur, humidité, lumière polaire) | U5, P7 | Délégable |
| U11 | Engine : sons d'ambiance par biome (extension de P9) | U5, P9 | Délégable |
| U12 | Engine : faune par biome (extension de P11) | U5, P11 | Délégable |
| U13 | Engine : calendriers de saisons par biome (saison sèche et saison des pluies, désert, polaire) | U5, P18 | Délégable |
| U14 | Engine : variantes régionales des roches, terres et bâtiments | U4, U6 | Délégable |
| U15 | Packs de biomes : thème 2.0 par défaut en couleurs unies, pack de textures libres téléchargeable par `theme-install` | U1, N10 | Délégable |
| U16 | Choix du biome au menu (forçage, retenu par U-Q1) | U2, O4 | Interne (menu) |
| U17 | Intégration dans la scène principale | U5 à U15 | Interne (rendu) |
| U18 | Recette sur le PC : un parcours par biome du premier jalon, performances, mémoire vidéo | U17 | Propriétaire |

Ordre conseillé : U0 et U1 ; puis le premier jalon (U-Q5) : U2, U4, U5, U6, U7, U11, U13, U14 et U15, intégrés par U17 et recettés par U18 ; ensuite U3 et U9 (littoral et mer), U8, U10 et U12 ; enfin les biomes lointains, qui ne demandent plus que des données (palettes, espèces, sons) dans les packs.

## 9. Risques

| # | Risque | Parade |
| --- | --- | --- |
| 1 | Mémoire vidéo et débit de textures sur la GTX 1060 | Tableaux de textures compressés, quatre biomes par tuile, tailles par préréglage, mesure dans U18 |
| 2 | Frontières de biomes visibles (lignes droites au bord des tuiles) | Poids sur une grille fine avec un bruit de bord, mélange continu entre tuiles voisines |
| 3 | Classification fausse (WorldCover ou OSM incomplets) | Valeurs par défaut prudentes (biome tempéré), forçage possible, rapport de compilation qui donne la part de chaque biome |
| 4 | Droits des textures | Textures CC0 seulement, téléchargées dans un pack, jamais dans le dépôt |
| 5 | Biomes lointains invisibles sur des traces françaises | Forçage (U-Q1), parcours de démonstration fictifs |
| 6 | Données personnelles | Aucune coordonnée réelle dans le dépôt ni dans les tests ; tables régionales à grosse maille |

## 10. Autre ajout prévu pour la 3.0

- **Option « gravel » (décision du propriétaire du 25 octobre 2026, question W-Q2 du [monde ouvert](../2.0/PLAN_SERIE_W.md)) :** un réglage des menus qui ouvre au monde ouvert les chemins de terre et les pistes forestières. Le navigateur peut alors les emprunter, et l'engine leur donne un ruban et une texture de terre ou de gravier. Ce réglage pourra aussi servir aux biomes (pistes de savane ou de désert).
