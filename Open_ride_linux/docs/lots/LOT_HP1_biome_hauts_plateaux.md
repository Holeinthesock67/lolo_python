# Lot HP1 – Biome `high_plateau` : hauts plateaux (Altiplano, Tibet, Ladakh) (version 6.0)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Biome `high_plateau` complet : contrat, thème, touffes d'ichu, lamas et yacks, maisons d'adobe, règle de pose au compilateur, trois cols de recette | Python, GDScript, JSON | U24, JP1 | Moyenne | En PR le 12 novembre, **version 6.0** |

## 1. Objectif

Rang 3 de l'étude `ETUDE_BIOMES_V6.md` (ordre validé par le propriétaire le 12 novembre : « ok 1 à 4 »). Les routes les plus hautes du monde (Khardung La, Ticlio, Abra Málaga) sortaient en `alpine` (alpage vert, vaches, chalets) ou en steppe : il leur manquait l'herbe jaune d'ichu, le sol ocre, l'air sec et très clair, les lamas et les yacks. Biome peu coûteux : une seule plante nouvelle, basse et clairsemée, pas d'arbre.

## 2. Contenu livré

| Où | Changement |
| --- | --- |
| Contrat | `world_format_v1.md` §8 quater, §9 et journal §12 ; schémas `biome`, `manifest`, `theme` (et sa copie du compilateur) : biome `high_plateau`, espèce `bunchgrass` ; ajout compatible |
| Compilateur | `biomes.BIOMES` ; règle des hauts plateaux (§3) dans `biomes.py`, donc aussi dans le monde ouvert (même `classify_level`) ; trois recettes du pack « Cols célèbres » |
| Core | `config.BIOMES` : « hauts plateaux » au menu « Biome du décor » |
| Thème par défaut 2.0 | `biomes.high_plateau` : ichu et sol ocre, roche brun-rouge, neige au-dessus de 5 200 m ; touffes d'ichu et quelques arbustes (60 par hectare, sans arbre) ; lacs bleu profond et clairs ; air très clair (brouillard 0,0002, aucun voile, lumière bleutée) ; vent sec (fond `singing_sand`), peu d'oiseaux ; saison sèche et saison des pluies |
| Engine | espèce `bunchgrass` (touffe de 14 brins sur un pied serré, environ 45 triangles, modèle lointain dès 120 m) ; lamas et yacks (`fauna_renderer.gd`, `fauna_placer.gd`), lamas aussi dans le rôle des chevreuils (vigognes) ; style de bâtiment `altiplano` (adobe et pierre, toit de paille peu pentu, églises en tuiles rondes) ; herbes hautes et rochers du bord de route (`ground_details.gd`) ; peu de parapentes, pas de montgolfière ; shader multi-biome à 18 biomes (54 couches) |
| Tests | Comptes de biomes tirés de `biome_ids.gd` partout (plus de nombre écrit en dur) ; tailles du shader contrôlées par rapport à la liste ; règle de pose (§3) |

## 3. Règle de pose

Sous 40° de latitude, le terrain ouvert d'ESA WorldCover (prairie, arbustes, sol nu, mousses, sable OSM) vote `high_plateau` pour une part `p` qui croît de 0 à 3 300 m à 1 à 3 800 m (`plateau_part`, fondue de 38° à 42° de latitude). Le reste de l'altitude garde la règle alpine, réduite d'autant : part `alpine` = `a × (1 − p)`. Neige et glaciers restent `alpine` ; forêts, cultures, zones humides et laves gardent leur biome. Les Alpes (45°) ne changent pas. Une seule règle pour les parcours compilés et le monde ouvert (le générateur appelle `classify_level`).

## 4. Parcours de recette (pack « Cols célèbres »)

| Recette | Départ → arrivée | Longueur et dénivelé de référence |
| --- | --- | --- |
| `khardung_la` | Leh → col (5 359 m) | 39 km, 2 200 m |
| `abra_malaga` | Ollantaytambo → col (4 316 m) | 43 km, 1 550 m |
| `ticlio` | Casapalca → col (4 818 m) | 14,6 km, 625 m (mesure du PC du 12 novembre : 14 566 m, 624 m) |

Références tirées des sites de cols (PJAMM, quaeldich, bikeclimbs) : **à caler sur la mesure du PC** (`route-pack-build`, tolérance 5 %), comme pour les recettes de Hakone. Chacaltaya est écarté : route en terre, en cul-de-sac.

Premier passage PC (12 novembre) : Khardung La et Abra Málaga refusés, « aucun chemin routier permis » : les lacets sortent du rectangle de 1,5 km autour des points. `route_recipe.py` réessaie maintenant avec une marge de 6 km, et un refus dit quel tronçon manque et s'il passerait par une route non revêtue (`unpaved = true`). Banc `--biome high_plateau` : 5,30 / 6,87 / 9,06 ms en low / medium / high (budgets 8 / 13 / 16 ms).

## 5. Essais

- Cloud : suites core, compilateur et engine ; vitrine des biomes (`vitrine_biomes.gd --biomes high_plateau,alpine,steppe`) et vitrine de rendu (touffes, lamas, yacks, maisons), captures dans `/mnt/project-files/captures/hp1-hauts-plateaux-2026-11-12/`, **à valider par le propriétaire**.
- PC (file du fil de fusion) : banc trois qualités (low 8, medium 13, high 16 ms) sur `khardung_la` et `ticlio` ; compilation des trois recettes et part des biomes.

## 6. Hors périmètre

- Sons propres (vent d'altitude, cris des lamas) : fonds U11 existants pour l'instant.
- Variante de toit en tôle (calamina) et habitat tibétain à toit plat : à voir après les captures.
- Ordre des identifiants avec le lot Atlantique : `atlantic_heath` 18e, `high_plateau` 19e une fois les deux fusionnés ; le second à fusionner remet main dans sa branche et place son identifiant après l'autre.
