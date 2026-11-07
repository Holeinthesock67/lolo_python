# Étude : optimisation du rendu des biomes (5 novembre 2026)

Point de départ : la recette U18 (partie PC, étape 7bt) dépasse les budgets GPU de `perf_targets.json` en medium et en high sur tous les biomes, et en low sur la côte, les cultures, la forêt et l'alpin. Demande du propriétaire (5 novembre) : un vrai travail de recherche d'optimisation, sans trop nuire à la qualité graphique, selon les règles de l'art du métier, et tout documenter. Document de recherche détaillé, avec les sources Web : Claude Doc « Optimisation graphique d'OpenRide : techniques du métier » (hors dépôt). Recherche précédente : `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` (27 octobre, techniques T1 à T14). Historique de tous les essais graphiques et de leur impact : `docs/HISTORIQUE_ESSAIS_GRAPHIQUES.md`.

## 1. Méthode (règles de l'art)

1. **Mesurer avant de changer**, sur le matériel cible (GTX 1060, 1680×1011, Godot 4.7.2), jamais sous Xvfb.
2. **Trouver d'abord où part le temps** : une seule différence à la fois avec le préréglage, au même endroit, à la même vitesse (`engine/tests/cout_rendu.py`).
3. **Mesurer le pire cas** : le biome le plus lourd de la recette (cultures), sur un parcours tout entier dans ce biome.
4. **Classer par gain contre perte visuelle**, et commencer par ce qui ne se voit presque pas.
5. **Combiner puis remesurer** : les gains ne s'additionnent pas exactement.
6. **Trois préréglages** à chaque essai (low, medium, high), **captures validées** par le propriétaire avant toute fusion.
7. **Pas de mise à l'échelle de la résolution** (décision du 27 octobre : résolution native).

## 2. Outils

- `engine/tests/recette_u18.py` : recette U18 partie PC sans vélo, tour des six biomes, sonde découpée biome par biome, planche des captures.
- `engine/tests/cout_rendu.py` : coût de chaque effet (variantes listées par `--list`).
- `engine/scripts/render_diag.gd` : variable `OPENRIDE_RENDER_DIAG` lue une fois au démarrage, qui change un effet pour les essais (aucun réglage du joueur ; sans variable, rendu inchangé). Test : `engine/tests/unit/test_render_diag.gd`.

## 3. Mesures

### 3.1 Recette U18, tour des biomes (main 555280f, 5 novembre matin)

