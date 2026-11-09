# Rapport d'équilibrage du Grand Prix des objets (lot GP5)

**Lecture (8 novembre 2026).** Les valeurs par défaut du lot GP1 sont gardées. Le propriétaire a choisi une course juste, sans rattrapage fort : les cibles sont celles du cahier réécrit, toutes tenues. Le cycliste virtuel est mené par le même cerveau que les bots : à niveau égal, il gagne sa part, 1/(N + 1), aux variations près (± 3 à 5 points sur 200 courses). À 10 % sous les bots, il ne gagne presque jamais (0 à 2 %) mais regagne des places : 10 % de puissance font environ 30 s sur 10 km, et les objets ne rendent que 4 à 10 s chacun. Aucun objet ne dépasse 35 % du temps gagné ou perdu (le plus lourd : le vent contraire à 11 bots, autour de 23 %).

Produit par `python -m openride_core.tools.grandprix_sim` : 200 courses par configuration, graine 1, courses de 10 km en ligne, bots à 250 W (forme ± 3 %), pas de 0.2 s.

| Bots | Chaos | Niveau | Victoires du cycliste | Place moyenne | Objets par course | Objet le plus lourd |
| --- | --- | --- | --- | --- | --- | --- |
| 2 | soft | 100 % | 30.0 % | 1.99 | 6.9 | gel (16.1 %) |
| 2 | soft | 90 % | 0.0 % | 3.00 | 6.7 | gel_x3 (19.5 %) |
| 2 | normal | 100 % | 29.0 % | 2.08 | 10.3 | gel_x3 (19.5 %) |
| 2 | normal | 90 % | 0.0 % | 2.96 | 9.4 | team_car (18.9 %) |
| 2 | wild | 100 % | 35.5 % | 1.92 | 13.0 | gel (21.5 %) |
| 2 | wild | 90 % | 2.0 % | 2.86 | 11.8 | gel (18.9 %) |
| 4 | soft | 100 % | 23.0 % | 2.94 | 15.6 | team_car (17.3 %) |
| 4 | soft | 90 % | 0.5 % | 4.95 | 16.0 | team_car (21.2 %) |
| 4 | normal | 100 % | 14.0 % | 3.25 | 23.3 | gel_x3 (15.9 %) |
| 4 | normal | 90 % | 0.0 % | 4.87 | 24.8 | team_car (16.3 %) |
| 4 | wild | 100 % | 21.5 % | 3.00 | 30.4 | gel (15.7 %) |
| 4 | wild | 90 % | 1.0 % | 4.63 | 31.1 | gel_x3 (15.7 %) |
| 11 | soft | 100 % | 9.5 % | 6.51 | 38.0 | headwind (19.2 %) |
| 11 | soft | 90 % | 0.0 % | 11.89 | 39.2 | headwind (19.8 %) |
| 11 | normal | 100 % | 7.5 % | 6.30 | 56.0 | headwind (21.8 %) |
| 11 | normal | 90 % | 0.0 % | 11.85 | 58.7 | headwind (20.0 %) |
| 11 | wild | 100 % | 11.5 % | 6.21 | 71.8 | headwind (22.9 %) |
| 11 | wild | 90 % | 0.0 % | 11.55 | 74.6 | headwind (23.1 %) |

## Part de chaque objet dans le temps gagné ou perdu

