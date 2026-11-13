# Lot HP2 – Cols Khardung La et Abra Málaga (hauts plateaux, version 6.0)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Recettes Khardung La et Abra Málaga dans le pack `cols_celebres` ; `unpaved = true` n'ouvre plus les pistes | Python, TOML | HP1, O16 | Petite | En PR le 13 novembre, **version 6.0** |

## 1. Objectif

Le lot HP1 (#854) livrait le biome `high_plateau` avec le seul col de Ticlio : Khardung La et Abra Málaga étaient refusés au passage PC du 12 novembre (décision du propriétaire : fusion avec Ticlio seul, les deux cols dans un lot à part, go le 13 novembre). Ce lot ajoute les deux recettes au pack `cols_celebres`.

## 2. Cause du refus et correctif

Les deux routes ont une partie notée non revêtue dans OpenStreetMap (gravier en haut de Khardung La, terre au premier kilomètre de la PE-28B à Ollantaytambo), d'où `unpaved = true`. Mais cette clé ouvrait aussi toutes les pistes (`track`) et sentiers (`path`) : le plus court chemin coupait les lacets (Khardung La 27,4 km au lieu de 37, Abra Málaga 26,6 km au lieu de 43).

Règle commune, sans cas particulier : `unpaved = true` ouvre les **routes** au revêtement non goudronné ; une piste ou un sentier n'est retenu que s'il est revêtu (`asphalt`, `paved`, `concrete`), avec ou sans la clé (`route_recipe.way_allowed`). Aucune recette existante n'avait `unpaved = true` : les 19 autres cols ne changent pas. Deux points de passage suffisent alors par col.

## 3. Recettes

| Recette | Versant | Référence (mesure du 13 novembre) |
| --- | --- | --- |
| `khardung_la` | Leh (Fort Road, 3 502 m) → col (5 358 m) | 37 100 m, 1 860 m (mesure : 37 058 m, 1 858 m) |
| `abra_malaga` | Ollantaytambo (2 849 m) → col (4 316 m) par la PE-28B | 42 700 m, 1 580 m (mesure : 42 749 m, 1 579 m) |

Méthode : routes OSM téléchargées une fois sur le PC (`~/OpenRide/cols-osm/`, Overpass est injoignable depuis le cloud), puis construction complète dans le cloud avec le compilateur (graphe, rectangles de 1,5 et 6 km) et le MNT Copernicus GLO-30. La route suivie a été comparée à la route principale (Leh Khardung La Road, PE-28B) : elle n'en sort qu'à Leh, par les rues de la vieille ville (2,9 km). L'arrivée d'Abra Málaga est placée au point haut du MNT (l'ancien point était 1,2 km après le col, en descente). Les anciennes références (39 km et 2 200 m pour Khardung La, 43 km et 1 550 m pour Abra Málaga) n'avaient pas été mesurées : elles sont remplacées par la mesure.

Aucune trace dans le dépôt : seulement les recettes. Crédits du pack inchangés (ODbL OpenStreetMap, Copernicus GLO-30).

## 4. Essais

- Cloud : `compiler/tests/test_route_recipe.py` (pack de 21 recettes, piste non revêtue écartée même avec `unpaved = true`, piste revêtue gardée), suite compilateur complète.
- PC (file du fil de fusion) : `route-pack-build cols_celebres --only khardung_la,abra_malaga --install` puis compilation des deux traces (part `high_plateau`) et banc trois qualités sur `khardung_la` (budgets low 8, medium 13, high 16 ms) ; captures validées par le propriétaire avant fusion.
- Pack de base livré hors git (décision du 12 novembre) : lot à part, avant l'installateur J9.