GPU médian par biome (budgets 6, 12 et 14 ms) : low 5,8 à 7,8 ms (60 images/s partout) ; medium 13,3 à 18,2 ms (cultures 53 images/s) ; high 17,2 à 20,4 ms (47 à 56 images/s). Seule la côte avec la mer tient les budgets. Textures 330 Mo en high (critère U18 §5.2 tenu, mais le pack de sols des biomes n'était pas installé). Montagnes du fond presque noires en medium et high.

### 3.2 Coût de chaque effet (b0a2d3c3, 5 novembre soir)

Biome cultures forcé, premier kilomètre du tour seulement : les millisecondes absolues sont plus basses que dans le bloc cultures, les écarts restent valables. Gain = GPU médian du préréglage moins celui de la variante.

| Variante | low | medium | high |
| --- | --- | --- | --- |
| Préréglage (GPU médian) | 5,61 | 13,23 | 16,30 |
| Sans anticrénelage (borne du MSAA) | — | 3,31 | 3,66 |
| Aucune ombre (borne) | 0,50 | 1,93 | 2,29 |
| MSAA 2× au lieu de 4× | — | 1,84 | 1,67 |
| Sans SSIL | — | 1,36 | 1,60 |
| Sans halo | — | 1,24 | 0,98 |
| Atlas des ombres 2048 | — | 0,96 | 0,81 |
| Moitié de l'herbe | 0,27 | 0,77 | 0,96 |
| Sans SSAO | — | 0,76 | 0,78 |
| Sans brume volumétrique | — | 0,54 | 0,58 |
| Ombres fines (2 cascades, 200 m, filtre), arbres (densité, détail, ombres) | ≤ 0,2 | 0,4 à 0,6 | 0,2 à 0,45 |
| Tri du visible (lot S1) | 0,17 | 0,37 | 0,14 |
| Brume éclairée par le ciel | — | ≈ 0 | ≈ 0 |

Constats :

- Le rendu est **limité par les pixels** (MSAA, SSIL, halo), pas par le nombre d'objets : le tri du visible et la densité des arbres ne gagnent presque rien.
- Les ombres font la moitié des primitives dessinées (1,32 million avec, 0,69 million sans, en medium) mais seulement 1,9 à 2,3 ms.
- **Montagnes sombres** : la brume volumétrique (medium et high) n'était pas éclairée par le ciel, et assombrissait tout ce qui est au-delà de sa portée. `volumetric_fog_ambient_inject = 1` corrige pour un coût nul (captures du 5 novembre).
- La variante mesurée sous le nom « msaa0_smaa » était en fait sans aucun anticrénelage (le high a `screen_aa = off`). Elle s'appelle maintenant `msaa0` ; `msaa0_smaa` met la SMAA à la place du MSAA.

## 4. Pistes retenues, par ordre (gain contre perte visuelle)

1. **Brume éclairée par le ciel** : corrige un défaut, coût nul.
2. **Réglages Godot presque sans perte** (recherche G1, G3, G5, G6) : feuillage (herbe et arbres, `tree_sway.gdshader`) en `diffuse_lambert` et `specular_disabled` ; arbres lointains sans vent ni reflets ; halo à 3 niveaux agrandi en linéaire ; filtrage anisotrope 8× en high. Variantes `feuillage_simple`, `arbres_loin_simple`, `halo_3_niveaux`, `aniso_8`, `godot_gratuits`.
3. **MSAA 2× au lieu de 4×** en medium et high : le plus gros gain mesuré pour une perte faible.
4. En high si besoin : **SSIL « low »** plutôt que coupé.
5. En low si besoin : **70 % de l'herbe** et arbres sans ombre.
6. Plus tard, en lots de développement : niveau de détail de l'herbe selon la distance, proxy d'ombre du terrain et des arbres, relevé du temps GPU par passe.

Écartées : ombres en cache (Godot ne le propose pas pour le soleil), mise à l'échelle de la résolution (décision du 27 octobre), imposteurs et occlusion par le relief (gain faible ici, le rendu est limité par les pixels).

## 5. Améliorations visuelles à faible coût (demande du 5 novembre soir)

Même méthode que pour les économies : une variante par idée, valeur 0 = rendu actuel, coût mesuré en trois qualités avec la capture, adoption seulement après validation des captures.

| Variante (`cout_rendu.py`) | Réglage de l'essai | Ce que ça ajoute | Coût attendu |
| --- | --- | --- | --- |
| `brume_ambiante` | `volumetric_fog_ambient_inject = 1` | perspective atmosphérique : le lointain bleuit au lieu de noircir | ≈ 0 (mesuré) |
| `soleil_brume` | `soleil_brume=0.3` → `fog_sun_scatter` | halo chaud du soleil dans le brouillard quand on roule face à lui | ≈ 0 (calcul par pixel déjà fait par le brouillard) |
| `terrain_macro` | `terrain_macro=0.35` → `macro_variation` (`terrain_shade.gdshaderinc`) | prés plus ou moins mûrs sur 230 à 600 m : casse la répétition vue de loin | 2 lectures de bruit par pixel d'herbe, < 0,1 ms attendu |
| `herbe_degrade` | `herbe_degrade=0.35` → `root_darken` (`tree_sway.gdshader`, herbe seule) | pied des touffes plus sombre, pointe plus claire : volume de l'herbe | une multiplication par pixel, ≈ 0 |
| `embellis` | les trois et la brume éclairée | ensemble | à mesurer |

Plus tard, en lot de développement : forêt jusqu'à l'horizon par imposteurs (lot Y5), coût à mesurer à part.

## 6. Mesures du 6 novembre (nuit, tête 2027b30)

Recette U18 complète, GPU médian par biome. M1 = réglages Godot + brume éclairée + MSAA 2× ; H1 = idem en high ; H2 = H1 + SSIL « low » ; L1 = réglages Godot + brume éclairée.

| Combinaison | GPU médian (ms) | Budget | Images/s |
| --- | --- | --- | --- |
| L1 | 5,71 (méditerranéen) à 7,92 (cultures), comme le 5 novembre | 6 | 60 partout |
| M1 | 11,50 (méditerranéen) à 16,41 (cultures), environ −1,8 ms partout | 12 | 59 à 60 |
| H1 | 15,38 (alpin) à 18,41 (cultures), −1,8 à −2,2 ms | 14 | 52 à 60 |
| H2 | encore −0,2 à −0,4 ms par rapport à H1 | 14 | 53 à 60 |

- Le gain vient presque entièrement du **MSAA 2×**. Les réglages Godot « presque gratuits » et les améliorations visuelles restent dans le bruit de mesure (±0,6 ms sur le banc tout en cultures).
- Les montagnes du fond ne sont plus noires (planche avant/après validée par le propriétaire le 6 novembre, 0 h 19).
- Retour du propriétaire : l'image est « un peu trop claire et pas assez contrastée ». Cause probable : la brume volumétrique éclairée à pleine lumière ambiante (`volumetric_fog_ambient_inject = 1`) pose un voile clair sur tout le champ. Réglage cherché avec `engine/tests/reglage_image.py` : brume éclairée à moitié, brume plus légère, contraste relevé.

Préconisations suivantes (à mesurer) : medium = M1 + atlas des ombres 2048 ; high = M1 en high + SSIL coupé + atlas 2048 ; low = 70 % de l'herbe et arbres sans ombre. Les cultures resteront au-dessus du budget : le vrai remède est un lot de développement (moins de détail d'herbe et de cultures au loin).

