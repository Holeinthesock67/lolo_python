# Charte cartoon de la Course tactique (lot CT9)

Version 5.0, série CT. Cahier : `docs/lots/LOT_CT9_charte_cartoon.md`. Plan : `docs/5.0/PLAN_SERIE_CT.md` (décision 5 du 29 octobre : effets **flashy, exagérés, façon cartoon**).

Cette charte fixe les couleurs, les formes, les effets et leurs trois niveaux de qualité du mode `tactical`. Elle s'applique seulement à ce mode : le classique garde le rendu réaliste (Y16) et le Cyber-Rogue garde la charte néon (R17). CT10 (effets) et CT11 (HUD) la suivent sans exception.

**Statut : maquettes soumises au propriétaire le 29 octobre 2026 et validées telles quelles le 29 octobre 2026 à 22 h 12 (heure de Paris). CT10 peut commencer, dans l'ordre de la série.**

---

## 1. Principes

1. **Encre et aplats.** Tout objet du mode a un contour noir épais (« encre ») et un ombrage en aplats (cel shading), sans dégradé photo ni texture. Tout est procédural : maillages, shaders, particules GPU, textes en police vectorielle (invariant A9).
2. **Une couleur = un rôle, doublé par une forme.** Aucune information ne passe par la couleur seule (daltonisme) : chaque jeton du §2 a une forme attitrée (§3).
3. **Exagéré mais lisible à l'effort.** Les effets sont gros, rebondissants et bavards (onomatopées), mais jamais devant les chiffres du HUD, jamais en flash plein écran, et ils clignotent au plus à 2 Hz (§6).
4. **La qualité règle le coût, le réglage « Effets » règle l'intensité.** `low`, `medium`, `high` changent le nombre de particules, de tons et la lueur ; « Effets » (forts, normaux, discrets) change la taille, l'opacité et la présence des mots (§5 et §6).

## 2. Palette

Dix jetons d'effet, saturés, nommés : aucune couleur d'effet n'est écrite en dur ailleurs (CT10 les recopie dans `tactical_palette.gd`).

| Jeton | Valeur | Rôle |
| --- | --- | --- |
| `ink` | #15121C | Contours, texte des panneaux, ombres portées |
| `paper` | #FFF6E0 | Fond des panneaux et des bulles, traits de vitesse plein écran |
| `fresh` | #2E8BFF | W′ pleine (au-dessus de 60 %), bouclier |
| `warm` | #FF8C1A | W′ entamée (25 à 60 %), voie sélective A |
| `hot` | #FF2E3E | W′ basse (sous 25 %), bulle « ! », vitesse critique |
| `draft` | #22E0D0 | Flux de l'abri |
| `sling` | #A64DFF | Catapulte (ressort, jauge en arc, onde de l'impulsion) |
| `spark` | #FFE93D | Éclairs, étincelles, étoiles, Apex, jauge de capacités |
| `leech` | #FF4FB3 | Sangsue (aimant), voisin de derrière dans le rétro-radar |
| `smoke` | #9C97AA | Fumée de surchauffe et de Burnout |

