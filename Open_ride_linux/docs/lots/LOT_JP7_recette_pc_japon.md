# Lot JP7 : recette du Japon sur le PC (version 6.0, série JP)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Recette sur le PC : Hakone et Fuji recompilés, vitrines du Japon en trois qualités, banc GPU | — | JP2 à JP6 | Petite | **Livré le 13 novembre** (mesures r855), **version 6.0** |

Plan : `docs/6.0/PLAN_SERIE_JP.md`.

## Livraison

Recette r855 du 12 novembre, faite sur le PC par la file des mesures, tête `caa45e43` de la PR #855
(JP2, JP3 et JP5, avant la reprise de main). Planches validées par le propriétaire le 13 novembre.

| Mesure | Résultat |
| --- | --- |
| `hakone_route_1` recompilé | biome `japan` 90,5 % (`temperate_grassland` 7,5 %, `volcanic` 2,0 %) |
| `fuji_azami_line` recompilé | biome `japan` 99,1 % |
| Vitrine `arbres_japon`, `torii`, `maisons_japon` (low, medium, high) | contrôles automatiques passés ; `maisons_japon` en high : 6 330 triangles, 3 appels de dessin |
| Banc Hakone 240 s, GPU low / medium / high | 5,37 / 8,61 / 10,39 ms (budgets 8 / 13 / 16 ms) |
| Pires images low / medium / high | 53 / 73 / 50 ms |
| Contacts | 0 ; seul contrôle en échec : la vitesse imposée du banc |

Pour comparer, le banc de #841, sans le biome posé, mesurait avec l'horizon 5,36 / 8,04 / 10,11 ms : avec le
biome japan, les forêts de sugi et les torii coûtent environ 0 / +0,6 / +0,3 ms.

Sur la vue `torii`, le décor autour reste européen : c'est une vue de test sur une route droite, pas un parcours
japonais. Sur la vraie route d'Hakone, les torii sont au pied des montées, dans les forêts de sugi.

## Reste

Garde-fous de la route au Japon (reportés du lot JP5).
