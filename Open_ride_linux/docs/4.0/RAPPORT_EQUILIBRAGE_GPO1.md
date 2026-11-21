# Rapport d'équilibrage du Grand Prix des objets (lot GPO1)

**Lecture (21 novembre 2026).** Valeurs du lot GPO1 (tout effet dure, objets plus forts et plus longs, boîtes de famille par voie, bots qui choisissent leur voie). Toutes les cibles du lot GP5 restent tenues : à niveau égal, le cycliste gagne sa part (1/(N + 1), ± quelques points) ; aucun objet ne dépasse 35 % du temps gagné ou perdu (le plus lourd : 23,7 %). Les objets pèsent plus par course (2 bots normal : 12,8 objets au lieu de 10,3) sans casser la course juste choisie le 8 novembre. Rapport d'avant : `RAPPORT_EQUILIBRAGE_GP5.md`.

Produit par `python -m openride_core.tools.grandprix_sim` : 200 courses par configuration, graine 1, courses de 10 km en ligne, bots à 250 W (forme ± 3 %), pas de 0.2 s.

| Bots | Chaos | Niveau | Victoires du cycliste | Place moyenne | Objets par course | Objet le plus lourd |
| --- | --- | --- | --- | --- | --- | --- |
| 2 | soft | 100 % | 30.0 % | 2.01 | 8.3 | gel_x3 (21.4 %) |
| 2 | soft | 90 % | 0.0 % | 2.98 | 7.5 | team_car (18.9 %) |
| 2 | normal | 100 % | 30.5 % | 1.99 | 12.8 | gel (19.5 %) |
| 2 | normal | 90 % | 1.0 % | 2.85 | 11.6 | gel (22.2 %) |
| 2 | wild | 100 % | 32.0 % | 2.00 | 15.7 | gel_x3 (21.7 %) |
| 2 | wild | 90 % | 3.5 % | 2.79 | 14.6 | gel (23.7 %) |
| 4 | soft | 100 % | 19.0 % | 2.83 | 18.8 | team_car (20.2 %) |
| 4 | soft | 90 % | 0.5 % | 4.93 | 18.7 | team_car (22.5 %) |
| 4 | normal | 100 % | 17.5 % | 3.17 | 28.4 | gel (20.5 %) |
| 4 | normal | 90 % | 0.5 % | 4.82 | 29.0 | gel_x3 (19.4 %) |
| 4 | wild | 100 % | 21.5 % | 2.91 | 37.1 | gel (21.2 %) |
| 4 | wild | 90 % | 0.5 % | 4.26 | 38.6 | gel_x3 (21.2 %) |
| 11 | soft | 100 % | 11.5 % | 6.25 | 44.5 | team_car (21.9 %) |
| 11 | soft | 90 % | 0.0 % | 11.95 | 45.9 | team_car (23.7 %) |
| 11 | normal | 100 % | 9.0 % | 6.20 | 62.6 | star (19.5 %) |
| 11 | normal | 90 % | 0.0 % | 11.53 | 64.7 | star (18.2 %) |
| 11 | wild | 100 % | 6.5 % | 6.34 | 81.5 | star (20.8 %) |
| 11 | wild | 90 % | 1.0 % | 10.48 | 83.2 | star (20.4 %) |

## Part de chaque objet dans le temps gagné ou perdu

