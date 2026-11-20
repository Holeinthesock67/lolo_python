# Série EA – Lacs, rivières et ponts (6.0)

Demande du propriétaire du 14 novembre, après l'explication de la modélisation de l'eau en monde ouvert : traiter les limites relevées dans le code.

## État avant la série (main du 14 novembre, après #844)

- Sources : OpenStreetMap seul (tuiles vectorielles OpenFreeMap ou extrait Geofabrik) ; lacs, étangs, réservoirs en surfaces ; rivières, ruisseaux, canaux en lignes. WorldCover ne dessine pas d'eau. La mer (U3, U9) n'existe que dans les parcours compilés.
- Plan d'eau : surface plane au minimum du terrain sur son contour ; terrain jamais modifié dessous. Rivière : ruban de largeur fixe par type (6, 2, 8 m) qui suit la pente.
- Monde ouvert : eau dans les carrés de 1 km à moins de 1,5 km de la route ; tuiles lointaines de 5 km sans eau.
- Pont : route en ligne droite d'une culée à l'autre, rien de dessiné ; ruban de rivière coupé sous la route.

## Lots

| Lot | Contenu | Dépend de | Taille |
| --- | --- | --- | --- |
| EA1 | Niveau commun d'un lac pris dans son MNT (plus de marches entre morceaux, plus d'exutoire qui tire le lac vers le bas), sol abaissé sous l'eau ; parcours compilés et monde ouvert (`docs/lots/LOT_EA1_niveau_lacs_sol_sous_eau.md`) | I4, W7 | Petite |
| EA2 | Eau au loin en monde ouvert : grands lacs (plus de 1 km²) écrits avec les tuiles lointaines et dessinés au-delà des carrés proches, sol lointain abaissé dessous ; même règle que EA1 | EA1, W7, W10 | Moyenne |
| EA3 | Grandes rivières en surface : `natural=water` + `water=river` (extrait) et classe `river` des tuiles vectorielles, niveau qui descend le long du cours (pas un plan horizontal) ; ruban gardé pour les rivières sans surface | EA1 | Moyenne |
| EA4 | Ponts dessinés : tablier et garde-corps sur les `spans` « bridge » des arêtes (monde ouvert) et sur les ponts OSM croisés par un parcours compilé, piles sous un grand pont ; budgets GPU low, medium, high | EA1 | Moyenne |

Ordre proposé : EA1, puis EA2 (le défaut le plus visible depuis la route), EA3, EA4. Chaque lot : une branche et une PR, essai PC en low, medium et high, captures validées par le propriétaire avant fusion.

## Questions ouvertes

- Mer : sol abaissé sous la mer comme sous les lacs (EA1 la laisse comme U9 l'a validée) ?
- Eaux intermittentes (`intermittent=yes`) : aujourd'hui écartées ; les montrer à sec (lit de galets) ?