### 6.1 Pistes lancées le 6 novembre (gain de chacune seule, sur le socle proposé)

Accord du propriétaire (0 h 24) : lancer les six pistes et vérifier les gains un par un. `cout_rendu.py --repetitions 2` (le 6 novembre avec l'option `--socle propose`, retirée depuis que les réglages proposés sont dans les préréglages) : chaque variante ajoute un seul réglage aux préréglages proposés, deux bancs alternés par variante, médiane gardée.

1. Temps GPU de chaque passe (`passes`, option `--gpu-profile` de Godot via `sim_bench.py --gpu-profile`) : `passes.md`.
2. Occlusion ambiante plus légère : `ssao_low` (medium, high), `ssao_medium` (high).
3. Brume volumétrique à la grille du medium en high : `brume_light`.
4. Pierres et fleurs du sol sans ombre : `sans_ombres_details`. L'herbe n'a déjà pas d'ombre.
5. Niveaux de détail des maillages plus tôt : `lod_maillage_1` (high), `lod_maillage_2` (medium).
6. Lots de développement à part : niveau de détail de l'herbe au loin (lot herbe), ombres simplifiées du terrain (écartée, voir § 6.2), forêt lointaine en imposteurs.

Image : `reglage_image.py` compare au milieu de chaque biome la brume éclairée à moitié (B), le contraste relevé (C, D), sans halo (E), un étalonnage en S (F, table de couleurs 1D `adjustment_color_correction`, coût nul) et F avec les trois améliorations visuelles (G).

### 6.2 Résultats du 6 novembre

Banc tout en cultures (6 km, 60 km/h, médiane de 2 bancs), préréglages proposés : low 5,15 ms (budget 6), medium 9,96 (12), high 10,69 (14). Ce banc est plus léger que le bloc cultures du tour des biomes, qui reste la référence.

| Piste | low | medium | high |
| --- | --- | --- | --- |
| Occlusion ambiante « low » | — | −0,34 | bruit |
| Niveaux de détail des maillages plus tôt | — | −0,32 | bruit |
| Pierres et fleurs sans ombre | −0,10 | −0,13 | bruit |
| Brume à la grille du medium | — | — | bruit |
| Ciel en mode incrémental | −0,13 | −0,48 | −0,18 |
| Ciel allégé (nuages hors de la carte de rayonnement, demi-résolution, incrémental) | −0,40 | −0,39 | −0,50 |

Temps GPU par passe (`passes.md`) : la passe opaque domine (3,1 / 4,2 / 5,4 ms), puis la prépasse de profondeur (0,2 / 1,25 / 1,8 ms). Le ciel coûtait 0,8 ms à chaque image dans les trois qualités : le `Sky` de `scenes/main.tscn` était en `PROCESS_MODE_REALTIME`, carte de rayonnement recalculée à chaque image, nuages compris.

Tour des six biomes avec les préréglages proposés (GPU médian, avant le 5 novembre → après) :

| Qualité | Avant | Après | Biomes sous le budget |
| --- | --- | --- | --- |
| low (6) | 5,8 à 7,8 | 5,8 à 8,0 | 1 sur 7 |
| medium (12) | 13,3 à 18,2 | 11,0 à 15,7 | 1 sur 7, 2 de plus à moins de 0,6 ms |
| high (14) | 17,2 à 20,4 | 13,1 à 16,4 | 4 sur 7 |

Couper 30 % de l'herbe et les ombres des arbres en low ne gagne rien : le propriétaire les garde. Les cultures et la forêt restent au-dessus du budget : lots Y22 (herbe au loin) et Y5 (forêt lointaine). Le relief alpin est aussi plus lourd que les cultures (banc de la PR #724).

Ombres simplifiées du relief (lot Y22, PR #724, 6 novembre, socle proposé, 2 répétitions, cultures et alpin, trois qualités) : le relief simplifié pour les ombres (maille de 40 m) retire 35 à 45 % des primitives, mais le gain GPU va de −0,25 à +0,34 ms, dans le bruit ; le relief sans aucune ombre gagne au plus 0,3 ms ; les captures sont identiques. Les ombres du relief ne coûtent presque rien sur la GTX 1060 : piste écartée, PR fermée sans fusion (choix du propriétaire, 6 novembre). Données : `mesures/2026-11-06-ombres-relief/` (dossier partagé du projet).

Revue des autres « loupés » du même genre : le globe du menu « Monde ouvert » (SubViewport de 560 px en `UPDATE_ALWAYS`) était dessiné à chaque image pendant la sortie ; corrigé, il ne l'est plus que menu ouvert.

## 7. Décisions (6 novembre)

Captures validées par le propriétaire : medium et high (MSAA 2×, atlas 2048, high sans SSIL), low inchangé, ciel allégé. Ces réglages sont dans `quality_presets.gd`, `render_quality.gd`, `tree_sway.gdshader`, `sky_clouds.gdshader` et `scenes/main.tscn` ; les essais correspondants ont quitté `render_diag.gd`. Reste à choisir sur captures le contraste et la part de lumière du ciel dans la brume (`RenderQuality.VOLUMETRIC_AMBIENT_INJECT`, à 1 en attendant ; image jugée trop claire), avec `reglage_image.py`.

Contraste et brume (`reglage_image.py`, tour des six biomes à 75 km/h, passe du 6 novembre, captures dans `mesures/2026-11-06-optim2/image2/`) : le propriétaire retient la variante F, soit la brume éclairée à moitié (`VOLUMETRIC_AMBIENT_INJECT` = 0,5) et un étalonnage en S de force 0,35 (`LOOK["s_curve"]`, table de couleurs 1D, Forward+ seulement, comme AgX). Les variantes B, C, F et G coûtent toutes pareil à 0,1 ou 0,2 ms près (GPU médian du tour : low 6,60, medium 12,57, high 13,89 ms pour F).

Défaut vu sur ces captures : en forêt et en montagne, la route disparaissait sous l'herbe. `carve_under_route` comparait les hauteurs réelles de la tuile lointaine à la hauteur affichée de la route (relief ×2,5). En montée, loin du départ, le seuil passait donc au-dessus du terrain et rien n'était creusé : une fois le relief exagéré, le lointain dépassait la chaussée de plusieurs mètres (5,6 m au-dessus du proche sur le tour, `test_terrain_coherence`). Le lointain se voit là où la tuile proche n'est pas encore affichée. Corrigé : le seuil est en altitude réelle. Reste 1,4 m au-dessus du proche à 130 m derrière l'arrivée, sur la route prolongée où la route ne creuse plus.

## 8. Cultures et forêt encore au-dessus du budget (6 novembre soir)

Passe finale U18 (`mesures/2026-11-06-final/u18/resume.md`, main 50442813) : cultures 7,83 / 14,18 / 16,52 ms et forêt 7,27 / 12,98 / 15,94 ms en low, medium et high (budgets 6, 12 et 14) ; alpin 6,89 ms en low.

### 8.1 Le surcoût des cultures vient de ce qui est devant la caméra

- Le banc tout en cultures (6 km d'un seul biome, § 6.2) est **sous** le budget (5,15 / 9,96 / 10,69 ms), alors que le bloc cultures du tour le dépasse de 2 à 6 ms. Le contenu des cultures (vignes, herbe, éoliennes) n'explique donc pas seul l'écart.
- Relevé seconde par seconde du tour (variante F de `reglage_image.py`, 75 km/h, `mesures/2026-11-06-optim2/image2/csv/`, blocs de 2 km : cultures de 6 à 8 km, forêt de 8 à 10 km, alpin de 10 à 12 km) : le temps GPU saute vers 6,5 km, **au milieu du bloc cultures**, au moment où les tuiles du bloc forêt se chargent. Arbres chargés (colonne `trees`) et GPU médian par tranche de 500 m :

| Tranche | low : arbres, GPU | medium : arbres, GPU | high : arbres, GPU | primitives medium |
| --- | --- | --- | --- | --- |
| cultures, 6 à 6,5 km | 11 900, 6,65 ms | 31 600, 12,84 ms | 39 800, 13,73 ms | 1,62 M |
| cultures, 6,5 à 8 km | 15 400 à 16 400, 7,75 à 8,32 ms | 57 300 à 60 600, 14,67 à 15,43 ms | 71 600 à 84 900, 15,39 à 16,91 ms | 1,19 à 1,71 M |
| forêt, 8 à 10 km | 15 000 à 16 400, 7,1 à 7,5 ms | 57 000 à 60 600, 13,7 à 14,8 ms | 80 000 à 84 900, 14,1 à 16,5 ms | 1,8 à 4,7 M |
| alpin, 10 à 12 km | 3 300 à 8 900, 6,8 à 6,9 ms | 9 000 à 24 600, 12,3 à 12,7 ms | 11 100 à 39 800, 12,5 à 13,5 ms | 1,35 à 1,55 M |

- Au saut de 6,5 km, les primitives dessinées **baissent** (1,62 → 1,19 M en medium) alors que le GPU monte de 2,6 ms ; dans la forêt elle-même, les primitives triplent (4 à 6 M) sans nouvelle hausse du GPU. Hypothèse à vérifier au banc : le coût est celui des arbres de la forêt vus de loin, 0,5 à 1,5 km devant (panneaux croisés du LOD 1, et modèle proche jusqu'à 630 m environ, car la bascule à 450 m se fait par case de 250 m, distance prise au centre de la case), des milliers de petits triangles de quelques pixels, plus chers par pixel que de grandes surfaces. Le banc tout en cultures n'a presque pas d'arbres devant lui (120 arbres/ha au plus, surtout des rangs de vigne), d'où l'écart.
- Défaut de l'outil trouvé en passant : la variante `vegetation_50` de `cout_rendu.py` mettait la densité à 0,5 au lieu de la diviser par deux (préréglages 0,3 / 0,8 / 1) : en low elle ajoutait des arbres. Corrigé : `vegetation_x=F` multiplie la densité du préréglage (`render_quality.gd`), `vegetation_50` = `vegetation_x=0.5`.

### 8.2 Banc du tronçon

`cout_rendu.py lancer --troncon farmland,temperate_forest,alpine` : 2 km par biome comme le tour (même générateur `make_biome_world`), 4 km parcourus à 60 km/h (le bloc alpin ne sert qu'à ce que la caméra voit devant elle dans la forêt), sonde découpée biome par biome comme la recette U18, une capture au milieu de chaque bloc. Variantes de la première passe, une seule différence chacune :

| Variante | Question posée |
| --- | --- |
| `base`, `passes` | référence ; temps de chaque passe dans le tronçon |
| `sans_arbres` | borne : part des arbres proches dans le surcoût |
| `vegetation_50` | le coût suit-il le nombre d'arbres ? |
| `arbres_lod0_300m` | part du modèle proche entre 300 et 630 m |
| `sans_ombres_arbres` | part des ombres des arbres |
| `sans_imposteurs` | part des forêts lointaines (lot Y5, mesurées seulement sur un monde de prairie) |

13 bancs par qualité avec `--repetitions 2` (la variante `passes` une seule fois), environ 5 min chacun : environ 3 h 30 pour low, medium et high. À lancer après la fusion de l'herbe au loin (PR #721), qui change aussi les cultures.

### 8.3 Remèdes envisagés, à choisir d'après la mesure

1. **Modèle intermédiaire des arbres** de 150 ou 200 m à 450 m (houppiers à moins de facettes, même silhouette 3D) : garde la bascule vers les panneaux à 450 m demandée le 1er novembre.
2. **Panneaux du LOD 1 allégés au loin** : couronne à 4 triangles au lieu de 8 au-delà de 800 m, ou forêts en imposteurs (lot Y5) dès 1 000 m au lieu de 1 500 m.
3. **Ombres des arbres limitées aux 200 premiers mètres** (un troisième jeu d'instances « ombre seule »), si `sans_ombres_arbres` gagne plus de 0,3 ms.
4. Prépasse de profondeur (1,25 à 1,8 ms en medium et high) : Forward+ s'en sert pour l'occlusion ambiante et la lumière indirecte, on ne la coupe pas ; elle baisse avec le nombre de triangles des arbres (pistes 1 et 2).

Chaque remède : banc du tronçon en low, medium et high, captures validées par le propriétaire avant fusion. Les budgets ne bougent pas sans décision du propriétaire.

### 8.4 Résultats du banc du tronçon (nuit du 6 au 7 novembre, main sans #721)

`mesures/2026-11-07-cultures-foret/` (dossier partagé du projet), 2 répétitions, GPU médian par biome. Référence : cultures 7,80 / 13,06 / 15,89 ms, forêt 7,07 / 12,91 / 16,34 ms (low, medium, high). Le bloc alpin n'est pas couvert (banc trop court, à refaire avec environ 400 s).

| Variante (gain en ms) | cultures low / medium / high | forêt low / medium / high |
| --- | --- | --- |
| `sans_ombres_arbres` | +0,10 / −0,06 / +0,06 | +0,18 / **+1,18** / **+1,86** |
| `vegetation_50` | +0,08 / −0,18 / +0,14 | +0,10 / +0,84 / **+1,91** |
| `arbres_lod0_300m` | +0,02 / 0,00 / +0,14 | +0,04 / +0,51 / +1,25 |
| `sans_imposteurs` | +0,11 / −0,21 / −0,07 | −0,05 / +0,06 / +0,22 |
| `sans_arbres` | +0,12 / −0,37 / −0,04 | **−0,95 / −0,97** / −0,28 |

Ce que ça dit :

- **Hypothèse du § 8.1 réfutée pour les cultures** : aucune variante des arbres ni des imposteurs n'y bouge le GPU de plus que le bruit. Le surcoût des cultures vient d'ailleurs (sol, herbe, vignes : la PR #721, absente de ce banc, devait gagner 0,6 ms en high). Le saut vu vers 6,5 km sur le tour reste à expliquer ; prochaine passe avec #721 : `herbe_50`, `sans_ombres`, `sans_ombres_details`.
- **Forêt : le coût vient des ombres des arbres proches et de leur nombre**, surtout en high (ombres jusqu'à 600 m). La passe « ombres » de `passes.md` ne pèse que 0,3 / 0,6 ms : le reste du gain de `sans_ombres_arbres` est probablement la prépasse de profondeur et la passe opaque, plus légères quand l'atlas d'ombre a moins de détails (à confirmer).
- **Sans aucun arbre, la forêt coûte plus cher** (−0,95 ms en low et en medium) : les arbres cachent le sol et l'herbe derrière eux, qui coûtent plus par pixel. Réduire la densité des arbres n'est donc pas le bon levier en low.
- `arbres_lod0_300m` gagne en high (+1,25) mais rapproche la bascule vers les panneaux, refusée le 1er novembre : pas retenu.

Remède mesuré à la passe suivante : **ombre portée des arbres limitée près de la caméra** (`ombres_arbres_m=M`, variantes `ombres_arbres_100`, `_150`, `_250`). Les cases de 250 m entièrement plus loin que M ne projettent plus d'ombre (`TreeRenderer.update_shadows`, recalculé tous les 10 m), et dans les cases à cheval le shader replie l'ombre des arbres plus loin que M, seulement dans les passes d'ombre (vue d'une autre caméra que la principale, `tree_sway.gdshader`) : l'image des arbres ne change pas, seules leurs ombres lointaines disparaissent. Vérifié dans le cloud (Vulkan logiciel) : l'ombre d'un objet à 33 m disparaît avec M = 10 et reste avec M = 100, l'objet reste dessiné.

**Décision du propriétaire (7 novembre, 3 h)** : budget GPU du low relevé de 6 à 8 ms (`perf_targets.json`). Le low tient 60 images/s sur la GTX 1060 avec une marge ×2 pour une carte deux fois moins puissante ; les cultures et la forêt en low (7,1 à 7,8 ms) passent sans retirer de détail. Budgets medium (12 ms) et high (14 ms) inchangés.

### 8.5 Deuxième banc (7 novembre, avec #721, #736 et #737)

`mesures/2026-11-07-cultures-foret-b/`, tête 0fa13490, 2 répétitions. Référence plus haute qu'au § 8.4 de 0,5 à 1,3 ms (cultures 8,39 / 14,20 / 17,23, forêt 7,54 / 13,63 / 17,11), probablement l'herbe de #721 (primitives +7 à 19 %). Un téléchargement OSM a tourné sur le PC pendant 4 bancs (heures notées dans le dossier) ; leurs deux répétitions restent cohérentes.

| Variante (gain en ms) | cultures low / medium / high | forêt low / medium / high |
| --- | --- | --- |
| `sans_ombres` (borne) | +0,68 / +0,82 / +1,15 | +0,87 / **+1,95** / **+3,12** |
| `sans_ombres_arbres` | +0,19 / −0,05 / +0,02 | +0,20 / +1,31 / **+2,13** |
| `ombres_arbres_100` | +0,14 / −0,04 / 0,00 | +0,10 / +0,34 / +0,40 |
| `ombres_arbres_150` | +0,18 / +0,06 / 0,00 | +0,08 / +0,31 / +0,34 |
| `ombres_arbres_250` | +0,16 / −0,01 / 0,00 | −0,04 / +0,01 / 0,00 |
| `herbe_50` | +0,35 / +0,69 / **+1,24** | +0,25 / +0,63 / **+1,29** |

Ce que ça dit :

- La première version de `ombres_arbres_m` ne gagne qu'un sixième de `sans_ombres_arbres` : la passe d'ombre est limitée par les sommets, et replier un sommet dans le shader ne lui évite pas d'être traité. Les cases de 250 m à cheval sur la limite gardaient aussi tous leurs arbres dans la passe.
- **Correctif (a2a87ad4)** : avec `ombres_arbres_m=M`, le modèle proche des arbres ne projette plus d'ombre du tout. Un MultiMesh « ombre seule » par espèce reçoit les arbres des carrés de 25 m à moins de M de la caméra, reconstruit tous les 10 m de déplacement ; le shader fond toujours l'ombre sur les derniers mètres. Vérifié dans le cloud : ombres proches identiques, ombres au-delà de M absentes, pas de décalage.
- Les cultures répondent à l'herbe (`herbe_50`) et aux ombres en général, pas aux arbres : elles demandent un autre levier que la forêt.

Passe suivante : `mesures/2026-11-07-cultures-foret-c/` avec le correctif, plus `ombres_2_cascades` et `ombres_200m` (medium et high).

### 8.6 Bancs c et d (7 novembre) et limite par défaut

`mesures/2026-11-07-cultures-foret-c/` (a2a87ad4) et `-d/` (f0c1fe42, avec #741 : bande large d'herbe moitié moins dense).

| Variante (gain forêt en ms) | low / medium / high |
| --- | --- |
| `ombres_arbres_100` (banc c) | +0,16 / +1,05 / +1,89 |
| `ombres_arbres_150` (banc c) | +0,17 / +0,84 / +1,64 |
| `sans_ombres_arbres` (borne, banc c) | +0,20 / +1,24 / +2,29 |
| `ombres_2_cascades` seul (banc c) | — / +0,59 / +1,13 |
| `ombres_arbres_100` (banc d) | — / +1,11 / +1,72 |
| `ombres_arbres_100_2c` (banc d) | — / +1,11 / +1,94 |
| `herbe_150m` (banc d) | ≈ 0 partout |

- Le groupe « ombre seule » rend presque tout le gain de `sans_ombres_arbres`. Ajouter 2 cascades par-dessus ne gagne presque plus rien (+0,02 / +0,13) : pas retenu.
- L'herbe coûte par sa densité, pas par sa distance (`herbe_150m` ≈ 0) : #741 (bande large moitié moins dense) est le bon levier, déjà sur main.
- Les cultures ne bougent avec aucune variante d'ombre des arbres.
- **Défaut retenu (7 novembre)** : ombre des arbres limitée à 100 m (`TreeRenderer.TREE_SHADOW_M`) dans les trois qualités, aspect validé par le propriétaire sur la planche du banc c. L'essai `ombres_arbres_m=0` (variante `ombres_arbres_illimitees`) rend l'ancien comportement.
- Reste au-dessus du budget : forêt ≈ 12,8 ms en medium (12) et ≈ 15,6 ms en high (14), cultures au-dessus en medium et high.
