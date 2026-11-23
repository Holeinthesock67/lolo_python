# Lot VR4 (V6-r4) – Biomes du rang 4 : forêt de nuages, bush à eucalyptus, forêt pluviale tempérée (version 6.0)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Trois biomes complets (`cloud_forest`, `eucalypt_woodland`, `temperate_rainforest`) : contrat, règle de pose par la table commune des biomes régionaux, thème, quatre arbres, kangourou, démonstration « Route des Trois Forêts » | Python, GDScript, JSON | U24, AT2, HP1, DB3 | Moyenne | **Livré le 21 novembre** (PR #935) |

## 1. Objectif

Rang 4 de l'ordre validé par le propriétaire le 12 novembre (« ok 1 à 4 ») sur l'étude `ETUDE_BIOMES_V6.md` (§3.4 à §3.6) : « plus tard forêt de nuages, eucalyptus, forêt pluviale ». Lot lancé par le propriétaire le 19 novembre. Principe suivi : pas d'exception, les trois biomes entrent par les mêmes chemins que l'Atlantique, le Japon et les hauts plateaux.

## 2. Contenu livré

| Où | Changement |
| --- | --- |
| Contrat | `world_format_v1.md` §8 quater, §9 et journal §12 ; schémas `biome`, `manifest`, `theme` (et sa copie du compilateur) : trois biomes, espèces `wax_palm`, `eucalyptus`, `douglas_fir`, `red_cedar` ; ajout compatible, identifiants ajoutés après `reef` (aucun indice existant ne bouge) |
| Compilateur | `biomes.BIOMES` ; trois entrées de la table commune `data/biome_zones.toml` (§3), donc la même règle pour les parcours GPX et le monde ouvert (`classify_level`) ; démonstration « Route des Trois Forêts » (`demo_biomes --forets`) |
| Core | `config.BIOMES` : les trois biomes au menu « Biome du décor » ; « Route des Trois Forêts » dans les contenus de départ (jeu de base) |
| Thème par défaut 2.0 | `biomes.cloud_forest` : sol noir moussu, roche ruisselante, páramo au-dessus de 3 600 m ; fougères arborescentes, palmiers à cire, chênes, bambous (550 par hectare) ; brouillard épais (0,003, voile 0,6) ; chœur de la jungle et grenouilles ; saison sèche et saison des pluies. `biomes.eucalypt_woodland` : herbes sèches et terre rouge, grès rouge ; eucalyptus, acacias, arbustes (140 par hectare, forêt claire) ; air sec et lumière dure ; cigales ; quatre saisons à été sec (inversées au sud par season_model.gd). `biomes.temperate_rainforest` : mousse épaisse, roche noire mouillée ; douglas, thuyas géants, épicéas, fougères (500 par hectare) ; brume (0,0022) ; vent dans les conifères, grenouilles |
| Engine | quatre espèces (`tree_species.gd`) : palmier à cire (28 m, stipe blanc, dix palmes), eucalyptus (22 m, fût clair, trois touffes gris-vert), douglas (34 m, quatre étages), thuya géant (26 m, cinq étages vert-jaune) ; kangourou (`fauna_renderer.gd`, bandes dans le bush, `fauna_placer.gd`), perroquets et singes de la forêt de nuages ; styles de bâtiment existants (`tuile_ronde`, `bois_peint` à toit de tôle, `bois` à bardeaux) ; herbes sèches au bord des routes du bush, blocs moussus dans la forêt pluviale ; peu de parapentes ; shader multi-biome à 23 biomes (117 couches) |
| Tests | règle de pose (§3) sur les cols de l'étude ; comptes de biomes tirés des listes ; démonstration (jeu de base, CLI, scénarios de menu) ; maillage du kangourou |

## 3. Règle de pose

Table commune des biomes régionaux (lot AT2), sans règle à part : un rectangle, une liste de codes de Köppen, une liste de classes WorldCover.

| Biome | Classe | Köppen | WorldCover | Rectangles |
| --- | --- | --- | --- | --- |
| `cloud_forest` | 204 | Cfb, Cfc, Cwb, Cwc | arbres | Andes du nord et du centre, Amérique centrale, Afrique de l'Est |
| `temperate_rainforest` | 206 | Cfb, Cfc, Csb, Csc, Dfb, Dfc, Dsb, Dsc | arbres | Oregon et Washington, Colombie-Britannique côtière, sud de l'Alaska, sud du Chili, Nouvelle-Zélande, ouest de la Tasmanie |
| `eucalypt_woodland` | 205 | Csa, Csb, Cfa, Cfb, Cwa, BSh, BSk | arbres, arbustes | Australie |

Sous les tropiques, les codes tempérés de Köppen ne se trouvent qu'en montagne (environ 1 500 à 3 500 m) : la carte porte l'étage de la forêt de nuages, sans seuil d'altitude à part. Le sommet de l'Alto de Letras (ET, páramo) reste ouvert. L'ouest de la Tasmanie est avant le rectangle de l'Australie (le premier rectangle l'emporte). Prairies, cultures, eau, bâti et neige gardent leur biome.

Vérifié sur les cols de l'étude : Alto de la Línea et Cerro de la Muerte en forêt de nuages ; Hurricane Ridge, Mount Seymour et Crown Range en forêt pluviale ; Willunga Hill, Corkscrew Road, Mount Buller et Mount Hotham en bush à eucalyptus.

`BIOME_VERSION` des tuiles reste « 1.0 », comme aux lots AT2, JP2 et HP1 : aucun format ne change, et seules les tuiles des régions nouvelles changent de contenu. Le cache du monde ouvert (`SCHEMA_VERSION` de la base OSM) n'est pas touché.

## 4. Démonstration « Route des Trois Forêts »

Règle du propriétaire du 14 novembre (lot DB3) : chaque biome réel a sa démonstration au jeu de base. `demo-biomes-forets` : trois blocs de 2 km en montée, du bush à eucalyptus (ferme, belvédère des gommiers) à la forêt pluviale tempérée (cabanes, torrent et cascade), puis la forêt de nuages (finca aux tuiles rondes et caféiers) jusqu'au « Col des Nuages » dans le brouillard.

## 5. Essais

- Cloud : suites core et compilateur ; tests unitaires engine ; vitrine de rendu (vue `arbres_rang4`, kangourous dans `faune_biomes`) et vitrine des biomes, captures à valider par le propriétaire.
- PC (file du fil de fusion) : banc `--biome` des trois biomes et de la Route des Trois Forêts en low, medium et high (budgets 8, 13 et 16 ms). La forêt pluviale (grands arbres serrés) et la forêt de nuages (densité proche de la jungle) sont les plus à surveiller.

## 6. Hors périmètre

- Sons propres (cris des cacatoès, pluie sur les feuilles) : fonds U11 existants.
- Mousses pendantes et épiphytes : à voir après les captures.
- Cols de recette dans le pack « Cols célèbres » (Alto de Letras, Willunga, Hurricane Ridge) : lot à part, calés sur le PC comme ceux des hauts plateaux.

## 7. Livraison

Fusionné le 21 novembre 2026 (PR #935 : biomes du rang 4 et démonstration « Route des Trois Forêts »). Détail des écarts et de la recette : description de la PR.