| Bots | Chaos | Niveau | gel | gel_x3 | bottle | bottle_x3 | musette | musette_x3 | homing | storm | star | bell | headwind | team_car | stealth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | soft | 100 % | 18.9 | 21.4 | 10.2 | 3.2 | 8.5 | 3.5 | 4.4 | 2.1 | 13.7 | 0.5 | 5.2 | 8.3 | 0.0 |
| 2 | soft | 90 % | 16.1 | 18.7 | 8.3 | 2.7 | 6.4 | 2.3 | 3.3 | 2.6 | 15.3 | 0.4 | 4.9 | 18.9 | 0.0 |
| 2 | normal | 100 % | 19.5 | 19.2 | 9.1 | 3.2 | 11.7 | 5.3 | 4.2 | 2.9 | 14.5 | 0.5 | 6.4 | 3.5 | 0.0 |
| 2 | normal | 90 % | 22.2 | 21.8 | 4.8 | 2.0 | 7.2 | 2.9 | 3.3 | 2.9 | 16.6 | 0.4 | 4.5 | 11.4 | 0.0 |
| 2 | wild | 100 % | 21.6 | 21.7 | 7.5 | 2.4 | 10.3 | 5.3 | 4.2 | 2.6 | 15.4 | 0.6 | 7.6 | 0.7 | 0.0 |
| 2 | wild | 90 % | 23.7 | 23.6 | 4.9 | 2.0 | 7.7 | 3.4 | 4.1 | 2.4 | 16.7 | 0.6 | 5.6 | 5.1 | 0.0 |
| 4 | soft | 100 % | 18.4 | 17.1 | 6.1 | 2.9 | 3.6 | 1.9 | 3.2 | 4.0 | 15.9 | 0.5 | 6.1 | 20.2 | 0.0 |
| 4 | soft | 90 % | 18.0 | 16.8 | 5.0 | 2.4 | 4.6 | 1.8 | 3.7 | 3.6 | 14.6 | 0.5 | 6.4 | 22.5 | 0.0 |
| 4 | normal | 100 % | 20.5 | 19.6 | 6.2 | 2.8 | 6.6 | 3.5 | 4.7 | 3.5 | 15.8 | 0.9 | 7.5 | 8.6 | 0.0 |
| 4 | normal | 90 % | 19.1 | 19.4 | 5.0 | 2.1 | 5.5 | 3.0 | 4.5 | 4.3 | 15.8 | 0.6 | 7.4 | 13.5 | 0.0 |
| 4 | wild | 100 % | 21.2 | 19.2 | 5.8 | 1.9 | 7.8 | 4.0 | 4.8 | 4.2 | 18.0 | 0.8 | 7.8 | 4.4 | 0.0 |
| 4 | wild | 90 % | 21.2 | 21.2 | 4.2 | 1.8 | 6.9 | 3.6 | 4.4 | 3.5 | 18.0 | 0.7 | 6.9 | 7.6 | 0.0 |
| 11 | soft | 100 % | 14.9 | 15.4 | 4.2 | 2.4 | 3.4 | 1.7 | 2.8 | 4.9 | 16.4 | 0.8 | 11.3 | 21.9 | 0.0 |
| 11 | soft | 90 % | 14.9 | 14.5 | 3.8 | 1.8 | 3.3 | 1.6 | 2.6 | 4.4 | 16.3 | 1.0 | 12.2 | 23.7 | 0.0 |
| 11 | normal | 100 % | 16.1 | 16.1 | 4.3 | 1.8 | 4.2 | 2.0 | 3.1 | 4.5 | 19.5 | 0.7 | 13.4 | 14.3 | 0.0 |
| 11 | normal | 90 % | 16.0 | 16.7 | 3.9 | 1.6 | 4.0 | 2.0 | 3.2 | 4.8 | 18.2 | 0.7 | 12.5 | 16.3 | 0.0 |
| 11 | wild | 100 % | 16.6 | 17.2 | 3.6 | 1.5 | 4.8 | 2.4 | 3.3 | 4.2 | 20.8 | 0.9 | 14.2 | 10.6 | 0.0 |
| 11 | wild | 90 % | 16.7 | 17.0 | 3.2 | 1.5 | 4.4 | 2.2 | 3.3 | 4.4 | 20.4 | 0.7 | 13.7 | 12.5 | 0.0 |

## Cibles

- OK : 2 bots, chaos soft, niveau 100 % : 30.0 % de victoires (part juste, cible 16.7 à 50.0 %)
- OK : 2 bots, chaos soft, niveau 100 % : objet le plus lourd gel_x3, 21.4 % du temps gagné ou perdu (au plus 35 %)
- OK : 2 bots, chaos soft, niveau 90 % : objet le plus lourd team_car, 18.9 % du temps gagné ou perdu (au plus 35 %)
- OK : 2 bots, chaos normal, niveau 100 % : 30.5 % de victoires (part juste, cible 16.7 à 50.0 %)
- OK : 2 bots, chaos normal, niveau 100 % : objet le plus lourd gel, 19.5 % du temps gagné ou perdu (au plus 35 %)
- OK : 2 bots, chaos normal, niveau 90 % : objet le plus lourd gel, 22.2 % du temps gagné ou perdu (au plus 35 %)
- OK : 2 bots, chaos wild, niveau 100 % : 32.0 % de victoires (part juste, cible 16.7 à 50.0 %)
- OK : 2 bots, chaos wild, niveau 100 % : objet le plus lourd gel_x3, 21.7 % du temps gagné ou perdu (au plus 35 %)
- OK : 2 bots, chaos wild, niveau 90 % : objet le plus lourd gel, 23.7 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos soft, niveau 100 % : 19.0 % de victoires (part juste, cible 10.0 à 30.0 %)
- OK : 4 bots, chaos soft, niveau 100 % : objet le plus lourd team_car, 20.2 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos soft, niveau 90 % : objet le plus lourd team_car, 22.5 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos normal, niveau 100 % : 17.5 % de victoires (part juste, cible 10.0 à 30.0 %)
- OK : 4 bots, chaos normal, niveau 100 % : objet le plus lourd gel, 20.5 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos normal, niveau 90 % : objet le plus lourd gel_x3, 19.4 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos wild, niveau 100 % : 21.5 % de victoires (part juste, cible 10.0 à 30.0 %)
- OK : 4 bots, chaos wild, niveau 100 % : objet le plus lourd gel, 21.2 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos wild, niveau 90 % : objet le plus lourd gel_x3, 21.2 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos soft, niveau 100 % : 11.5 % de victoires (part juste, cible 4.2 à 12.5 %)
- OK : 11 bots, chaos soft, niveau 100 % : objet le plus lourd team_car, 21.9 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos soft, niveau 90 % : objet le plus lourd team_car, 23.7 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos normal, niveau 100 % : 9.0 % de victoires (part juste, cible 4.2 à 12.5 %)
- OK : 11 bots, chaos normal, niveau 100 % : objet le plus lourd star, 19.5 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos normal, niveau 90 % : objet le plus lourd star, 18.2 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos wild, niveau 100 % : 6.5 % de victoires (part juste, cible 4.2 à 12.5 %)
- OK : 11 bots, chaos wild, niveau 100 % : objet le plus lourd star, 20.8 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos wild, niveau 90 % : objet le plus lourd star, 20.4 % du temps gagné ou perdu (au plus 35 %)
