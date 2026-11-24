# Rapport d'équilibrage du Grand Prix des objets (lot GPO1)

**Lecture (22 novembre 2026, après l'essai vélo du jour).** Valeurs du lot GPO1 : tout effet dure, boîtes de famille par voie, bots qui choisissent leur voie ; puis, après l'essai, glissade à 60 % pendant 5 s, esquive des bots réduite (0,18 / 0,30 / 0,45), sonnette des bots après un temps de réaction de 0,6 à 1,5 s et onde de 15 m. Toutes les cibles du lot GP5 restent tenues : à niveau égal, le cycliste gagne sa part (1/(N + 1), à quelques points près) ; aucun objet ne dépasse 35 % du temps gagné ou perdu (le plus lourd : 22,9 %). Rapport d'avant : `RAPPORT_EQUILIBRAGE_GP5.md`.

Produit par `python -m openride_core.tools.grandprix_sim` : 200 courses par configuration, graine 1, courses de 10 km en ligne, bots à 250 W (forme ± 3 %), pas de 0.2 s.

| Bots | Chaos | Niveau | Victoires du cycliste | Place moyenne | Objets par course | Objet le plus lourd |
| --- | --- | --- | --- | --- | --- | --- |
| 2 | soft | 100 % | 29.0 % | 2.02 | 8.3 | gel (18.1 %) |
| 2 | soft | 90 % | 0.0 % | 2.97 | 7.7 | team_car (18.2 %) |
| 2 | normal | 100 % | 32.0 % | 1.97 | 13.0 | gel (18.5 %) |
| 2 | normal | 90 % | 1.5 % | 2.88 | 11.7 | gel_x3 (20.8 %) |
| 2 | wild | 100 % | 36.0 % | 1.94 | 16.8 | gel (20.2 %) |
| 2 | wild | 90 % | 4.5 % | 2.75 | 15.0 | gel_x3 (22.4 %) |
| 4 | soft | 100 % | 22.0 % | 2.98 | 18.7 | team_car (18.6 %) |
| 4 | soft | 90 % | 0.0 % | 5.00 | 18.8 | team_car (21.9 %) |
| 4 | normal | 100 % | 20.0 % | 3.00 | 28.7 | gel_x3 (18.9 %) |
| 4 | normal | 90 % | 2.5 % | 4.68 | 28.1 | gel_x3 (17.7 %) |
| 4 | wild | 100 % | 21.5 % | 2.94 | 37.1 | gel (18.8 %) |
| 4 | wild | 90 % | 2.0 % | 4.08 | 37.8 | gel (20.0 %) |
| 11 | soft | 100 % | 7.0 % | 6.25 | 44.1 | team_car (21.4 %) |
| 11 | soft | 90 % | 0.0 % | 11.82 | 45.2 | team_car (22.9 %) |
| 11 | normal | 100 % | 10.0 % | 6.21 | 62.7 | star (19.7 %) |
| 11 | normal | 90 % | 0.0 % | 11.59 | 65.1 | star (17.9 %) |
| 11 | wild | 100 % | 8.0 % | 6.25 | 82.7 | star (20.0 %) |
| 11 | wild | 90 % | 0.0 % | 10.38 | 84.7 | star (19.4 %) |

## Part de chaque objet dans le temps gagné ou perdu

| Bots | Chaos | Niveau | gel | gel_x3 | bottle | bottle_x3 | musette | musette_x3 | homing | storm | star | bell | headwind | team_car | stealth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | soft | 100 % | 18.1 | 17.6 | 12.9 | 4.8 | 9.6 | 3.8 | 4.2 | 1.7 | 13.9 | 0.1 | 5.0 | 8.4 | 0.0 |
| 2 | soft | 90 % | 15.5 | 17.3 | 10.1 | 3.5 | 8.0 | 3.3 | 3.9 | 2.6 | 14.1 | 0.2 | 3.3 | 18.2 | 0.0 |
| 2 | normal | 100 % | 18.5 | 17.7 | 9.9 | 3.7 | 12.3 | 4.7 | 5.4 | 3.0 | 15.1 | 0.4 | 5.8 | 3.4 | 0.0 |
| 2 | normal | 90 % | 20.4 | 20.8 | 6.7 | 2.9 | 7.2 | 2.8 | 3.2 | 2.6 | 16.9 | 0.4 | 4.6 | 11.4 | 0.0 |
| 2 | wild | 100 % | 20.2 | 19.9 | 9.2 | 3.3 | 11.8 | 6.1 | 4.6 | 2.1 | 14.0 | 0.5 | 6.4 | 1.9 | 0.0 |
| 2 | wild | 90 % | 20.6 | 22.4 | 5.6 | 2.5 | 8.2 | 4.1 | 4.7 | 2.4 | 16.5 | 0.4 | 6.4 | 6.1 | 0.0 |
| 4 | soft | 100 % | 17.3 | 16.7 | 7.4 | 3.8 | 4.7 | 2.2 | 3.5 | 3.6 | 15.4 | 0.4 | 6.3 | 18.6 | 0.0 |
| 4 | soft | 90 % | 17.1 | 14.7 | 6.2 | 3.1 | 5.1 | 2.2 | 4.4 | 3.8 | 15.1 | 0.3 | 6.1 | 21.9 | 0.0 |
| 4 | normal | 100 % | 18.4 | 18.9 | 7.2 | 3.4 | 6.8 | 3.6 | 4.8 | 3.0 | 16.4 | 0.6 | 6.7 | 10.1 | 0.0 |
| 4 | normal | 90 % | 17.5 | 17.7 | 6.4 | 3.2 | 6.6 | 2.9 | 5.0 | 3.8 | 15.4 | 0.5 | 6.7 | 14.2 | 0.0 |
| 4 | wild | 100 % | 18.8 | 17.8 | 7.0 | 2.8 | 8.1 | 4.4 | 5.2 | 4.2 | 16.3 | 0.7 | 7.5 | 7.1 | 0.0 |
| 4 | wild | 90 % | 20.0 | 16.9 | 6.7 | 2.0 | 8.4 | 4.1 | 5.2 | 3.8 | 16.1 | 0.5 | 6.9 | 9.4 | 0.0 |
| 11 | soft | 100 % | 13.9 | 13.2 | 5.4 | 3.0 | 4.0 | 1.5 | 3.5 | 4.9 | 17.0 | 0.6 | 11.7 | 21.4 | 0.0 |
| 11 | soft | 90 % | 13.5 | 13.5 | 5.0 | 2.6 | 3.9 | 1.7 | 3.0 | 5.4 | 16.1 | 0.5 | 11.9 | 22.9 | 0.0 |
| 11 | normal | 100 % | 14.3 | 14.4 | 5.4 | 2.3 | 4.7 | 2.4 | 4.0 | 4.9 | 19.7 | 0.6 | 12.3 | 15.0 | 0.0 |
| 11 | normal | 90 % | 14.7 | 15.4 | 5.0 | 2.4 | 4.8 | 2.2 | 4.0 | 4.4 | 17.9 | 0.5 | 12.0 | 16.7 | 0.0 |
| 11 | wild | 100 % | 15.6 | 15.7 | 5.1 | 2.4 | 5.3 | 2.6 | 4.1 | 4.5 | 20.0 | 0.6 | 12.4 | 11.6 | 0.0 |
| 11 | wild | 90 % | 14.8 | 15.9 | 4.5 | 2.2 | 5.0 | 2.7 | 4.0 | 4.4 | 19.4 | 0.7 | 12.8 | 13.6 | 0.0 |

## Cibles

- OK : 2 bots, chaos soft, niveau 100 % : 29.0 % de victoires (part juste, cible 16.7 à 50.0 %)
- OK : 2 bots, chaos soft, niveau 100 % : objet le plus lourd gel, 18.1 % du temps gagné ou perdu (au plus 35 %)
- OK : 2 bots, chaos soft, niveau 90 % : objet le plus lourd team_car, 18.2 % du temps gagné ou perdu (au plus 35 %)
- OK : 2 bots, chaos normal, niveau 100 % : 32.0 % de victoires (part juste, cible 16.7 à 50.0 %)
- OK : 2 bots, chaos normal, niveau 100 % : objet le plus lourd gel, 18.5 % du temps gagné ou perdu (au plus 35 %)
- OK : 2 bots, chaos normal, niveau 90 % : objet le plus lourd gel_x3, 20.8 % du temps gagné ou perdu (au plus 35 %)
- OK : 2 bots, chaos wild, niveau 100 % : 36.0 % de victoires (part juste, cible 16.7 à 50.0 %)
- OK : 2 bots, chaos wild, niveau 100 % : objet le plus lourd gel, 20.2 % du temps gagné ou perdu (au plus 35 %)
- OK : 2 bots, chaos wild, niveau 90 % : objet le plus lourd gel_x3, 22.4 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos soft, niveau 100 % : 22.0 % de victoires (part juste, cible 10.0 à 30.0 %)
- OK : 4 bots, chaos soft, niveau 100 % : objet le plus lourd team_car, 18.6 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos soft, niveau 90 % : objet le plus lourd team_car, 21.9 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos normal, niveau 100 % : 20.0 % de victoires (part juste, cible 10.0 à 30.0 %)
- OK : 4 bots, chaos normal, niveau 100 % : objet le plus lourd gel_x3, 18.9 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos normal, niveau 90 % : objet le plus lourd gel_x3, 17.7 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos wild, niveau 100 % : 21.5 % de victoires (part juste, cible 10.0 à 30.0 %)
- OK : 4 bots, chaos wild, niveau 100 % : objet le plus lourd gel, 18.8 % du temps gagné ou perdu (au plus 35 %)
- OK : 4 bots, chaos wild, niveau 90 % : objet le plus lourd gel, 20.0 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos soft, niveau 100 % : 7.0 % de victoires (part juste, cible 4.2 à 12.5 %)
- OK : 11 bots, chaos soft, niveau 100 % : objet le plus lourd team_car, 21.4 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos soft, niveau 90 % : objet le plus lourd team_car, 22.9 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos normal, niveau 100 % : 10.0 % de victoires (part juste, cible 4.2 à 12.5 %)
- OK : 11 bots, chaos normal, niveau 100 % : objet le plus lourd star, 19.7 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos normal, niveau 90 % : objet le plus lourd star, 17.9 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos wild, niveau 100 % : 8.0 % de victoires (part juste, cible 4.2 à 12.5 %)
- OK : 11 bots, chaos wild, niveau 100 % : objet le plus lourd star, 20.0 % du temps gagné ou perdu (au plus 35 %)
- OK : 11 bots, chaos wild, niveau 90 % : objet le plus lourd star, 19.4 % du temps gagné ou perdu (au plus 35 %)

## Cote Elo au Grand Prix (23 novembre, CI de la chaîne GP)

Campagne `python -m openride_core.tools.elo_campagne --courses 20 --forces 0.92,1.0,1.08 --adversaires 3` (anneau de 2 km, 4 coureurs), le cycliste jouant ses objets comme un bot :

| Force | main (avant GPO1) | GPO1 |
| --- | --- | --- |
| 0,92 | 1 337 | 1 383 |
| 1,00 | 1 484 | 1 460 |
| 1,08 | 1 593 | 1 532 |

La cote suit toujours l'ordre des forces, mais deux fois moins vite : un coup coûte environ 7 s, autant que 8 % de puissance sur 2 km. C'est l'effet voulu d'objets plus forts (plus de chance en course), qui touche aussi les manches de la ligue courues au Grand Prix. Le banc demande donc 25 points au lieu de 40 au Grand Prix (`MIN_DELTA_BY_MODE`), et le test court joue 12 courses au lieu de 4.
