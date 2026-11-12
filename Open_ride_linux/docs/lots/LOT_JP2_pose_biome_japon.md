# Lot JP2 : pose du biome `japan` par le compilateur (version 6.0, série JP)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Compilateur : biome `japan` posé sur les forêts et broussailles du Japon (zone × Köppen × WorldCover), toit `kawara` | Python, TOML | JP1, U24 | Moyenne | En PR le 12 novembre, **version 6.0** |

Plan : `docs/6.0/PLAN_SERIE_JP.md`. Dépend de JP1 (#832) et du lot Köppen U24 (#833), fusionnés.

## Règle

Un point de la couche biome prend `japan` quand les trois conditions sont réunies :

1. il est dans un des rectangles de `compiler/src/openride_compiler/data/japan_zone.toml` (degrés entiers :
   Kyūshū, Shikoku, Honshū, Hokkaidō ; ni la Corée, ni le continent, ni Okinawa) ;
2. son climat de Köppen (carte embarquée du lot U24) est `Cfa`, `Cfb`, `Dfa` ou `Dfb` ;
3. sa classe WorldCover est arbres (10) ou arbustes (20) : cèdres sugi, cyprès hinoki, érables, bambous, sasa.

Les autres classes gardent leur biome : rizières et cultures (`farmland`), prairies, bâti, eau, sol nu (le sol nu
du Fuji reste `volcanic`), neige ; l'étage alpin d'après l'altitude s'applique comme ailleurs. Même mécanique
que les paysages volcaniques (classe propre au compilateur `JAPAN_FOREST` = 202), injectable par
`Inputs.japan` pour les essais.

## Variantes régionales

Cinq zones `japon_*` dans `data/regional_variants.toml`, mêmes rectangles : toit `kawara`, sol `basalte`
(andésites et basaltes de l'arc japonais). Un test vérifie que les deux tables gardent les mêmes rectangles.

## Limites

- Le sud des Kouriles et la pointe sud de Sakhaline (moins de 15 km) entrent dans le rectangle de Hokkaidō.
- Aucun changement de format : `japan` est au contrat depuis la 1.7 (JP1).

## Critères

1. `compiler/tests/test_japan_biome.py` vert (lieux connus, forêts → `japan`, cultures et sol nu inchangés,
   forêts hors du Japon inchangées, tables cohérentes).
2. Sur le PC (JP7) : Hakone et Fuji Azami Line recompilés, part `japan` majoritaire, captures à valider.
