# Série JP – Biome « Japon » : Hakone et le mont Fuji (version 6.0)

<!-- Plan de série validé par le propriétaire le 9 novembre (« ok ») ; un cahier par lot dans docs/lots/LOT_JP*.md. -->

Demande du propriétaire du 9 novembre 2026 : « Pour v6 j'aimerais bien un biome Japon avec Hakone et Fuji ».

## 1. Objectif

Rouler au Japon de façon reconnaissable : routes de montagne de Hakone (lacets dans la forêt de cèdres, lac Ashi), village aux toits de tuiles gris, et **le mont Fuji visible au loin** depuis les cols de Hakone, puis gravi par la Fuji Subaru Line (déjà dans le pack « Cols célèbres », lot O16).

Trois manques rendent cela impossible aujourd'hui :

1. **Pas de biome japonais.** La liste fermée des seize biomes (lot U0) n'a rien pour la forêt humide de montagne du Japon : la classification (U2) y pose `temperate_forest` (chênes, hêtres) ou `mediterranean`, et les toits suivent le style du biome (U23).
2. **Le Fuji ne se voit pas depuis Hakone.** Le terrain s'arrête à ± 5 km de la route (niveau lointain, `FAR_BAND_M`, cases de 50 m) ; le sommet est à 25–30 km du lac Ashi.
3. **Aucun parcours à Hakone** dans le pack « Cols célèbres ».

## 2. Choix retenus (validés par le propriétaire le 9 novembre)