| Bots | Chaos | Niveau | gel | gel_x3 | bottle | bottle_x3 | musette | musette_x3 | homing | storm | star | bell | headwind | team_car | stealth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | soft | 100 % | 16.1 | 15.3 | 9.7 | 3.3 | 7.0 | 3.3 | 5.3 | 9.1 | 8.5 | 1.8 | 5.6 | 15.1 | 0.0 |
| 2 | soft | 90 % | 16.1 | 19.5 | 6.2 | 2.5 | 4.9 | 3.5 | 4.5 | 6.9 | 10.1 | 2.1 | 4.4 | 19.1 | 0.0 |
| 2 | normal | 100 % | 19.0 | 19.5 | 7.0 | 4.9 | 8.0 | 3.7 | 7.2 | 7.3 | 9.3 | 2.5 | 7.3 | 4.5 | 0.0 |
| 2 | normal | 90 % | 16.4 | 16.7 | 4.6 | 2.6 | 5.1 | 2.9 | 5.1 | 9.3 | 9.5 | 1.8 | 7.0 | 18.9 | 0.0 |
| 2 | wild | 100 % | 21.5 | 19.1 | 7.1 | 2.1 | 7.3 | 3.5 | 7.2 | 7.3 | 9.1 | 2.9 | 6.8 | 6.1 | 0.0 |
| 2 | wild | 90 % | 18.9 | 15.9 | 4.7 | 1.7 | 6.6 | 2.9 | 6.2 | 9.8 | 11.1 | 2.1 | 6.1 | 14.0 | 0.0 |
| 4 | soft | 100 % | 13.8 | 13.2 | 5.8 | 3.6 | 5.3 | 3.3 | 5.9 | 10.5 | 8.5 | 2.7 | 9.9 | 17.3 | 0.0 |
| 4 | soft | 90 % | 14.1 | 13.1 | 4.7 | 3.5 | 4.0 | 2.2 | 5.0 | 10.2 | 9.2 | 2.1 | 10.9 | 21.2 | 0.0 |
| 4 | normal | 100 % | 14.9 | 15.9 | 6.0 | 3.4 | 7.0 | 2.8 | 7.3 | 8.9 | 9.6 | 2.4 | 10.5 | 11.3 | 0.0 |
| 4 | normal | 90 % | 15.2 | 14.3 | 4.5 | 2.9 | 5.7 | 2.9 | 6.3 | 9.9 | 9.9 | 2.1 | 10.0 | 16.3 | 0.0 |
| 4 | wild | 100 % | 15.7 | 15.2 | 4.9 | 1.8 | 7.4 | 3.3 | 8.0 | 9.6 | 9.7 | 2.2 | 11.1 | 11.2 | 0.0 |
| 4 | wild | 90 % | 15.6 | 15.7 | 4.1 | 1.8 | 6.5 | 3.1 | 7.4 | 8.7 | 10.0 | 1.8 | 10.5 | 14.6 | 0.0 |
| 11 | soft | 100 % | 10.5 | 11.5 | 3.3 | 2.6 | 4.4 | 2.2 | 6.1 | 11.4 | 9.1 | 2.2 | 19.2 | 17.5 | 0.0 |
| 11 | soft | 90 % | 10.9 | 10.2 | 3.2 | 2.2 | 4.6 | 2.4 | 5.8 | 10.6 | 9.2 | 2.2 | 19.8 | 18.9 | 0.0 |
| 11 | normal | 100 % | 10.8 | 10.6 | 3.9 | 1.8 | 5.6 | 2.6 | 5.7 | 10.2 | 10.1 | 1.7 | 21.8 | 15.3 | 0.0 |
| 11 | normal | 90 % | 10.7 | 11.1 | 3.9 | 1.9 | 5.3 | 2.8 | 6.0 | 10.5 | 9.7 | 1.5 | 20.0 | 16.7 | 0.0 |
| 11 | wild | 100 % | 11.6 | 11.3 | 3.4 | 1.5 | 6.1 | 2.7 | 6.2 | 9.4 | 10.3 | 1.9 | 22.9 | 12.8 | 0.0 |
| 11 | wild | 90 % | 11.4 | 10.5 | 3.1 | 1.5 | 5.7 | 2.7 | 5.9 | 9.6 | 9.9 | 1.8 | 23.1 | 14.6 | 0.0 |

## Cibles

- OK : 2 bots, chaos soft, niveau 100 % : 30.0 % de victoires (part juste, cible 16.7 à 50.0 %)
- OK : 2 bots, chaos soft, niveau 100 % : objet le plus lourd gel, 16.1 % du temps gagné ou perdu (au plus 35 %)
- OK : 2 bots, chaos soft, niveau 90 % : objet le plus lourd gel_x3, 19.5 % du temps gagné ou perdu (au plus 35 %)
- OK : 2 bots, chaos normal, niveau 100 % : 29.0 % de victoires (part juste, cible 16.7 à 50.0 %)
- OK : 2 bots, chaos normal, niveau 100 % : objet le plus lourd gel_x3, 19.5 % du temps gagné ou perdu (au plus 35 %)
- OK : 2 bots, chaos normal, niveau 90 % : objet le plus lourd team_car, 18.9 % du temps gagné ou perdu (au plus 35 %)
- OK : 2 bots, chaos wild, niveau 100 % : 35.5 % de victoires (part juste, cible 16.7 à 50.0 %)
- OK : 2 bots, chaos wild, niveau 100 % : objet le plus lourd gel, 21.5 % du temps gagné ou perdu (au plus 35 %)
- OK : 2 bots, chaos wild, niveau 90 % : objet le plus lourd gel, 18.9 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos soft, niveau 100 % : 23.0 % de victoires (part juste, cible 10.0 à 30.0 %)
- OK : 4 bots, chaos soft, niveau 100 % : objet le plus lourd team_car, 17.3 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos soft, niveau 90 % : objet le plus lourd team_car, 21.2 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos normal, niveau 100 % : 14.0 % de victoires (part juste, cible 10.0 à 30.0 %)
- OK : 4 bots, chaos normal, niveau 100 % : objet le plus lourd gel_x3, 15.9 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos normal, niveau 90 % : objet le plus lourd team_car, 16.3 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos wild, niveau 100 % : 21.5 % de victoires (part juste, cible 10.0 à 30.0 %)
- OK : 4 bots, chaos wild, niveau 100 % : objet le plus lourd gel, 15.7 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos wild, niveau 90 % : objet le plus lourd gel_x3, 15.7 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos soft, niveau 100 % : 9.5 % de victoires (part juste, cible 4.2 à 12.5 %)
- OK : 11 bots, chaos soft, niveau 100 % : objet le plus lourd headwind, 19.2 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos soft, niveau 90 % : objet le plus lourd headwind, 19.8 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos normal, niveau 100 % : 7.5 % de victoires (part juste, cible 4.2 à 12.5 %)
- OK : 11 bots, chaos normal, niveau 100 % : objet le plus lourd headwind, 21.8 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos normal, niveau 90 % : objet le plus lourd headwind, 20.0 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos wild, niveau 100 % : 11.5 % de victoires (part juste, cible 4.2 à 12.5 %)
- OK : 11 bots, chaos wild, niveau 100 % : objet le plus lourd headwind, 22.9 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos wild, niveau 90 % : objet le plus lourd headwind, 23.1 % du temps gagné ou perdu (au plus 35 %)
