# Lot Y13 – Qualité d'image par préréglage (consommer la marge du GPU)

## 1. Objectif

Demande du propriétaire du 27 octobre (19 h 33) : « augmenter la qualité graphique générale vu la marge ». Sur la GTX 1060 du PC cible, la carte graphique travaille environ 5 ms par image en `medium` sur les 16,7 ms d'une image à 60 Hz : il reste de quoi rendre l'image plus belle sans repasser sous les budgets.

Consigne du propriétaire (19 h 35) : **la résolution reste la résolution maximale de l'écran**. Ni mise à l'échelle 3D, ni suréchantillonnage, ni FSR ou résolution adaptative dans ce lot : la marge sert aux autres leviers.

Le lot procède par étapes, chacune mesurée sur le PC avant et après ; l'étape 1 est un prototype soumis à l'accord du propriétaire avant de généraliser.

## 2. État des lieux chiffré (`main` du 27 octobre, Godot 4.3, Forward+)

Mesures : banc simulé `montee_descente` avec la sonde X13 sur la GTX 1060 (essai Y1 du 27 octobre, fenêtre 1857 × 1011, synchronisation verticale à 60 Hz), médianes après les 20 premières secondes.

| Préréglage | Images/s | Temps GPU par image | Charge GPU | Appels de dessin | Primitives | Arbres |
| --- | --- | --- | --- | --- | --- | --- |
| `low` (village) | 60 | 2,8 ms | 23 % (pointe 66 %) | 430 | 1,0 M | 19 700 |
| `medium` (village) | 60 | 5,0 ms | 35 % (pointe 40 %) | 443 | 1,4 M | 49 700 |
| `medium` (OSM) | 60 | 4,7 ms | 34 % (pointe 37 %) | 444 | 1,4 M | 49 700 |

Essais en fenêtre du 27 octobre (`medium`) : 59 images/s en moyenne, p99 du temps d'image ≈ 21 ms, GPU à 28 % en moyenne et 54 % au plus fort. Le PC du propriétaire tourne bien en `medium` (`[render] quality = "medium"` dans sa configuration, vérifié le 27 octobre).

Réglages d'image avant ce lot :

| Réglage | `low` | `medium` | `high` | Où |
| --- | --- | --- | --- | --- |
| Rendu des tons | Linear (aucun) | Linear | Linear | défaut de l'`Environment` |
| Étalonnage (contraste, saturation) | aucun | aucun | aucun | — |
| Anticrénelage | aucun | MSAA 2× | MSAA 4× | `quality_presets.gd` |
| Filtrage anisotrope | 4× (défaut Godot) | 4× | 4× | `project.godot` |
| Occlusion ambiante (SSAO) | non | qualité « très basse » | qualité « très basse » | `project.godot` |
| Lumière indirecte d'écran (SSIL) | non | non | non | — |
| Glow | non | non | non | — |
| Ombres du soleil | atlas 2048, 4 cascades, filtre par défaut, 150 m | idem, 300 m | idem, 600 m | `project.godot`, `quality_presets.gd` |
| Brouillard opaque | 4 km | 6 km | 9 km (+ volumétrique) | Y1 |
| Densité de végétation, arbres | 0,3, 20 000 | 0,6, 50 000 | 1,0, 100 000 | `quality_presets.gd` |
| Bâtiments visibles jusqu'à | 1,5 km | 2,5 km | 4 km | `quality_presets.gd` |
| LOD automatique (seuil) | 1 px (défaut) | 1 px | 1 px | — |

Constat : aucun rendu des tons ni étalonnage (couleurs plates, ciel délavé), SSAO au plus bas, pas d'anticrénelage en `low`, ombres floues et peu visibles sous les arbres.

## 3. Budgets par préréglage

Mesurés à la résolution native de l'écran, en plein écran ou fenêtre maximale, avec tout le décor vivant.

