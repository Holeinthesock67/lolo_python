# Rapport d'équilibrage de la Course tactique (lot CT0)

Produit par `python -m openride_core.tools.tactical_sim --report docs/5.0/RAPPORT_EQUILIBRAGE_CT0.md` (graine 1, 200 courses par configuration, table d'équilibrage `7f883a4b`).
Ne pas modifier à la main : relancer l'outil.

Une configuration = un circuit généré × une stratégie du cycliste virtuel. Chaque course : le cycliste (FTP 250 W, W′ 20 kJ, 75 kg) et 6 bots à profil (forces relatives du lot T12, plus le baroudeur et le puncheur du simulateur) mis à une échelle commune : seuls, leur temps moyen sur le circuit est celui du cycliste seul à 95 % de la FTP (valeur `bots_level_pct` de la table) ; forme du jour tirée pour chacun.

Règles simulées par des bouchons tant que leurs lots ne sont pas faits (`tactical/bouchons.py`) : Burnout (CT2), catapulte (CT4), crédits et capacités (CT6), suivre ou lâcher (CT3). Non simulés : virages (CT7, pas de courbure sur les circuits générés), placement latéral (AS2), parade (CT5), variantes asymétriques (CT8).

## Critères du cahier (§7)

- [OK] stratégie suceur : 2.8 % de victoires du cycliste (au plus 45 %)
- [OK] stratégie rouleur : 2.9 % de victoires du cycliste (au plus 45 %)
- [OK] stratégie attaquant : 3.3 % de victoires du cycliste (au plus 45 %)
- [OK] stratégie echappee : 0.6 % de victoires du cycliste (moins de 20 %)
- [OK] stratégie mixte : 19.9 % de victoires du cycliste (au plus 45 %)
- [OK] profil Grimpeur : premier bot sur bosse_finale, col, col_puis_plat
- [EN ATTENTE] profil Rouleur : premier bot sur aucun circuit (en attente : bordures par vent de travers du lot CT20, pas encore simulées)
- [OK] profil Sprinteur : premier bot sur plat
- [OK] profil Diesel : premier bot sur bosses_puis_plat, longue_distance
- [OK] profil Baroudeur : premier bot sur faux_plat
- [OK] profil Puncheur : premier bot sur mur_final, vallonne

Part des victoires sur tout le calendrier (cible : environ 14 % chacun) : Cycliste 5.9 %, Grimpeur 29.6 %, Rouleur 9.0 %, Sprinteur 9.6 %, Diesel 15.0 %, Baroudeur 13.2 %, Puncheur 17.7 %.

## Classement Elo

Toutes les courses du rapport, dans l'ordre (départ à 1 500, K = 24, duels par paires) ; chaque stratégie du cycliste a son propre classement. Un profil équilibré reste près de 1 500.

| Coureur | Elo |
| --- | --- |
| Rouleur | 1739 |
| Baroudeur | 1703 |
| Diesel | 1671 |
| Cycliste (suceur) | 1547 |
| Cycliste (mixte) | 1486 |
| Cycliste (attaquant) | 1478 |
| Puncheur | 1472 |
| Cycliste (rouleur) | 1469 |
| Grimpeur | 1390 |
| Sprinteur | 1350 |
| Cycliste (echappee) | 1195 |

## Circuits

| Circuit | Longueur | Description | Échelle commune des bots |
| --- | --- | --- | --- |
| `plat` | 12.0 km | 12 km de plat, arrivée au sprint | 0.949 |
| `vallonne` | 15.0 km | 15 km de bosses de 800 m à 4 % | 0.929 |
| `col` | 11.0 km | 6 km de plat puis 5 km à 7 % | 0.918 |
| `bosse_finale` | 11.3 km | 10 km de plat puis 1 km à 5 % et 300 m de plat | 0.938 |
| `col_puis_plat` | 13.0 km | 4 km de plat, 3 km à 6 % puis 6 km de plat | 0.926 |
| `bosses_puis_plat` | 12.4 km | 4 bosses de 600 m à 5 % puis 4 km de plat | 0.931 |
| `mur_final` | 10.5 km | 10 km de plat vallonné puis un mur de 500 m à 9 % | 0.934 |
| `longue_distance` | 16.0 km | 16 km de faux plats : 3 km de plat puis 1 km à 2 %, quatre fois | 0.941 |
| `faux_plat` | 14.0 km | 14 km de faux plat à 2,5 % | 0.925 |

## Victoires par stratégie (toutes configurations)

| Stratégie | Cycliste | Grimpeur | Rouleur | Sprinteur | Diesel | Baroudeur | Puncheur |
| --- | --- | --- | --- | --- | --- | --- | --- |
| suceur | 2.8 % | 29.3 % | 10.0 % | 10.8 % | 17.7 % | 11.4 % | 17.9 % |
| rouleur | 2.9 % | 26.0 % | 10.2 % | 14.3 % | 19.4 % | 11.1 % | 16.1 % |
| attaquant | 3.3 % | 30.4 % | 10.1 % | 11.8 % | 16.1 % | 11.0 % | 17.4 % |
| echappee | 0.6 % | 36.7 % | 8.1 % | 1.3 % | 4.6 % | 25.7 % | 23.1 % |
| mixte | 19.9 % | 25.4 % | 6.5 % | 9.8 % | 17.4 % | 6.9 % | 13.9 % |

## Victoires par profil et par circuit (toutes stratégies)

| Circuit | Cycliste | Grimpeur | Rouleur | Sprinteur | Diesel | Baroudeur | Puncheur |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `plat` | 0.8 % | 0.9 % | 10.7 % | 53.8 % | 15.8 % | 14.0 % | 4.0 % |
| `vallonne` | 10.5 % | 21.7 % | 6.6 % | 0.1 % | 14.0 % | 21.2 % | 25.9 % |
| `col` | 3.0 % | 95.8 % | 0.0 % | 0.0 % | 1.2 % | 0.0 % | 0.0 % |
| `bosse_finale` | 4.1 % | 42.5 % | 9.0 % | 0.0 % | 1.2 % | 6.3 % | 36.9 % |
| `col_puis_plat` | 8.0 % | 45.1 % | 3.1 % | 7.5 % | 25.4 % | 9.8 % | 1.1 % |
| `bosses_puis_plat` | 2.6 % | 11.9 % | 4.9 % | 20.2 % | 35.9 % | 6.1 % | 18.4 % |
| `mur_final` | 17.8 % | 22.6 % | 13.8 % | 0.0 % | 0.4 % | 4.0 % | 41.4 % |
| `longue_distance` | 4.9 % | 13.6 % | 5.7 % | 4.9 % | 33.7 % | 12.3 % | 24.9 % |
| `faux_plat` | 1.4 % | 12.0 % | 27.0 % | 0.0 % | 7.8 % | 45.3 % | 6.5 % |

## Détail par configuration

Écarts moyens à l'arrivée en secondes derrière le vainqueur ; Burnouts, catapultes : moyennes par course pour les 5 coureurs ; capacités : achetées par le cycliste.

| Circuit | Stratégie | Vainqueur le plus fréquent | Cycliste gagne | Écart cycliste | Écart G / R / S / D / B / P | Burnouts (dont cycliste) | Catapultes | Capacités |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `plat` | suceur | Sprinteur (55.5 %) | 1.5 % | 1.5 | 3.8 / 1.3 / 2.6 / 1.5 / 1.4 / 3.9 | 0.73 (0.00) | 8.41 | 0.00 |
| `plat` | rouleur | Sprinteur (75.5 %) | 0.0 % | 1.5 | 4.0 / 1.1 / 1.0 / 0.9 / 1.5 / 2.9 | 0.85 (0.00) | 8.48 | 1.00 |
| `plat` | attaquant | Sprinteur (57.5 %) | 1.5 % | 1.7 | 4.0 / 1.7 / 2.7 / 1.7 / 2.0 / 4.6 | 0.78 (0.00) | 8.65 | 0.00 |
| `plat` | echappee | Baroudeur (42.5 %) | 0.0 % | 12.9 | 12.0 / 6.9 / 12.2 / 12.4 / 3.8 / 9.8 | 1.20 (0.00) | 8.09 | 0.00 |
| `plat` | mixte | Sprinteur (72.0 %) | 1.0 % | 1.5 | 3.1 / 1.0 / 1.0 / 1.1 / 1.3 / 2.6 | 0.88 (0.00) | 8.61 | 0.99 |
| `vallonne` | suceur | Puncheur (29.5 %) | 1.5 % | 52.0 | 4.9 / 42.9 / 68.5 / 34.7 / 43.6 / 12.8 | 5.08 (0.00) | 20.01 | 0.00 |
| `vallonne` | rouleur | Grimpeur (22.5 %) | 6.5 % | 12.5 | 7.2 / 13.6 / 29.1 / 2.2 / 19.5 / 17.3 | 6.11 (0.00) | 19.70 | 1.04 |
| `vallonne` | attaquant | Puncheur (34.5 %) | 2.5 % | 52.6 | 4.4 / 44.0 / 66.4 / 36.0 / 42.9 / 11.6 | 5.09 (0.01) | 20.17 | 0.00 |
| `vallonne` | echappee | Baroudeur (38.0 %) | 0.0 % | 55.1 | 9.6 / 45.9 / 55.4 / 48.2 / 17.0 / 13.1 | 4.98 (0.00) | 18.52 | 0.00 |
| `vallonne` | mixte | Cycliste (42.0 %) | 42.0 % | 2.1 | 4.9 / 25.0 / 36.2 / 8.0 / 31.5 / 25.3 | 7.22 (0.14) | 21.85 | 3.64 |
| `col` | suceur | Grimpeur (100.0 %) | 0.0 % | 93.1 | 0.0 / 92.1 / 143.3 / 94.8 / 87.0 / 85.6 | 10.31 (0.10) | 7.74 | 0.00 |
| `col` | rouleur | Grimpeur (97.5 %) | 0.0 % | 114.8 | 0.1 / 96.1 / 148.4 / 86.0 / 90.7 / 92.4 | 10.91 (0.07) | 7.96 | 0.32 |
| `col` | attaquant | Grimpeur (99.5 %) | 0.0 % | 95.8 | 0.0 / 96.1 / 148.9 / 101.6 / 90.8 / 86.4 | 10.08 (0.06) | 7.70 | 0.00 |
| `col` | echappee | Grimpeur (99.5 %) | 0.0 % | 94.8 | 0.0 / 92.6 / 142.0 / 103.0 / 87.4 / 98.6 | 10.30 (0.00) | 7.74 | 0.00 |
| `col` | mixte | Grimpeur (82.5 %) | 15.0 % | 35.8 | 1.1 / 100.8 / 146.8 / 75.3 / 90.8 / 93.4 | 16.46 (4.81) | 8.93 | 0.33 |
| `bosse_finale` | suceur | Puncheur (38.5 %) | 4.0 % | 13.0 | 3.6 / 14.8 / 27.8 / 15.4 / 16.3 / 3.9 | 2.84 (0.00) | 9.53 | 0.00 |
| `bosse_finale` | rouleur | Puncheur (45.0 %) | 1.0 % | 12.6 | 2.3 / 16.0 / 26.5 / 12.0 / 18.2 / 2.7 | 2.98 (0.00) | 9.78 | 1.00 |
| `bosse_finale` | attaquant | Grimpeur (40.0 %) | 5.0 % | 12.4 | 3.1 / 16.4 / 27.6 / 15.9 / 17.1 / 3.2 | 2.79 (0.00) | 9.44 | 0.00 |
| `bosse_finale` | echappee | Grimpeur (56.5 %) | 0.0 % | 35.8 | 2.2 / 24.2 / 35.2 / 31.8 / 21.6 / 4.0 | 1.89 (0.00) | 8.88 | 0.00 |
| `bosse_finale` | mixte | Grimpeur (43.0 %) | 10.5 % | 4.2 | 2.6 / 16.0 / 24.4 / 13.9 / 18.0 / 2.8 | 3.17 (0.01) | 11.07 | 1.00 |
| `col_puis_plat` | suceur | Grimpeur (53.0 %) | 0.5 % | 21.4 | 1.2 / 19.2 / 30.0 / 13.6 / 15.2 / 20.1 | 0.99 (0.00) | 9.24 | 0.00 |
| `col_puis_plat` | rouleur | Diesel (41.0 %) | 0.5 % | 10.9 | 1.8 / 11.1 / 26.2 / 3.3 / 6.2 / 11.8 | 1.29 (0.00) | 8.97 | 0.99 |
| `col_puis_plat` | attaquant | Grimpeur (55.5 %) | 1.0 % | 21.0 | 1.2 / 18.7 / 29.1 / 14.5 / 16.1 / 20.7 | 1.11 (0.00) | 9.35 | 0.00 |
| `col_puis_plat` | echappee | Grimpeur (65.0 %) | 0.0 % | 38.8 | 0.6 / 31.1 / 38.4 / 31.6 / 10.0 / 35.4 | 1.50 (0.00) | 8.47 | 0.00 |
| `col_puis_plat` | mixte | Cycliste (38.0 %) | 38.0 % | 0.6 | 0.6 / 25.8 / 42.5 / 10.3 / 22.2 / 27.0 | 1.64 (0.03) | 10.13 | 1.67 |
| `bosses_puis_plat` | suceur | Diesel (38.0 %) | 1.0 % | 25.5 | 3.4 / 19.4 / 23.4 / 9.8 / 26.8 / 10.7 | 1.38 (0.00) | 15.09 | 0.00 |
| `bosses_puis_plat` | rouleur | Diesel (41.5 %) | 0.5 % | 7.7 | 4.0 / 8.0 / 12.8 / 1.4 / 15.4 / 10.5 | 1.58 (0.00) | 14.68 | 1.01 |
| `bosses_puis_plat` | attaquant | Diesel (37.5 %) | 0.0 % | 24.1 | 2.9 / 18.5 / 23.5 / 10.9 / 26.2 / 9.9 | 1.17 (0.00) | 15.21 | 0.00 |
| `bosses_puis_plat` | echappee | Puncheur (35.5 %) | 0.0 % | 40.3 | 2.6 / 30.8 / 37.8 / 23.4 / 13.3 / 7.2 | 1.81 (0.00) | 14.01 | 0.00 |
| `bosses_puis_plat` | mixte | Diesel (43.0 %) | 11.5 % | 1.6 | 4.9 / 18.6 / 21.8 / 4.7 / 25.7 / 18.8 | 2.19 (0.00) | 16.84 | 2.92 |
| `mur_final` | suceur | Puncheur (45.5 %) | 14.5 % | 7.8 | 8.6 / 11.9 / 32.3 / 15.6 / 17.7 / 6.6 | 15.23 (0.08) | 14.86 | 0.00 |
| `mur_final` | rouleur | Puncheur (40.0 %) | 17.0 % | 6.8 | 7.9 / 12.0 / 30.3 / 15.2 / 19.2 / 7.2 | 16.14 (0.02) | 14.92 | 0.88 |
| `mur_final` | attaquant | Puncheur (26.5 %) | 18.5 % | 6.8 | 6.6 / 11.4 / 32.1 / 16.0 / 17.0 / 9.4 | 15.26 (0.03) | 14.57 | 0.00 |
| `mur_final` | echappee | Puncheur (61.0 %) | 0.0 % | 29.4 | 8.0 / 20.6 / 42.3 / 24.3 / 20.4 / 4.0 | 14.27 (0.00) | 13.82 | 0.00 |
| `mur_final` | mixte | Cycliste (39.0 %) | 39.0 % | 3.3 | 8.2 / 16.6 / 33.9 / 19.3 / 24.9 / 8.7 | 16.66 (1.39) | 16.62 | 2.68 |
| `longue_distance` | suceur | Diesel (48.0 %) | 1.5 % | 19.9 | 5.4 / 12.0 / 18.0 / 2.7 / 21.3 / 4.3 | 2.36 (0.00) | 19.35 | 0.00 |
| `longue_distance` | rouleur | Diesel (45.0 %) | 0.5 % | 8.0 | 5.0 / 6.6 / 14.6 / 1.7 / 15.9 / 3.5 | 2.60 (0.00) | 19.30 | 0.93 |
| `longue_distance` | attaquant | Diesel (37.0 %) | 0.5 % | 19.7 | 6.5 / 13.4 / 20.9 / 3.1 / 22.6 / 5.1 | 2.48 (0.00) | 19.12 | 0.00 |
| `longue_distance` | echappee | Baroudeur (36.5 %) | 0.0 % | 36.6 | 6.7 / 28.4 / 35.8 / 33.5 / 4.2 / 2.8 | 2.17 (0.00) | 17.98 | 0.00 |
| `longue_distance` | mixte | Diesel (36.5 %) | 22.0 % | 1.2 | 6.7 / 8.7 / 14.1 / 2.7 / 16.5 / 6.3 | 2.69 (0.00) | 21.77 | 3.78 |
| `faux_plat` | suceur | Baroudeur (41.0 %) | 1.0 % | 15.5 | 12.7 / 7.3 / 30.1 / 28.7 / 13.4 / 27.4 | 3.69 (0.00) | 11.11 | 0.00 |
| `faux_plat` | rouleur | Baroudeur (49.0 %) | 0.0 % | 13.9 | 12.1 / 7.1 / 56.9 / 53.0 / 10.1 / 51.6 | 3.59 (0.00) | 13.14 | 0.00 |
| `faux_plat` | attaquant | Baroudeur (38.0 %) | 0.5 % | 15.2 | 12.7 / 7.6 / 26.3 / 24.3 / 11.5 / 22.3 | 3.47 (0.00) | 11.54 | 0.00 |
| `faux_plat` | echappee | Baroudeur (62.5 %) | 5.0 % | 45.1 | 9.1 / 36.6 / 48.3 / 48.0 / 11.2 / 44.3 | 3.42 (0.00) | 10.05 | 0.00 |
| `faux_plat` | mixte | Baroudeur (36.0 %) | 0.5 % | 16.1 | 14.3 / 7.9 / 38.1 / 33.9 / 13.6 / 33.3 | 3.62 (0.00) | 11.41 | 0.00 |