Couleurs de décor du mode (ni jetons d'effet ni rôles de jeu) : ciel #43BFFF vers #C4F0FF, herbe #72D652, route #707490, collines #49B04F et #3C9A45, arbres #2F9E46. Maillots des bots : tons sourds (#4DAA57, #C9733A, #5C7A8A, #E8DFC8, #7A6A5A), jamais un jeton, pour qu'un effet ne se confonde pas avec un maillot. Le joueur est en blanc à bande noire.

**Encre :** épaisseur constante à l'écran, 3 px à 1050 px de haut (2 px à 600 px), 1,5 px au minimum ; contour par coque inversée (`cull_front`, normale gonflée) sur les cyclistes, les arbres proches et les objets d'effet.

**Tons :** `low` 1 ton (aplat seul), `medium` 2 tons (aplat + ombre à 22 % d'`ink`), `high` 3 tons (+ reflet blanc à 40 %), calculés dans le shader (rampe en escalier sur N·L), sans texture.

## 3. Formes : chaque couleur doublée

| Information | Couleur | Forme qui la double |
| --- | --- | --- |
| W′ pleine | `fresh` | Double contour fin, rien d'autre |
| W′ entamée | `warm` | Double contour moyen, gouttes de sueur, volutes de vapeur |
| W′ basse | `hot` | Double contour épais, fumée, ondes de chaleur, bulle « ! » |
| Burnout | `smoke` | Gros nuage, couronne d'étoiles qui tourne, ressort cassé, « PFIOU » |
| Abri | `draft` | Lignes d'air en tirets qui contournent le suiveur |
| Catapulte | `sling` | Ressort spiralé entre les deux vélos, arc au-dessus du bot (jauge C) |
| Catapulte pleine | `spark` | Éclairs autour du ressort, « PRÊT ! » |
| Impulsion | `sling` + `paper` | Anneaux au sol, traits rayonnants plein écran, « ZOOM ! » |
| Apex | `spark` + `hot` | Étoile éclatée, étincelles, « POW ! » |
| Sangsue | `leech` | Aimant en U au-dessus du bot, arcs d'attraction |
| Variante | `warm` (A) / `fresh` (B) | Flèche géante en relief qui rebondit, pastille à lettre, étiquette |
| Vitesse critique | `hot` | Panneau rond « 38 » à l'entrée du virage, panneau jaune dans le HUD |

## 4. Catalogue des effets

Coûts GPU **estimés** sur la GTX 1060 en 1680×1050, au moment le plus chargé de l'effet ; CT10 les mesure avec la sonde X13 en `low`, `medium` et `high` et remplace ces chiffres. Pour référence, le rendu classique est à environ 10,8 ms GPU en `medium` à cette définition (Y13).

| Effet | Piloté par (plan §6) | `low` | `medium` | `high` | Coût estimé (low / medium / high) |
| --- | --- | --- | --- | --- | --- |
| Encre et cel shading des cyclistes | toujours | Contour sur le joueur et les 3 bots les plus proches, 1 ton | Contour sur tous les bots à moins de 60 m, 2 tons | Contour sur tous les bots et les arbres proches, 3 tons | 0,15 / 0,30 / 0,45 ms |
| Vélo qui rougit (W′) | `tactical.wbal_pct`, `bots[].wbal_pct` | Double contour + jante et tube de selle teintés | + 2e ton sur le teint rouge | + halo transparent de la couleur (coque, pas de glow global) | 0,05 / 0,08 / 0,12 ms |
| Sueur et vapeur (`warm`) | idem | 3 gouttes, 1 volute | 5 gouttes, 2 volutes | 8 gouttes, 3 volutes | 0,02 / 0,03 / 0,05 ms |
| Fumée et chaleur (`hot`) | idem | 3 bouffées, 1 onde, bulle « ! » | 5 bouffées, 2 ondes | 8 bouffées, 4 ondes | 0,04 / 0,07 / 0,10 ms |
| Burnout | `tactical.burnout_s`, `bots[].burnout` | 3 bouffées, 3 étoiles, ressort | 5 bouffées, 4 étoiles | 8 bouffées, 5 étoiles, reflets | 0,05 / 0,08 / 0,12 ms |
| Flux de l'abri | abri reçu (`draft`) | 2 lignes par côté | 3 lignes par côté | 4 lignes par côté | 0,02 / 0,03 / 0,04 ms |
| Catapulte chargée | `tactical.sling_pct`, `bots[].sling_pct` | Ressort (tube procédural), 2 éclairs à 100 % | + reflet sur le ressort, 5 éclairs | + halo, 7 éclairs | 0,05 / 0,08 / 0,12 ms |
| Jauge en arc au-dessus du bot (choix C) | idem | Arc seul | + pourcentage | + halo | 0,01 / 0,01 / 0,02 ms |
| Impulsion | déclenchement de la catapulte | 2 anneaux, 10 traits plein écran | 3 anneaux, 18 traits | 3 anneaux, 28 traits | 0,15 / 0,20 / 0,25 ms (0,6 s seulement) |
| Apex | `tactical.corner.apex` | Étoile, 4 étincelles, 3 étincelles sous la roue | + 2e ton, 9 étincelles | + halo, 14 étincelles | 0,04 / 0,06 / 0,08 ms |
| Ligne idéale et panneau de vitesse critique | `tactical.corner` | Pointillés + panneau | idem | idem | 0,02 ms |
| Sangsue | `tactical.leech` | Aimant + 3 arcs | idem | idem | 0,01 ms |
| Flèches de variante | variantes (forme `open_world.next`) | Flèches en relief, pastilles, sans ombre | + ombre au sol, reflet | + halo de la voie choisie | 0,03 / 0,05 / 0,06 ms |
| Onomatopées (« POW ! », « ZOOM ! », « PFIOU », « PRÊT ! ») | événements | `Label3D` à contour, police du jeu | idem | idem | 0,01 ms |
| HUD cartoon (CT11) | `state`, `state.tactical` | Panneaux `paper` à contour `ink` | idem | + ombre portée des panneaux | 0,10 ms |
| **Total, pire moment** | | | | | **≈ 0,8 / 1,2 / 1,7 ms** |

Règles de coût : pas de glow ni de bloom global (les halos sont des coques transparentes), pas de lumière dynamique, une seule passe plein écran (traits de l'impulsion) et seulement pendant 0,6 s. Le garde-fou de charge de Y6 coupe d'abord les halos, puis les traits plein écran, puis la moitié des particules.

### 4.1 Durées et mouvements

| Effet | Durée | Mouvement |
| --- | --- | --- |
| Bulle « ! » (W′ basse) | tant que la W′ est sous 25 % | Clignote à **1 Hz** |
| Couronne d'étoiles du Burnout | 8 s (durée du Burnout) | Tourne à 0,5 tour par seconde (rotation, pas de clignotement) |
| Éclairs de la catapulte pleine | tant que la charge est à 100 % | Changent de place à **2 Hz** au plus |
| Impulsion | 0,6 s | Anneaux qui s'élargissent, traits qui s'éloignent, puis fondu |
| Apex « POW ! » | 0,6 s | Grossit de 60 à 100 % puis fondu, au plus une fois toutes les 30 s (plan §5) |
| Flèches de variante | de 150 m avant à la séparation | Rebond de 1,5 Hz (mouvement, pas de clignotement), la voie choisie au Click grandit |
| Fumée, vapeur, sueur | tant que l'état dure | Montent et s'effacent en 1 à 1,5 s |

## 5. Réglage « Effets »

Nouveau réglage du mode, sur l'écran de départ et dans la pause (CT11), indépendant de la qualité graphique.

| Valeur | Taille | Opacité | Onomatopées | Traits plein écran |
| --- | --- | --- | --- | --- |
| Forts (par défaut) | 100 % | 100 % | Oui | Oui, 28 % d'opacité |
| Normaux | 80 % | 85 % | Oui | Oui, 20 % |
| Discrets | 55 % | 60 % | Non (remplacées par une étoile) | Non |

Le réglage « réduire les mouvements » (O4) impose « Discrets » et coupe le rebond des flèches.

## 6. Règles de confort (non négociables, vérifiables)

1. **Clignotement au plus à 2 Hz** : bulle « ! » à 1 Hz, éclairs à 2 Hz ; aucune autre alternance. CT10 le teste sur les données de chaque effet (fréquence déclarée), comme R17.
2. **Pas de flash plein écran**, ni blanc ni rouge : aucune couleur ne couvre plus de 30 % de l'écran d'un coup.
3. **Effets plein écran sous 30 % d'opacité** : seuls les traits de l'impulsion sont plein écran, à 28 % au plus.
4. **Chaque couleur doublée par une forme** (§3).
5. **Rien devant les chiffres** : aucun effet ne passe au-dessus des panneaux du HUD ; contraste des chiffres d'au moins 7:1 (`ink` sur `paper` : 17:1).

## 7. Maquettes

Dossier du projet (hors dépôt) : `/mnt/project-files/captures/course-tactique-maquettes/`. Six scènes, chacune en 1680×1050 et 1024×600, en `low`, `medium` et `high` (36 images dans `images/`), une planche par scène et une planche du réglage « Effets ». Images fixes dessinées en SVG et rendues par Chromium (script `maquettes_ct9.js` du même dossier) : ce ne sont pas des captures de l'engine, qui n'a encore aucun code du mode.

| Scène | Ce qu'elle montre |
| --- | --- |
| 1. Peloton | Vélo de chaque coureur à sa couleur de W′, flux de l'abri derrière le bot de tête, jauge de catapulte en arc, sangsue (aimant) sur un bot qui charge dans une roue |
| 2. Attaque et Burnout | Joueur en W′ basse qui lance l'impulsion (anneaux, traits plein écran, « ZOOM ! ») ; bot en Burnout (nuage, étoiles, ressort cassé, « PFIOU ») |
| 3. Catapulte | Ressort tendu entre les deux vélos, éclairs, jauge à 100 %, « PRÊT ! » |
| 4. Virage et Apex | Panneau de vitesse critique, ligne idéale en pointillés, « POW ! » au point de corde, étincelles sous la roue du joueur penché |
| 5. Variante | Flèches géantes A (courte, raide, sélective) et B (longue, douce, le groupe reste), pastilles et étiquettes ; A choisie |
| 6. HUD complet | Puissance avec barre de W′ à 10 cases, jauge de capacités à 3 paliers (Échappée 25 %, Bouclier 50 %, Casque aéro 100 %), vitesse, pente, panneau de virage, voisins avec W′ et rétro-radar (aimant, charge de la catapulte de celui qui est derrière) |

## 8. Ce que la validation tranche

En validant les maquettes, le propriétaire valide : la palette du §2, les formes du §3, les trois niveaux du §4, le réglage « Effets » du §5 et les onomatopées en français. Toute remarque sur une scène se reporte ici avant CT10.