| Préréglage | Images/s | p99 du temps d'image | Temps GPU médian | Enveloppe de ce lot |
| --- | --- | --- | --- | --- |
| `low` | ≥ 55 (spécification) | < 25 ms | ≤ 6 ms (4 ms jusqu'au 31/10, voir ci-dessous) | +0,5 ms au plus |
| `medium` | ≥ 58 | < 25 ms | ≤ 12 ms, Y11 et Y12 compris | +4,5 ms au plus |
| `high` | ≥ 55 | < 25 ms | ≤ 14 ms | +6 ms au plus |

Budget `low` relevé de 4 à 6 ms le 31 octobre (décision du propriétaire après l'endurance 7bi) : depuis l'herbe Y14, le `low` mesure 4,7 à 5,7 ms à 1680 × 1050 sur la GTX 1060 (5,4 ms sur l'heure de 7bi), toujours à 60 images/s ; l'herbe reste telle quelle.

Le plafond de 12 ms en `medium` garde environ 30 % de marge pour les scènes chargées (villages, pluie, foules) et laisse l'enveloppe de +2,5 ms déjà accordée à Y11 et Y12.

## 4. Plan, ordonné par gain visuel par milliseconde

Coûts estimés pour la GTX 1060 en 1080p, à confirmer au banc à chaque étape.

| Étape | Contenu | Gain visuel | Coût GPU estimé (`medium`) | Godot |
| --- | --- | --- | --- | --- |
| **1 (prototype, cette PR)** | Rendu des tons Filmic, exposition, contraste et saturation (tous préréglages) | Fort : couleurs, ciel non délavé | ≈ 0 | 4.3 |
| 1 | Ombres : atlas 4096, filtre doux par préréglage, 4 cascades en `medium` et `high` (2 en `low`) | Fort : ombres nettes sous les arbres et les bâtiments | +0,5 à 1 ms | 4.3 |
| 1 | SSAO « medium » et SSIL « low » en demi-résolution (`medium`), SSAO « high » et SSIL « medium » en demi-résolution (`high`, ramené après la mesure du §6) | Moyen à fort : pieds des arbres, coins des maisons | +1 à 1,5 ms | 4.3 |
| 1 | MSAA 4× en `medium` (2× avant), FXAA en `low` (rien avant) | Moyen : bords des arbres, lignes de route | +0,5 à 1 ms ; `low` +0,2 ms | 4.3 |
| 1 | Filtrage anisotrope 16× (tous) | Moyen : route et sol nets au loin | +0,1 à 0,3 ms | 4.3 |
| 1 | Glow léger sur les zones très claires (`medium`, `high`) | Faible à moyen | +0,3 ms | 4.3 |
| 1 | Seuil des LOD automatiques 2 / 1 / 0,5 px | Faible | ≈ 0 | 4.3 |
| 2 | Densités et distances en `medium` : végétation 0,6 → 0,8, arbres 50 000 → 70 000, ombres 300 → 400 m, bâtiments 2,5 → 3,5 km | Moyen : paysage plus plein | +1 à 2 ms ; risque sur le p99 (construction des tuiles, à mesurer) | 4.3 |
| 3 | Brume volumétrique légère en `medium` (profondeur de l'air dans les vallées) | Moyen | +1 à 2 ms | 4.3 |
| 4 | Après la migration Y2 (4.7) : tonalité AgX, glow recalé (changé en 4.6) ; SMAA en `low` par Y6, SSR de l'eau par Y12 | Moyen | à mesurer | 4.7 |

Les plus gros gains visuels restants ne sont pas des réglages mais du contenu, déjà prévus ailleurs et non dupliqués ici : toits à pans et façades (Y8), forêts jusqu'à l'horizon en imposteurs (Y5), chaussée et herbe (Y11, et le fil « Améliorer l'herbe et les personnages »), lumières et particules (Y12), animaux et véhicules (P22 à P27).

## 5. Étape 1 réalisée (prototype)

- `quality_presets.gd` : nouvelle table `IMAGE` (anticrénelage `msaa` et `fxaa`, `ssao`, `ssil`, `ao_half_size`, `glow`, `shadow_atlas`, `shadow_splits`, `shadow_filter`, `mesh_lod_threshold`) et fonction `image(name)`. Les clés `ssao` et `msaa` quittent `PRESETS` pour cette table : toute la qualité d'image est au même endroit. Les budgets du décor vivant (`LIVING`) ne changent pas.
- `render_quality.gd` : `apply_image()` applique la table ; `LOOK` (rendu des tons et étalonnage communs) et `GLOW` ; `scaling_3d_scale` forcé à 1 (résolution native).
- `project.godot` : filtrage anisotrope 16×.
- Tests : `test_quality_presets.gd` (clés, valeurs connues, qualité croissante de `low` à `high`, toujours un anticrénelage) et `test_render_quality.gd` (application sur le viewport, l'environnement et le soleil).

| Réglage | `low` | `medium` | `high` |
| --- | --- | --- | --- |
| Rendu des tons | Filmic, exposition 1,25, blanc 6, contraste 1,08, saturation 1,18 | idem | idem |
| Anticrénelage | FXAA | MSAA 4× | MSAA 4× |
| SSAO / SSIL | non / non | medium / low, demi-résolution | high / medium, demi-résolution |
| Glow | non | oui | oui |
| Ombres | atlas 2048, 2 cascades, filtre doux bas | atlas 4096, 4 cascades, filtre doux moyen | atlas 4096, 4 cascades, filtre doux haut |
| Seuil LOD | 2 px | 1 px | 0,5 px |

Le rendu des tons a été choisi sur captures parmi Linear, Reinhard, Filmic et ACES : Filmic garde un ciel bleu et des verts francs, ACES délave le ciel, Reinhard aplatit les contrastes.

**Moteur Compatibility** (Xvfb, GPU modestes) : le filtre doux des ombres y tire un bruit différent à chaque image (grain qui scintille, relevé par la vérification « image figée » de `visual_check.py`) ; sans RenderingDevice, les ombres restent dures, comme SSAO et SSIL restent coupés. En `medium` sous Compatibility, le MSAA 4× sur les touffes d'herbe qui ondulent fait dépasser le seuil de cette même vérification (le vent bouge l'image) ; les tests automatiques tournent en `low` et le rendu Forward+ de `medium` passe la vérification.

**Captures avant et après** : rendu Forward+ réel de Godot 4.3 (Vulkan logiciel lavapipe, sans carte graphique) par `visual_check.py --native` sous Xvfb, 537 vérifications sur 537 en `low`, `medium` et `high`. Les captures ne sont pas prises au même instant exact (le rendu logiciel tourne à 1 à 3 images/s) : la position diffère de quelques mètres et les touffes d'herbe, construites progressivement, sont moins nombreuses après. Les mesures de temps se font sur le PC.

## 6. Mesures à faire sur le PC (étape 1)

Deux blocs de moins de 10 minutes, PC au calme, sans séance vélo, fenêtre annoncée avant ouverture :

1. `main` puis la branche, `medium`, monde `village` : `python3 engine/tests/sim_bench.py --native --probe --quality medium --size LxH --world village --scenario montee_descente`, `LxH` étant la résolution native de l'écran (1680 × 1050 sur le PC du propriétaire), environ 3 min chacun.
2. La branche en `low` puis en `high`, même commande.

**Défaut du banc corrigé dans cette PR (28 octobre) :** `sim_bench.py` passait `--quality` à l'engine mais n'écrivait pas `[render] quality` dans la configuration du core ; le core renvoyait sa valeur par défaut (`low`) dans ses réglages au démarrage et l'engine l'appliquait (« Qualité graphique : low » dans `engine.log`), alors que la colonne `preset` de la sonde affichait le préréglage demandé. Les bancs `medium` et `high` mesuraient donc du `low` depuis l'envoi des réglages par le core (O4). Vérifier cette ligne de `engine.log` à chaque banc.

**Résultats (28 octobre, GTX 1060, Vulkan Forward+, 1680 × 1050, `village` / `montee_descente`, médianes après 20 s ; avant = `main` 80fb951, après = la branche) :**

| Banc | img/s | GPU ms médian / max | CPU ms | Charge GPU médiane / max | p99 ms | Appels de rendu | Primitives | VRAM Godot |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| avant `low` | 60 | 4,87 / 5,77 | 0,80 | 35 / 40 % | 16,7 | 429 | 803 k | 143 Mo |
| après `low` | 60 | 4,71 / 5,84 | 0,77 | 35 / 41 % | 16,7 | 410 | 498 k | 143 Mo |
| avant `medium` | 60 | 5,06 / 6,06 | 0,86 | 35 / 44 % | 16,7 | 435 | 1 047 k | 220 Mo |
| après `medium` | 60 | 8,47 / 9,90 | 0,97 | 54 / 67 % | 16,7 | 435 | 1 048 k | 370 Mo |
| après `high` (pleine résolution) | 60 | 13,43 / 15,30 | 1,03 | 83 / 100 % | 16,7 | 449 | 1 486 k | 413 Mo |

- `low` est gratuit (38 % de primitives en moins grâce au seuil LOD).
- `medium` coûte +3,4 ms de GPU et +150 Mo de VRAM : 8,5 ms pour un budget de 12 ms.
- `high` en pleine résolution dépassait son budget en pointe (15,3 ms pour 14, 18 s au-dessus de 95 % de charge) : SSAO et SSIL de `high` passent en demi-résolution, à remesurer avant la fusion.
- Les pics de 130 à 150 ms (chargement, captures) sont présents avant comme après. Aucune erreur Godot.
- **Remesure du 28 octobre** (branche à jour avec `main` 8bfb255, qui apporte l'herbe et les arbres de Y14 : +30 à 50 % de primitives) : `medium` 10,02 ms médian / 12,03 ms max, charge 65 / 81 %, 1 357 k primitives, 376 Mo ; `high` (SSAO/SSIL en demi-résolution) 13,07 / 15,52 ms, charge 82 / 99 %, 17 s au-dessus de 95 %, 2 187 k primitives, 393 Mo. 60 img/s et p99 16,7 ms pour les deux. `high` tient sa médiane ; il reste 2 ms à `medium` pour l'étape 2.
- Captures aux instants 43, 83, 123 et 163 s de chaque banc : `~/OpenRide/sim_bench/2026-10-27_Y13/captures/` sur le PC (non versionnées).

Critères : budgets du §3 ; écart d'images/s et de p99 entre `main` et la branche ; GPU médian et pointe dans `sonde.csv`. Si `medium` dépasse son enveloppe, retirer d'abord le SSIL, puis passer le MSAA à 2×.

## 7. Étapes suivantes (après l'accord du propriétaire sur l'étape 1)

Chaque étape : une branche et une PR, mesure avant et après avec le protocole du §6 (même monde, même scénario, résolution native), budgets du §3, captures avant et après jointes. Une étape qui dépasse son enveloppe est réduite (repli indiqué) ou abandonnée, jamais gardée « en option ».

### 7.1 Étape 2 : densités et distances en `medium`

Accord du propriétaire le 28 octobre (« généraliser et continuer »). Valeurs appliquées dans `quality_presets.gd`.

**Mesure du 28 octobre** (GTX 1060, 1680 × 1050, `village` / `montee_descente`, médianes entre 20 et 640 s) : `main` medium 10,38 ms de GPU (max 12,07), 1 479 k primitives ; étape 2 medium 10,58 ms (max 11,87), 1 759 k primitives (+19 %), charge 68,5 / 84 %, 60 img/s, p99 16,7 ms. Le coût est de +0,2 ms : pas besoin du repli. Le monde `osm` reste à mesurer quand un parcours boisé sera fourni au banc.

| Réglage (`quality_presets.gd`) | `medium` avant | `medium` après | `low` / `high` |
| --- | --- | --- | --- |
| `vegetation_density_factor` | 0,6 | 0,8 | inchangés (0,3 / 1,0) |
| `TREE_BUDGETS` | 50 000 | 70 000 | inchangés (20 000 / 100 000) |
| `SHADOW_DISTANCES` | 300 m | 400 m | inchangés (150 / 600 m) |
| `BUILDING_VISIBILITY_END` | 2 500 m | 3 500 m | inchangés (1 500 / 4 000 m) |

- Gain attendu : paysage plus plein, ombres des arbres plus loin, villages visibles de plus loin. Coût estimé +1 à 2 ms de GPU.
- Risque principal : le **p99**, pas la moyenne. Construire une tuile d'arbres coûte déjà 40 à 80 ms de processeur sur le PC (budgets `tree_tile_high`, `vegetation_tile_max`) ; 30 % d'arbres en plus allongent ces pics. Mesure sur `village` **et** sur un parcours OSM boisé (le monde `osm` du banc), p99 relevé tuile par tuile dans `sonde.csv`.
- Repli si le p99 dépasse 25 ms : garder les ombres à 400 m et les bâtiments à 3,5 km (coût GPU seul), laisser la végétation à 0,6 et les arbres à 50 000 jusqu'à ce que la construction étalée des tuiles (O1, S1) soit livrée.
- Ordre croissant de `low` à `high` conservé (test `test_quality_presets.gd` existant) ; seules les valeurs `medium` et les tests changent. Les clés `LIVING` (herbe, faune, véhicules) restent aux autres fils.

### 7.2 Étape 3 : brume volumétrique légère en `medium`

- La clé `fog_volumetric` quitte `PRESETS` pour `IMAGE` (même règle que `ssao` et `msaa` à l'étape 1 : toute la qualité d'image au même endroit) et devient un niveau : `off` (`low`), `light` (`medium`), `full` (`high`).
- `light` : brouillard volumétrique de Godot avec une grille réduite (`RenderingServer.environment_set_volumetric_fog_volume_size(48, 64)`, filtre actif), portée `volumetric_fog_length` 600 m, densité 0,004, anisotropie 0,6 pour que le soleil éclaire la brume vers l'avant (rayons dans les trouées des arbres), couleur de l'horizon, `volumetric_fog_sky_affect` 0 (règle de P16 : le ciel et les nuages restent visibles).
- `full` (`high`) : grille 64 × 64, portée 1 200 m, densité 0,006.
- **Constat du 28 octobre :** les densités des thèmes (0,0004 à 0,0012) ne se voyaient pas, et `high` gardait la portée par défaut de Godot (64 m) : son brouillard volumétrique ne montrait rien. Les densités du niveau sont donc des minimums ; un thème plus brumeux l'emporte. Captures du rendu logiciel : la brume adoucit les arbres et les collines au loin sans voiler la route.
- Le brouillard de profondeur d'Y1 (opaque à 4 / 6 / 9 km) ne change pas : la brume volumétrique ajoute la profondeur de l'air de près, sans rapprocher l'horizon. La brume de la météo (P17, `fog_boost`) agit sur les deux : la densité volumétrique est multipliée par `1 + 3 × fog_boost` dans `apply_weather_fog`.
- Compatibility n'a pas de brouillard volumétrique : `off` sans RenderingDevice, comme SSAO et SSIL.
- Coût estimé +1 à 1,5 ms en `medium`. Vérifications : pas de scintillement image figée en Forward+ (le volumétrique réutilise les images précédentes, `visual_check.py --native`), pas de traînée derrière les objets à 40 km/h (captures du banc en mouvement).
- Repli : grille 32 × 32 et portée 400 m ; si l'enveloppe reste dépassée, `medium` reste `off`.
- **Mesure du 28 octobre** (GTX 1060, 1680 × 1050, `village` / `montee_descente`, médianes entre 20 et 640 s) : `medium` 10,57 ms de GPU (max 12,43) contre 10,38 sur `main`, soit +0,2 ms, charge 69 / 83 % ; `high` 13,64 ms (max 15,24), charge 85 / 100 %, 27 s au-dessus de 95 %. 60 img/s et p99 16,7 ms partout. Pas de repli nécessaire ; `high` reste le préréglage des cartes plus fortes que la 1060.

### 7.3 Étape 4 : après la migration Y2 (Godot 4.7)

Réalisée pendant la recette visuelle d'Y2, qui renvoie ici. Rien de cette étape ne se fait en 4.3.

| Réglage | 4.3 (étapes 1 à 3) | 4.7 (étape 4) | Pourquoi |
| --- | --- | --- | --- |
| Rendu des tons (`LOOK`) | Filmic, exposition 1,25, blanc 6 | AgX (4.4) avec ses réglages de blanc et de contraste (4.6), exposition recalée | AgX garde mieux la couleur dans les très hautes lumières (ciel, soleil) ; choix final sur captures Filmic contre AgX, comme à l'étape 1 |
| Glow (`GLOW`) | Soft Light, intensité 0,6 | recalé : 4.6 mélange le glow avant la tonalité et passe en « Screen » par défaut | l'ancien rendu ne se retrouve pas par un simple réglage (recherche §3) |
| Anticrénelage de `low` | FXAA | SMAA 1× (4.5), **fait par Y6** | plus net que le FXAA pour un coût proche (+0,3 ms environ) |
| Filtrage anisotrope | 16× global (`project.godot`) | par préréglage 4× / 8× / 16× si 4.7 l'expose sur le viewport (**à vérifier** le jour du lot) | `low` léger sans exception |
| Occlusion spéculaire | — | automatique à partir du SSAO (4.5) | reflets plus justes dans les creux, sans réglage |
| Seuils LOD | 2 / 1 / 0,5 px | inchangés, revérifiés (LOD générés de 4.6) | — |

- Les reflets SSR de l'eau restent dans Y12 (refaits en 4.6, demi-résolution).
- Mesure : protocole du §6 sur 4.3 puis sur 4.7 avec les mêmes réglages, puis avec ceux de l'étape 4 ; budgets du §3.

**Réalisation (29 octobre, Godot 4.7.2, après Y2 #557) :**

- Rendu des tons : **AgX** (`tonemap_agx_white` 16,29 et `tonemap_agx_contrast` 1,25, valeurs du moteur), exposition 1,25, contraste 1,08 et saturation 1,18 gardés. Captures Forward+ dans le cloud (`visual_check.py --native`, 1280×720) Filmic contre AgX : ciel plus bleu et moins délavé vers l'horizon (moyenne du haut de l'image +20 sur 255 environ), herbe et route presque inchangées (±5).
- Filtrage anisotrope par préréglage sur le viewport : 4× en `low`, 8× en `medium`, 16× en `high` (clé `anisotropy` d'`IMAGE`) ; le réglage global de `project.godot` reste la valeur de départ avant l'application du préréglage.
- Moteur Compatibility (tests sous Xvfb seulement, le jeu tourne en Forward+ dans les trois préréglages) : Filmic gardé, faute de tampon HDR AgX y blanchissait le ciel et l'herbe et effaçait les nuages (tests graphiques « ciel » et « nuages » en échec).
- Glow inchangé (Soft Light, intensité 0,6) : aucun écart visible en 4.7 sur les captures, `low` sans glow décalant autant que `medium`.
- SMAA de `low` : lot Y6. Occlusion spéculaire : automatique depuis 4.5.
- Reste : banc sur le PC cible (budgets du §3) et choix du propriétaire sur les captures.

## 8. Fichiers concernés

- **Modifiés (étape 1) :** `engine/scripts/quality_presets.gd`, `render_quality.gd`, `engine/project.godot`, `engine/tests/unit/test_quality_presets.gd`, `test_render_quality.gd`, ce cahier, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`, `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md`.
- **Étapes 2 à 4 :** les mêmes fichiers (`quality_presets.gd`, `render_quality.gd`, leurs tests) ; la brume de la météo de l'étape 3 passe par `RenderQuality.apply_weather_fog`, déjà appelée par `living_decor.gd`, sans toucher ce dernier.
- **Hors lot :** les clés `LIVING` (décor vivant, fils P22 à P27 et herbe), `crowd_renderer.gd`, `grass_tufts.gd`, `fauna_*.gd`, `traffic_*.gd`, les shaders de la route et du terrain (Y11), les menus.

## 9. Liens avec les autres lots de la série Y

- **Y4 (ombres)** garde le côté coût : objets sans ombres, distances. La qualité des ombres (atlas, filtre, cascades) est ici.
- **Y6** (réécrit le 28 octobre : SMAA en `low` et garde-fou de charge, sans baisse de résolution) : Y13 pose le FXAA de `low` en 4.3 ; Y6 le remplace par le SMAA après Y2. La mise à l'échelle 3D et la résolution adaptative restent exclues (consigne du 27 octobre).
- **Y8** : l'étalonnage passe ici (étape 1) ; Y8 garde les toits et les façades.
- **Y2** : la migration renvoie à l'étape 4 (§7.3) pour la tonalité AgX et le glow (changé en 4.6), le SMAA étant dans Y6 ; elle se fait pendant la recette visuelle d'Y2, avec les mêmes mesures.

## 10. Modifications de contrat autorisées

Aucune : ni IPC, ni format `.world`, ni thème, ni configuration (`[render] quality` reste le seul choix du joueur).
