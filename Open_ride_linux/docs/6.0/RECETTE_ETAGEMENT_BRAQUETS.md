# Recette : étagement des 24 braquets et braquets de la piste (14 et 15 novembre 2026)

## 15 novembre : pas fixe de 0,5 point par clic

Remarques du propriétaire après ses sorties : pas assez de différence entre les braquets, braquet 1 trop dur dans certaines pentes, braquet 24 trop facile en descente. Les trois venaient de la loi multiplicative (G_eff = (G + 2) × R_k − 2) : sur le plat, un clic valait 0,16 point (≈ 5 W) ; dans un mur, le braquet 1 gardait une forte pente ; au-delà de − 2 %, un grand rapport rendait la descente encore plus descendante. Loi choisie le 15 novembre (carte de décision) :

G_eff = G_terrain × difficulté + (k − 12) × 0,5 + décalage du lieu (+ 0,5 point sur la piste, 0 ailleurs)

| | Avant (14 novembre) | Après (15 novembre) |
| --- | --- | --- |
| Réglages | `ratio_min` 0,455, `ratio_max` 2,60, `g_base_pct` 2, `[velodrome] gear_scale` 1,25 | `neutral_gear` 12, `step_pct` 0,5, `[velodrome] gear_offset_pct` 0,5 |
| Un clic sur le plat | 0,16 point (≈ 5 W à 55 tr/min) | 0,5 point (≈ 17 W) |
| Braquet 1 sur 12 %, difficulté 50 % | 2,2 % | 0,5 % |
| Braquet 24 sur − 4 %, difficulté 100 % | − 7,2 % (braquet 1 : − 2,9 %) | + 2 % (on appuie) |

Pente envoyée au trainer, difficulté 50 %, sans vent ni abri :

| Braquet | − 6 % | − 4 % | Plat | 3,6 % | 6 % | 12 % |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | − 8,5 % | − 7,5 % | − 5,5 % | 0 % | 0 % | 0,5 % |
| 6 | − 6 % | − 5 % | − 3 % | 0 % | 0 % | 3 % |
| 12 | − 3 % | − 2 % | 0 % | 1,8 % | 3 % | 6 % |
| 18 | 0 % | 1 % | 3 % | 4,8 % | 6 % | 9 % |
| 24 | 3 % | 4 % | 6 % | 7,8 % | 9 % | 12 % |

Limites connues, à juger en sortie :

- Une montée reste au moins plate (règle du 24 octobre) : dans une montée douce, les plus petits braquets donnent tous du plat (sur 3,6 % à 50 %, braquets 1 à 8).
- Avec le trainer mesuré le 28 octobre (16 N + 6,6 N par point), la résistance ne baisse plus sous − 2,4 % environ : sur le plat, les braquets 1 à 7 se sentent pareil (le plus léger possible) ; chaque clic au-dessus se sent.
- Les clés `ratio_min`, `ratio_max`, `g_base_pct` et `[velodrome] gear_scale` encore écrites dans `~/OpenRide/config.toml` sont ignorées avec un avertissement au lancement.

L'ERG, la vitesse virtuelle, les bots, le calibrage et les contacts n'utilisent pas les braquets : rien ne change pour eux. Contrat IPC inchangé (`gears_total` seul). Les séances EB et EBP ci-dessous restent valables (le propriétaire juge en sortie, sans essai dédié).

## 14 novembre

Demande du propriétaire après les essais physiques du 14 novembre : braquet 1 plus facile de 30 %, braquet 24 plus dur de 30 %, dans tous les modes ; sur la piste du vélodrome, la même gamme décalée en plus de 25 % vers le dur.

## Ce qui change

| | Avant | Après |
| --- | --- | --- |
| Rapport du braquet 1 (`[gearing] ratio_min`) | 0,65 | 0,455 (× 0,7) |
| Rapport du braquet 24 (`[gearing] ratio_max`) | 2,00 | 2,60 (× 1,3) |
| Pas par clic | 5,0 % | 7,9 % |
| Braquet 12 (départ) | 1,11 | 1,05 |
| Piste (`[velodrome] gear_scale`) | — | chaque rapport × 1,25 |

La formule ne change pas : G_eff = (G_terrain + G_base) × R_k × s − G_base, avec G_base = 2 %, s = 1 sur route et `gear_scale` sur une piste. Les bornes (−10 % / +16 %) et la règle du signe (une montée reste au moins plate) restent. L'ERG n'utilise pas les braquets. Le contrat IPC ne transmet que `gears_total` : pas de révision (reste 1.16).

Pente envoyée au trainer, difficulté 100 %, sans vent ni abri :

| Braquet | Plat avant | Plat après | 3,6 % avant | 3,6 % après | Piste après (bois compris) |
| --- | --- | --- | --- | --- | --- |
| 1 | −0,70 % | −1,09 % | 1,64 % | 0,55 % | −1,02 % |
| 12 | 0,23 % | 0,09 % | 4,23 % | 3,86 % | 0,46 % |
| 24 | 2,00 % | 3,20 % | 9,20 % | 12,56 % | 4,34 % |

Avec le modèle du trainer mesuré le 28 octobre (≈ 16 N + 6,6 N par point de pente à la roue), la résistance baisse d'environ 25 % au braquet 1 et monte d'environ 28 % au braquet 24. Point à surveiller : au braquet 1 à 50 % de difficulté, 3,6 % donne 0,27 % (0,82 % avant), proche du plat qui avait motivé la plage du 28 octobre.

## Avant de rouler

- Code de la PR sur le PC (file PC).
- `~/OpenRide/config.toml` ne doit pas fixer `ratio_min`, `ratio_max` ni `gear_scale` : sinon la valeur écrite l'emporte sur les nouveaux défauts.

## Séance EB : route plate, 10 min

Parcours plat (carré d'essai `essai-vent-carre`, vent coupé), SIM, difficulté habituelle.

1. 0–1 min : échauffement au braquet 12.
2. 1 min : descends au braquet 1 (appui long −, puis − courts). Garde la cadence.
3. 2 min 30 : remonte au braquet 12.
4. 4 min : monte au braquet 24 (appui long +, puis + courts). Garde la cadence si possible.
5. 5 min 30 : redescends clic par clic jusqu'au 12, un clic toutes les 5 s : chaque clic se sent-il ?
6. 7 min–9 min : libre, cherche ton braquet de croisière.
7. 9 min : fin.

Questions : braquet 1 assez facile et braquet 24 assez dur (note sur 5) ? Chaque clic se sent-il, sans saut brutal (oui/non) ?

## Séance EBP : vélodrome, 10 min

Accueil › Parcours › « Vélodrome 250 m » › Session libre, sans épreuve.

1. 0–1 min : braquet 12.
2. 1 min : braquet 24, 1 min. Assez dur maintenant à plat ?
3. 3 min : braquet 18, puis 12, une minute chacun.
4. 5 min : braquet 1, 30 s, puis libre.
5. 9 min : fin.

Questions : braquets de la piste justes (note sur 5) ? Trop durs, justes ou encore trop légers ?

Le journal note braquet et pente envoyée à chaque seconde (`grade_sent`) : les valeurs du tableau se vérifient après la séance.