| # | Sujet | Choix proposé | Pourquoi |
| --- | --- | --- | --- |
| JP-Q1 | Biome ou variante régionale | **Un 17e biome `japan`** (« Japon : montagnes humides ») dans la liste fermée, pas une simple zone de `regional_variants.toml` | Une variante ne change que roches et toits ; la végétation, le ciel humide, la faune et les sons du Japon demandent un biome. Une seule liste, partout à jour (principe « pas d'exception ») |
| JP-Q2 | Où le compilateur pose `japan` | Archipel japonais (zone géographique en degrés entiers, comme U4) **et** climat Köppen tempéré humide (Cfa, Cfb, Dfa, Dfb) **et** classe « arbres » ou « arbustes » de WorldCover. Neige et sol nu gardent `alpine` / `volcanic` (sommet du Fuji) | S'appuie sur la carte Köppen du lot en cours (fil « Choisir le climat avec une carte Köppen ») au lieu de la latitude |
| JP-Q3 | Voir le Fuji | **Un niveau de terrain « horizon »** générique : cases de 500 m jusqu'à 40 km de la route, maillage très léger sans texture de détail ni végétation, fondu dans le brouillard | Profite à tous les mondes (Alpes vues du Galibier, Ventoux vu de loin) ; pas de silhouette peinte propre au Fuji |
| JP-Q4 | Parcours | Ajouter au pack « Cols célèbres » : Hakone Turnpike (Odawara → Daikanzan), Route 1 de l'Ekiden (Hakone-Yumoto → col de Kuniyoshi, 874 m) et, en option, la Fuji Azami Line (Subashiri) ; Fuji Subaru Line et Irohazaka existent déjà | Le pack sait déjà construire une montée réelle depuis OSM ; recettes de waypoints vérifiées sur le PC (Overpass bloqué depuis le cloud) |
| JP-Q5 | Monde demo | Pas de monde demo fictif « Japon » dans le jeu de base | Les mondes demo viennent d'être nettoyés (O37) ; le Japon passe par de vrais parcours |

## 3. Contenu du biome `japan`

| Élément | Contenu | Où |
| --- | --- | --- |
| Sol | Terre volcanique brun sombre (andosol), mousse sur les talus, roche de lave grise en pente ; neige seulement au-dessus de 2 500 m (reste `alpine`) | thème 2.0 (`default_theme.json`, `engine/themes/default/theme.json`), shader multi-biome U6 |
| Arbres | Nouvelles espèces : `sugi` (cèdre du Japon, colonne étroite très haute), `hinoki` (cyprès), `momiji` (érable du Japon, rouge en automne), `bamboo` (bosquets denses en bord de route), `pine` existant (pin noir) | `vegetation.species` (contrat), `tree_species.gd` |
| Sous-bois | Hortensias (Hakone en juin), azalées, fougères, herbe `susuki` (Sengokuhara) | U8 détails de sol |
| Constructions | Style `minka` : murs crépi clair et bois sombre, toit `kawara` (tuiles grises vernissées, faîtage relevé) ; nouvelle variante de toit `kawara` dans l'énumération fermée | `building_styles.gd`, U4/U23 |
| Repères | Torii rouges près des sanctuaires OSM (`amenity=place_of_worship` + `religion=shinto`), lanternes de pierre, garde-fous orange et blancs des routes japonaises | POI, mobilier de route |
| Faune | Macaque (existe : `monkey`), cerf sika (deer), faisan vert, corbeau à gros bec | U12/U23 |
| Ciel et lumière | Air humide, brume sur les crêtes, nuages bas plus fréquents | atmosphère U10, ciel P31 |
| Sons | Cigales `minmin` l'été, corbeaux, ruisseau | U11 |
| Saisons | Calendrier `four` ; érables rouges et sugi toujours verts en automne | U13 |

## 4. Données nécessaires

| Donnée | Source | Remarque |
| --- | --- | --- |
| Routes, sanctuaires, bâti, lac Ashi | OpenStreetMap (Overpass) | ODbL, comme tous les mondes ; compilation sur le PC |
| Altitude proche et lointaine | Copernicus GLO-30 (déjà utilisé) | Pas de nouvelle source |
| Altitude « horizon » (40 km) | Copernicus GLO-90 ou GLO-30 sous-échantillonné | ~ 80 × 80 km autour de la route ; cache comme le MNT |
| Occupation du sol | ESA WorldCover 2021 (déjà utilisé, U2) | |
| Climat | Carte Köppen-Geiger du lot Köppen | Ne pas dupliquer : brancher JP2 sur sa table |
| Textures | Packs CC0 (ambientCG, Poly Haven) par `theme-install` (U-Q3) ; couleurs unies par défaut | Rien dans le dépôt |
| Traces GPX | Aucune trace du propriétaire nécessaire | Les parcours sont des recettes de waypoints |

## 5. Budgets GPU (GTX 1060)

Budgets du projet : **low 8 ms, medium 13 ms, high 16 ms**. Toute mesure couvre les trois qualités et passe par la file du PC (`plans/FILE_MESURES_PC.md`, fil « Fusionner les PR et séquencer les mesures »).

| Lot | Coût attendu | Garde-fou |
| --- | --- | --- |
| JP3 biome `japan` | Nul en plus d'un autre biome : mêmes plafonds d'instances par tuile, 4 biomes par tuile au plus (3 en low) | Banc vitrine `japan` contre `temperate_forest`, écart ≤ 0,3 ms par qualité |
| JP4 niveau horizon | + 0,2 à 0,5 ms : environ 6 400 cases (80 × 80 km à 500 m sur l'anneau 5–40 km) rendues en 2 à 4 morceaux, une seule passe, pas d'ombre | low : horizon coupé à 20 km et cases de 1 km si le budget de 8 ms n'est pas tenu ; banc trois qualités sur Hakone Turnpike |
| JP5 sugi et bambous | Arbres hauts et denses : plafond d'instances existant par qualité | Banc sur la montée la plus boisée |

## 6. Découpage en lots

| Lot | Contenu | Dépend de | Taille |
| --- | --- | --- | --- |
| JP0 | Ce plan et les décisions JP-Q1 à JP-Q5 | — | Petite |
| JP1 | Contrat : 17e biome `japan` et toit `kawara` dans toutes les énumérations fermées, avec un rendu de base (thème, style de bâtiment, nom au menu) ; les espèces `sugi`, `hinoki`, `momiji`, `bamboo` entrent au contrat avec leurs maillages (JP5) et le niveau `horizon` avec JP4 (cahier `docs/lots/LOT_JP1_contrat_biome_japon.md`) | JP0 | Petite |
| JP2 | Compilateur : pose de `japan` (zone Japon × Köppen × WorldCover), toit `kawara` dans `regional_variants.toml` ; fait le 12/11, cahier `docs/lots/LOT_JP2_pose_biome_japon.md` | JP1, lot Köppen fusionné | Moyenne |
| JP3 | Engine : thème `japan`, sol, ciel, faune, sons, style `minka` (maisons faites le 12/11, cahier `docs/lots/LOT_JP3_maisons_japonaises.md`), nom au menu « Biome du décor » | JP1 | Moyenne |
| JP4 | Niveau de terrain « horizon » : compilateur (tuiles 500 m, 40 km) et engine (maillage, brouillard) ; fait le 12/11, cahier `docs/lots/LOT_JP4_niveau_horizon.md` | JP1 | Moyenne |
| JP5 | Végétation : maillages `sugi`, `hinoki`, `momiji`, `bamboo` ; torii, lanternes, garde-fous (reportés) ; espèces faites le 12/11, cahier `docs/lots/LOT_JP5_vegetation_japon.md` | JP3 | Moyenne |
| JP6 | Parcours : Route 1 de l'Ekiden et Fuji Azami Line dans le pack « Cols célèbres » (Turnpike écartée : interdite aux vélos) ; fait le 12/11, cahier `docs/lots/LOT_JP6_parcours_hakone_fuji.md` | JP2 | Petite |
| JP7 | Recette sur le PC : compiler Hakone et Fuji, captures low / medium / high à valider par le propriétaire, banc GPU trois qualités | JP2 à JP6 | Petite |

Ordre conseillé : JP1, puis JP2 / JP3 / JP4 en parallèle, JP5, JP6, JP7. Une branche et une PR par lot.

## 7. Questions ouvertes

1. Nom au menu : « Japon » ou « Montagnes humides (Japon) » ?
2. Le biome `japan` doit-il aussi servir ailleurs (Corée, Taïwan, montagnes du sud de la Chine) ou rester strictement japonais ?
3. Le niveau horizon (JP4) doit-il arriver plus tôt, pour tous les mondes, indépendamment du Japon ?
