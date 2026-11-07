# Rapport d'équilibrage de la Course tactique (lot CT0)

Produit par `python -m openride_core.tools.tactical_sim --report docs/5.0/RAPPORT_EQUILIBRAGE_CT0.md` (graine 1, 200 courses par configuration, table d'équilibrage `9d9f9d16`).
Ne pas modifier à la main : relancer l'outil.

Une configuration = un circuit généré × une stratégie du cycliste virtuel. Chaque course : le cycliste (FTP 250 W, W′ 20 kJ, 75 kg) et 4 bots à profil (forces relatives du lot T12) mis à une échelle commune : seuls, leur temps moyen sur le circuit est celui du cycliste seul à 95 % de la FTP (valeur `bots_level_pct` de la table) ; forme du jour tirée pour chacun.

Règles simulées par des bouchons tant que leurs lots ne sont pas faits (`tactical/bouchons.py`) : Burnout (CT2), catapulte (CT4), crédits et capacités (CT6), suivre ou lâcher (CT3). Non simulés : virages (CT7, pas de courbure sur les circuits générés), placement latéral (AS2), parade (CT5), variantes asymétriques (CT8).

## Critères du cahier (§7)

- [OK] stratégie suceur : 15.9 % de victoires du cycliste (au plus 45 %)
- [OK] stratégie rouleur : 9.7 % de victoires du cycliste (au plus 45 %)
- [OK] stratégie attaquant : 14.5 % de victoires du cycliste (au plus 45 %)
- [OK] stratégie echappee : 0.0 % de victoires du cycliste (moins de 20 %)
- [OK] stratégie mixte : 35.7 % de victoires du cycliste (au plus 45 %)
- [OK] profil Grimpeur : premier bot sur bosse_finale, col, vallonne
- [OK] profil Rouleur : premier bot sur faux_plat
- [OK] profil Sprinteur : premier bot sur plat
- [OK] profil Diesel : premier bot sur bosses_puis_plat, col_puis_plat

## Circuits

| Circuit | Longueur | Description | Échelle commune des bots |
| --- | --- | --- | --- |
| `plat` | 12.0 km | 12 km de plat, arrivée au sprint | 0.948 |
| `vallonne` | 15.0 km | 15 km de bosses de 800 m à 4 % | 0.931 |
| `col` | 11.0 km | 6 km de plat puis 5 km à 7 % | 0.921 |
| `bosse_finale` | 11.3 km | 10 km de plat puis 1 km à 5 % et 300 m de plat | 0.939 |
| `col_puis_plat` | 13.0 km | 4 km de plat, 3 km à 6 % puis 6 km de plat | 0.929 |
| `bosses_puis_plat` | 12.4 km | 4 bosses de 600 m à 5 % puis 4 km de plat | 0.932 |
| `faux_plat` | 14.0 km | 14 km de faux plat à 2,5 % | 0.926 |

## Victoires par stratégie (toutes configurations)

| Stratégie | Cycliste | Grimpeur | Rouleur | Sprinteur | Diesel |
| --- | --- | --- | --- | --- | --- |
| suceur | 15.9 % | 23.7 % | 12.0 % | 19.4 % | 29.0 % |
| rouleur | 9.7 % | 26.4 % | 9.4 % | 19.1 % | 35.4 % |
| attaquant | 14.5 % | 25.7 % | 10.8 % | 20.2 % | 28.8 % |
| echappee | 0.0 % | 74.8 % | 11.7 % | 12.6 % | 0.9 % |
| mixte | 35.7 % | 13.4 % | 8.1 % | 17.6 % | 25.2 % |

## Victoires par profil et par circuit (toutes stratégies)

| Circuit | Cycliste | Grimpeur | Rouleur | Sprinteur | Diesel |
| --- | --- | --- | --- | --- | --- |
| `plat` | 0.0 % | 0.1 % | 7.5 % | 92.1 % | 0.3 % |
| `vallonne` | 11.9 % | 42.3 % | 8.4 % | 0.2 % | 37.2 % |
| `col` | 9.0 % | 86.8 % | 0.9 % | 0.0 % | 3.3 % |
| `bosse_finale` | 40.8 % | 36.8 % | 7.2 % | 0.9 % | 14.3 % |
| `col_puis_plat` | 21.3 % | 25.6 % | 5.5 % | 2.7 % | 44.9 % |
| `bosses_puis_plat` | 14.8 % | 18.7 % | 3.6 % | 10.5 % | 52.4 % |
| `faux_plat` | 8.4 % | 19.2 % | 39.6 % | 18.2 % | 14.6 % |

## Détail par configuration

Écarts moyens à l'arrivée en secondes derrière le vainqueur ; Burnouts, catapultes : moyennes par course pour les 5 coureurs ; capacités : achetées par le cycliste.

| Circuit | Stratégie | Vainqueur le plus fréquent | Cycliste gagne | Écart cycliste | Écart G / R / S / D | Burnouts (dont cycliste) | Catapultes | Capacités |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `plat` | suceur | Sprinteur (99.5 %) | 0.0 % | 0.7 | 0.8 / 0.7 / 0.0 / 0.5 | 0.01 (0.00) | 5.49 | 0.00 |
| `plat` | rouleur | Sprinteur (100.0 %) | 0.0 % | 0.7 | 0.9 / 0.8 / 0.0 / 0.7 | 0.00 (0.00) | 4.99 | 1.00 |
| `plat` | attaquant | Sprinteur (99.0 %) | 0.0 % | 0.7 | 0.8 / 0.7 / 0.0 / 0.5 | 0.00 (0.00) | 5.53 | 0.00 |
| `plat` | echappee | Sprinteur (62.5 %) | 0.0 % | 3.0 | 3.0 / 0.5 / 2.1 / 2.7 | 0.01 (0.00) | 5.00 | 0.00 |
| `plat` | mixte | Sprinteur (99.5 %) | 0.0 % | 0.8 | 1.0 / 0.8 / 0.0 / 0.7 | 0.01 (0.00) | 4.94 | 1.00 |
| `vallonne` | suceur | Diesel (45.0 %) | 11.0 % | 49.5 | 0.7 / 48.3 / 97.1 / 10.3 | 2.23 (0.03) | 9.57 | 0.00 |
| `vallonne` | rouleur | Grimpeur (50.0 %) | 4.0 % | 42.2 | 0.5 / 46.0 / 82.4 / 0.7 | 2.67 (0.00) | 8.86 | 1.08 |
| `vallonne` | attaquant | Grimpeur (43.0 %) | 7.5 % | 56.7 | 0.7 / 51.9 / 103.4 / 13.1 | 2.19 (0.04) | 9.48 | 0.00 |
| `vallonne` | echappee | Grimpeur (83.0 %) | 0.0 % | 22.9 | 0.7 / 17.4 / 23.2 / 22.4 | 1.26 (0.00) | 5.71 | 0.00 |
| `vallonne` | mixte | Diesel (59.0 %) | 37.0 % | 0.3 | 4.0 / 69.9 / 87.9 / 5.0 | 3.27 (0.01) | 13.80 | 3.85 |
| `col` | suceur | Grimpeur (83.5 %) | 13.0 % | 60.5 | 0.7 / 98.3 / 167.7 / 91.3 | 8.79 (2.44) | 3.73 | 0.00 |
| `col` | rouleur | Grimpeur (84.5 %) | 6.5 % | 89.7 | 0.6 / 107.5 / 170.8 / 37.8 | 10.75 (1.64) | 3.21 | 1.00 |
| `col` | attaquant | Grimpeur (87.0 %) | 11.0 % | 67.1 | 0.5 / 107.0 / 174.9 / 98.4 | 8.84 (2.54) | 3.75 | 0.00 |
| `col` | echappee | Grimpeur (98.5 %) | 0.0 % | 100.1 | 0.1 / 92.4 / 138.5 / 104.1 | 4.76 (0.00) | 4.33 | 0.00 |
| `col` | mixte | Grimpeur (80.5 %) | 14.5 % | 38.5 | 0.9 / 107.4 / 163.9 / 40.9 | 13.65 (4.75) | 3.93 | 2.57 |
| `bosse_finale` | suceur | Cycliste (52.5 %) | 52.5 % | 2.3 | 0.1 / 10.9 / 26.2 / 6.9 | 0.85 (0.00) | 5.59 | 0.00 |
| `bosse_finale` | rouleur | Grimpeur (43.5 %) | 14.5 % | 9.0 | 0.2 / 8.7 / 22.9 / 1.5 | 1.17 (0.00) | 5.66 | 1.00 |
| `bosse_finale` | attaquant | Cycliste (50.5 %) | 50.5 % | 1.3 | 0.1 / 9.9 / 27.0 / 6.0 | 0.85 (0.00) | 5.36 | 0.00 |
| `bosse_finale` | echappee | Grimpeur (90.0 %) | 0.0 % | 32.8 | 0.1 / 22.7 / 31.7 / 28.8 | 0.20 (0.00) | 5.31 | 0.00 |
| `bosse_finale` | mixte | Cycliste (86.5 %) | 86.5 % | 0.0 | 0.2 / 18.5 / 28.6 / 5.8 | 0.99 (0.00) | 6.45 | 1.67 |
| `col_puis_plat` | suceur | Diesel (58.0 %) | 17.5 % | 9.2 | 0.2 / 22.2 / 60.6 / 16.2 | 0.17 (0.00) | 4.61 | 0.00 |
| `col_puis_plat` | rouleur | Diesel (65.5 %) | 24.0 % | 27.4 | 0.2 / 32.8 / 86.6 / 3.1 | 0.29 (0.00) | 4.52 | 1.00 |
| `col_puis_plat` | attaquant | Diesel (55.5 %) | 18.0 % | 8.0 | 0.2 / 21.9 / 56.5 / 13.1 | 0.20 (0.00) | 4.78 | 0.00 |
| `col_puis_plat` | echappee | Grimpeur (92.0 %) | 0.0 % | 35.4 | 0.1 / 29.0 / 35.5 / 35.2 | 0.09 (0.00) | 5.00 | 0.00 |
| `col_puis_plat` | mixte | Cycliste (47.0 %) | 47.0 % | 1.2 | 0.2 / 52.8 / 80.2 / 4.3 | 1.03 (0.14) | 5.17 | 2.75 |
| `bosses_puis_plat` | suceur | Diesel (69.0 %) | 6.0 % | 37.0 | 0.3 / 31.4 / 61.1 / 7.5 | 0.20 (0.00) | 7.66 | 0.00 |
| `bosses_puis_plat` | rouleur | Diesel (83.0 %) | 8.5 % | 27.4 | 0.3 / 28.9 / 64.9 / 0.1 | 0.28 (0.00) | 7.29 | 1.03 |
| `bosses_puis_plat` | attaquant | Diesel (65.5 %) | 6.5 % | 40.8 | 0.3 / 35.5 / 59.6 / 8.1 | 0.18 (0.00) | 7.60 | 0.00 |
| `bosses_puis_plat` | echappee | Grimpeur (71.5 %) | 0.0 % | 13.8 | 0.3 / 12.2 / 12.9 / 13.5 | 0.17 (0.00) | 5.28 | 0.00 |
| `bosses_puis_plat` | mixte | Cycliste (53.0 %) | 53.0 % | 0.4 | 2.2 / 42.1 / 51.1 / 2.6 | 0.80 (0.00) | 9.93 | 3.56 |
| `faux_plat` | suceur | Rouleur (50.5 %) | 11.5 % | 5.1 | 5.8 / 0.1 / 81.7 / 81.4 | 1.17 (0.00) | 4.08 | 0.00 |
| `faux_plat` | rouleur | Rouleur (45.0 %) | 10.5 % | 4.3 | 4.9 / 0.2 / 67.9 / 67.7 | 1.12 (0.00) | 4.19 | 0.00 |
| `faux_plat` | attaquant | Rouleur (46.0 %) | 8.0 % | 4.6 | 5.2 / 0.2 / 63.5 / 63.3 | 1.12 (0.00) | 4.25 | 0.00 |
| `faux_plat` | echappee | Grimpeur (88.0 %) | 0.0 % | 43.4 | 0.5 / 35.2 / 42.7 / 43.0 | 1.20 (0.00) | 4.46 | 0.00 |
| `faux_plat` | mixte | Rouleur (50.0 %) | 12.0 % | 5.0 | 5.6 / 0.2 / 66.6 / 66.4 | 1.11 (0.00) | 4.75 | 0.00 |
