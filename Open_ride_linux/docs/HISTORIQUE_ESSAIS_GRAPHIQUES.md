# Historique des essais graphiques et de leur impact (27 octobre → 7 novembre 2026)

Demande du propriétaire (7 novembre) : documenter tous les essais graphiques réalisés et l'impact des réglages essayés. Ce document rassemble, sans rien remesurer, ce que disent les cahiers des lots, les études, les résultats des bancs déposés dans le dossier partagé du projet (`mesures/`, `plans/FILE_MESURES_PC.md`) et les PR fusionnées ou fermées. Quand une valeur n'a pas été retrouvée dans ces sources, c'est écrit « non retrouvé » : rien n'est extrapolé.

Documents liés : [RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md](RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md) (recherche du 27 octobre, techniques et série Y), [ETUDE_OPTIMISATION_RENDU_2026-11-05.md](ETUDE_OPTIMISATION_RENDU_2026-11-05.md) (étude d'optimisation des 5 et 6 novembre, détail des variantes), [ETUDE_RENDU_INVISIBLE.md](ETUDE_RENDU_INVISIBLE.md) (lot S1), cahiers `docs/lots/LOT_Y*.md`, `LOT_S1_rendu_invisible.md`, `LOT_U18_recette_biomes.md`.

## 0. Conventions de lecture

- **Matériel** : PC cible, GTX 1060 (Pascal), Linux, Vulkan Forward+. Godot 4.3 jusqu'au 30 octobre, **4.7.2** ensuite (lot Y2).
- **Résolution** : native, 1680 × 1050 jusqu'au 30 octobre puis 1680 × 1011 (fenêtre du banc). Quelques bancs anciens sont en 1280 × 720 ou 1857 × 1011 : c'est signalé, ils ne se comparent pas aux autres.
- **Budgets GPU** (médiane du temps GPU de la vue, `perf_targets.json`) : **low 6 ms** (4 ms jusqu'au 31 octobre, **8 ms depuis le 7 novembre**), **medium 12 ms** (**13 ms depuis le 8 novembre**), **high 14 ms** (**16 ms depuis le 8 novembre**). À 60 Hz une image dure 16,7 ms. Les verdicts « au-dessus du budget » de ce document en low sont lus contre le budget en vigueur le jour de l'essai (6 ms du 31 octobre au 6 novembre).
- **Historique du budget low** : 4 ms (Y13, 27 octobre) → 6 ms (31 octobre, le low mesurait 4,7 à 5,7 ms depuis l'herbe Y14, toujours à 60 images/s ; herbe gardée telle quelle) → **8 ms** (7 novembre, décision du propriétaire, appliquée sur la branche de #732) : 6 ms était trop strict, et 8 ms laisse encore de la marge sous les 16,7 ms d'une image pour une carte plus faible que la GTX 1060. **Medium 12 → 13 ms et high 14 → 16 ms le 8 novembre** (décision du propriétaire, #732) : avec la limite d'ombre des arbres à 100 m, la forêt restait à 12,3 ms en medium et 15,3 ms en high, les cultures à 13,9 et 16,7 ms, et les leviers des arbres et de l'herbe étaient épuisés ; les essais suivants (effets d'écran) sont reportés en 5.0 (§ 5).
- **GPU** = temps GPU médian de la vue, en ms. **p99** = 99e centile du **temps d'image** (pas du GPU) ; il vaut 16,7 ms tant que le jeu tient 60 images/s (synchronisation verticale). Le p99 du temps GPU n'a été relevé que sur quelques bancs (Y21, Y6) : ailleurs, « non relevé ».
- **Gain** = GPU de la référence moins GPU de la variante (positif : la variante coûte moins). Écart de ±0,2 ms en dessous du bruit d'un banc de 2 min ; ±0,6 ms sur le banc tout en cultures (étude du 5 novembre §6).
- **Verdict** : adopté (dans les préréglages ou le code de `main`), rejeté (PR fermée ou réglage abandonné), livré coupé (code présent, désactivé par défaut), en cours.
- **Captures** : chaque essai visuel a ses captures low / medium / high validées par le propriétaire avant fusion (règle du 28 octobre). Les chemins sont relatifs au dossier partagé du projet, sauf mention « PC » (`~/OpenRide/...`, non versionné).

## 1. Pièges de mesure rencontrés (à connaître avant de relire les chiffres)

| Date | Piège | Effet sur les mesures | Correction |
| --- | --- | --- | --- |
| 28/10 | `sim_bench.py` passait `--quality` à l'engine sans écrire `[render] quality` dans la configuration du core | **Tous les bancs medium et high faits avec `sim_bench` depuis O4 mesuraient en réalité du low** | #446 (90813b3) ; vérifier la ligne du préréglage dans `engine.log` à chaque banc |
| 28/10 | Bancs d'autres fils en 1280 × 720 (≈ 5 ms en medium) | Non comparables aux bancs à 1680 × 1050 | Bancs en résolution native (`--native`) |
| 28/10 | Captures du banc toutes les 20 s | Saccades de ≈ 140 ms et p99 de 142–144 ms dus aux captures, pas au jeu (S1) | Lecture des à-coups hors captures (`hitch_checks`) |
| 28/10 | Un `Shader.new()` par essence d'arbre (Y8 étape 2, #516) | medium 58 → 7,5 images/s, GPU 8 → 31,6 ms (compilations de pipelines en double) | 824f6c9 : un seul shader partagé ; règle : jamais un `Shader.new()` par matériau |
| 30/10 | Godot remet `fog_density` à zéro quand `fog_mode` change (Rogue en high délavé) | Brume à 1,0/m en high dans le Cyber-Rogue | #604 : poser `fog_mode` **avant** `fog_density` |
| 30/10 | Dérivées (`texture()`, `fwidth`, `dFdx`) dans des branches non uniformes du shader du sol | Points sombres sur NVIDIA, invisibles sous llvmpipe (cloud) | #581 (`textureGrad`), règle shader |
| 01/11 | 18,1 / 13,1 ms annoncés pour le high de main | C'étaient des p99, la médiane GPU était 11,1 ms | Relire la colonne avant de conclure |
| 03/11 | Essais du cloud en Compatibility (OpenGL), jeu en Forward+ (Vulkan) | Couleurs et ombres différentes entre essais et jeu | #706 : essais en Forward+ (`rendu_jeu.py`, Vulkan logiciel) ; règle des couleurs sRGB |
| 05/11 | Variante appelée « msaa0_smaa » | Était en fait sans aucun anticrénelage (le high a `screen_aa = off`) | Renommée `msaa0` ; `msaa0_smaa` met vraiment la SMAA |
| 06/11 | Banc de forêt au ras du sol (6 m) | Les arbres proches cachent l'horizon : forêts lointaines invisibles, coût non mesurable | Option `--camera-height` (caméra haute 120 m) |
| 06/11 | Banc « tout en cultures » plus léger que le bloc cultures du tour des biomes | Chiffres absolus plus bas (≈ 10 ms en medium au lieu de 14–16) ; les écarts restent valables | Le tour des biomes (`recette_u18.py`) reste la référence |
| 06–07/11 | Indexeur de fichiers GNOME (localsearch) actif pendant les bancs | Charge parasite sur le PC | Exclure `~/OpenRide` et le dépôt de l'indexation |

## 2. Chronologie des essais

Pour chaque essai : référence → essai, en ms de GPU médian (low / medium / high), puis verdict.

### 2.1 Fin octobre : poser la qualité d'image (Godot 4.3)

**Y1 – Brouillard et distance par préréglage (27/10, PR #381).** Brouillard opaque à 4 / 6 / 9 km au lieu de 12 km pour tous, `camera.far` suivant le brouillard, tuiles lointaines jusqu'au brouillard + 5 km. Banc au calme : aucun gain ni perte mesurable (60 images/s plafonnées, monde d'essai à 12 tuiles lointaines seulement). Référence de l'époque : medium ≈ 5 ms, low ≈ 2,8 ms (1857 × 1011). Horizon validé par le propriétaire en medium sur `essai-horizon`. **Adopté.**

**Y11 + Y14 – Route et herbe procédurales, touffes en brins, personnages articulés (27–28/10, PR #445).** Grain, rapiéçages et bandes de roulement de la chaussée, relief et plaques de l'herbe, vagues de vent, touffes de 12 brins (budgets 1 500 / 8 000 / 20 000), fondu de l'herbe de 30 à 150 m, corps articulés de 580 triangles. Fusionné **sans mesure préalable** (choix du propriétaire, 28/10 02:11). Mesure après coup sur main (be3765f, 25a83a1) : low 57,7 images/s, p99 21,2 ms, GPU 4,5 ms, 754 k primitives ; medium 57,6 images/s, p99 22,8 ms, GPU 5,0 ms, 1,15 M primitives ; high 57,5 images/s, p99 21,9 ms, GPU 9,24 ms, 1,79 M primitives. Résolution de ce banc : non retrouvée. Le tableau de résultats du protocole `docs/ESSAI_RENDU_Y11_Y12.md` §6 n'a jamais été rempli ; les effets de Y12 (lumière, particules) n'ont pas été mesurés : non retrouvé. **Adopté.**

**Y13 étape 1 – Qualité d'image par préréglage (28/10, PR #446).** Ombres atlas 4096, filtre doux, 4 cascades en medium / high ; SSAO medium + SSIL low en demi-résolution (medium), SSAO high + SSIL medium (high) ; MSAA 4× en medium, FXAA en low ; anisotrope 16× ; halo léger ; rendu des tons Filmic (choisi sur captures contre Linear, Reinhard et ACES). Banc 1680 × 1050, `village` / `montee_descente` :

| Banc | GPU médian / max | p99 image | Primitives | VRAM |
| --- | --- | --- | --- | --- |
| main low | 4,87 / 5,77 | 16,7 | 803 k | 143 Mo |
| Y13 low | 4,71 / 5,84 | 16,7 | 498 k (seuil LOD) | 143 Mo |
| main medium | 5,06 / 6,06 | 16,7 | 1 047 k | 220 Mo |
| Y13 medium | 8,47 / 9,90 | 16,7 | 1 048 k | 370 Mo |
| Y13 high (pleine résolution) | 13,43 / 15,30 | 16,7 | 1 486 k | 413 Mo |

low gratuit ; medium +3,4 ms et +150 Mo ; high en pointe au-dessus du budget, d'où SSAO / SSIL de high passés en demi-résolution. Remesure avec l'herbe Y14 (8bfb255) : medium 10,02 / 12,03 ms, high 13,07 / 15,52 ms. Captures : `qualite-graphique/pc_gtx1060/`, `pc_gtx1060_remesure/`. **Adopté.**

**Y13 étape 2 – Densités et distances en medium (28/10, PR #484).** Végétation 0,6 → 0,8, arbres 50 000 → 70 000, ombres 300 → 400 m, bâtiments 2,5 → 3,5 km. medium 10,38 → 10,58 ms (+0,2), primitives +19 %. **Adopté.**

**Y13 étape 3 – Brume volumétrique légère en medium (28/10, PR #491).** Niveaux off / light / full ; constat : la brume du high était invisible (portée par défaut de Godot 64 m). medium 10,38 → 10,57 ms (+0,2) ; high 13,64 ms (max 15,24). **Adopté.**

**S1a – Ne calculer que le visible (28/10, PR #465).** Tuiles proches et arbres hors du champ écartés. Village : 60 images/s des deux côtés, GPU 4,7 / 5,1 ms (sans tri / avec, préréglage non précisé dans la source), arbres medium 49,7 k → 40,6 k. `essai-69` low : 58,0 → 58,4 images/s, GPU 4,58 → 4,47 ms, captures identiques. Sous le seuil de la série (3 % d'images/s ou 1 ms de p99). Remesuré le 5/11 (variante `tri_visible`) : gain 0,17 / 0,37 / 0,14 ms. **Livré coupé par défaut** (`--culling=on`) ; S1b et S1c non lancés.

**Y8 – Toits, façades, arbres, éoliennes (28/10, PR #470, #516, #533).** Façades (1280 × 720) : low 4,7 → 4,4 ms, medium 5,25 → 5,17 ms (bruit). Arbres (#516) : après correction du piège du shader, medium 8,08 → 8,61 ms (+0,5) ; faux relief des arbres retiré. Éoliennes (#533) : 8,08 → 8,09 ms. **Adopté.**

**Y16 – Avatar détaillé (28/10, PR #538).** medium, village, vue de suivi proche : GPU 8,43 → 8,33 ms, p99 19,1 → 18,1 ms. **Adopté.**

### 2.2 Godot 4.7, AgX, SMAA, garde-fou (29–31 octobre)

**Y2 – Migration Godot 4.3 → 4.7.2 (30/10, PR #557)** et **Y13 étape 4 – AgX et anisotrope par préréglage (PR #559).** Rendu des tons AgX (choisi par le propriétaire le 29/10 sur captures Filmic / AgX : ciel plus bleu, moins délavé), anisotrope 4× / 8× / 16×. GPU 4.3 → 4.7.2 : low 4,81 → 5,01, medium 11,30 → 11,25, high 14,02 → 13,54 ms ; #559 en high 13,61 ms ; appels de dessin ÷ 2,7. Halo inchangé. Captures `qualite-graphique/y2_godot47/`, `y13_etape4_agx/`. **Adopté.**

**Y17 – Parallaxe du gravier de la route en high (30/10, PR #603).** 720p : 5,14 / 7,72 / 11,98 ms. Natif 1680 × 1011, parallaxe sur toute la route : 4,99 / 11,47 / **18,79** ms (+5,2 ms, 49 images/s). Limitée à 6 m : 5,09 / 11,38 / **17,45** ms (+3,8 ms, 53 images/s), effet visible à 2–3 m seulement. **Rejeté** par le propriétaire (PR fermée), plutôt qu'un préréglage « ultra ».

**Y6 étape 1 – SMAA en low (30/10, PR #608).** FXAA → SMAA 1× : low 4,89 → 4,92, medium 11,71 → 11,67, high 13,92 → 13,92 ms ; panneaux et fenêtres plus nets. Critère ≤ +0,3 ms tenu. **Adopté.**

**Y6 étape 2 – Garde-fou de charge (30/10, PR #612).** Coupe SSIL, puis SSAO, puis halo, puis MSAA 2× quand la moyenne sur 3 s dépasse 13 ms ; retour quand moyenne + coût mesuré < 12,5 ms pendant 10 s. Essai 7bd (village) :

| Passage | GPU médian | p99 GPU | Coupes |
| --- | --- | --- | --- |
| low, garde-fou actif | 5,68 | 6,32 | aucune |
| medium, sans garde-fou | 13,69 | 15,42 | – |
| medium, garde-fou actif | 11,85 | 15,86 | SSIL puis SSAO (≈ 2 ms), SSAO non rendu faute de marge |
| high, garde-fou actif | 12,10 | non retrouvé | 4 coupes, MSAA et halo rendus |

Aucune oscillation ni à-coup vu. Endurance 7bx (01/11, garde-fou actif) : medium 8,8, high 10,7 ms. **Adopté** (réglage `[render] load_guard`).

**Y18 – Bots dessinés comme l'avatar (31/10, PR #668).** GPU branche / main : low 4,59 / 4,73, medium 8,20 / 8,32, high 9,91 / 10,10 ms. Construction des niveaux de détail déplacée hors du fil principal (pic de 39,5 ms). **Adopté.**

**P20 – Textures CC0 du décor (31/10, PR #621).** Banc 7bn : low 4,6 ms (au-dessus de l'ancien budget de 4 ms), medium 8,1, high 10,0. Le propriétaire a relevé le budget low de 4 à 6 ms le même jour (le low mesurait 4,7 à 5,7 ms depuis l'herbe Y14). **Adopté.**

### 2.3 Début novembre : détail des arbres, harmonisation, démo (1er–5 novembre)

**Bascule des arbres détaillés de 300 à 450 m (01/11, PR #689).** Demande du propriétaire (« éloigner la distance de LOD des arbres »). GPU low 5,2 / medium 9,4 / high 11,5 ms contre main 5,3 / 9,0 / 11,1–11,9, 60 images/s partout ; captures validées (« Ok 689 »). **Adopté** : c'est pourquoi la variante « arbres détaillés jusqu'à 300 m » n'est plus retenue ensuite, même quand elle gagne.

**Endurance high (01/11, 7bw, 1 h sur main 536ab6ee).** 60 images/s, saccades 2,2 / h, mais GPU médian 15,3 ms pour 14 (identique au 30/10). Constat qui a lancé le travail d'allègement du high.

**Série AS – abri, cyclistes et véhicules (02/11, banc 7cs, PR #649).** Monde ouvert 1680 × 1011 : 5,05 → 5,06 / 11,27 → 11,32 / 13,51 → 13,55 ms. Coût de la circulation AS6 avec véhicules à l'écran : non mesuré (aucun véhicule aux instants relevés ; le 15,5 ms du 31/10 était à 1857 × 1011, non comparable). **Adopté.**

**Rendu des essais = rendu du jeu (03/11, PR #706).** Essais du cloud en Forward+ et couleurs sRGB converties une fois. PC (5fea8a8e contre main) : 5,18 / 5,22, 12,25 / 12,13, 14,43 / 14,40 ms : aucun écart. Planches `captures/r706-rendu-harmonise/` (PC). **Adopté.**

**Saccades tous les 40 m sur la démo sans terrain (04/11, PR #710)** et **route qui lévite (PR #708).** À-coups et terrain, pas de coût GPU nouveau. Constat du banc : la démo compilée était déjà au bord du budget sur main, medium 12,0–12,1 / 12, high 14,2 / 14 ms. Garde-fou `hitches` ajouté à `perf_targets.json`. **Adopté.**

**2.0.1 – GPU de la démo compilée (05/11, PR #717).** Variantes `OPENRIDE_RENDER_DIAG` sur la démo, medium / high :

| Variante | medium | high |
| --- | --- | --- |
| Référence | 12,64 | 14,61 |
| V1 : filtre des ombres un cran plus bas | 11,77 | 13,95 |
| V2 : anisotrope ÷ 2 | 11,83 | 14,30 |
| V3 : SSIL un cran plus bas | 10,71 | 13,95 |

Rien de visible. Retenu V1 + V3 (medium : filtre low et SSIL coupé ; high : filtre medium et SSIL low). Contrôle : 5,12 / 10,59 / 13,69 ms. Planche validée le 05/11. **Adopté** (le high a ensuite perdu le SSIL, voir 2.4).

**Y21 – Personnages du bord de route (05/11, PR #715).** Montée du village, foule pleine, GPU médian / p99 GPU : low 5,29 / 5,98 (main 5,30 / 5,89), medium 9,82 / 11,02 (9,32 / 10,88), high 12,46 / 14,06 (11,63 / 13,62). À-coups de 51–58 ms en high corrigés (tri natif, une écriture de tampon, préchauffage) ; 2e banc high 12,42 / 13,92. **Adopté.**

### 2.4 Étude d'optimisation des biomes (5–6 novembre)

Point de départ : **recette U18, tour des six biomes (05/11, main 555280f)**. Hors côte avec la mer, tous les biomes dépassent en medium et high, et quatre en low. Montagnes du fond presque noires.

| Biome | low | medium | high |
| --- | --- | --- | --- |
| Côte | 6,29 | 14,34 | 18,60 |
| Méditerranéen | 5,77 | 13,27 | 17,57 |
| Prairie tempérée | 5,96 | 14,95 | 17,80 |
| **Cultures** | **7,84** | **18,24** (53 i/s, p99 20,0) | **20,44** (47 i/s, p99 24,9) |
| **Forêt tempérée** | **7,28** | **16,86** (p99 22,2) | **19,38** |
| Alpin | 6,75 | 14,92 | 17,16 |
| Frontières | 6,46 | 15,30 | 17,95 |
| Côte avec la mer | 4,73 | 11,44 | 13,92 |

**Coût de chaque effet (05/11 soir, b0a2d3c3, `cout_rendu.py`, premier kilomètre en cultures).** Référence 5,61 / 13,23 / 16,30 ms ; gain de la variante seule :

| Variante | low | medium | high |
| --- | --- | --- | --- |
| Sans anticrénelage (borne du MSAA) | — | 3,31 | 3,66 |
| Aucune ombre (borne) | 0,50 | 1,93 | 2,29 |
| MSAA 2× au lieu de 4× | — | 1,84 | 1,67 |
| Sans SSIL | — | 1,36 | 1,60 |
| Sans halo | — | 1,24 | 0,98 |
| Atlas des ombres 2048 | — | 0,96 | 0,81 |
| Moitié de l'herbe | 0,27 | 0,77 | 0,96 |
| Sans SSAO | — | 0,76 | 0,78 |
| Filtre des ombres « low » | — | 0,58 | 0,44 |
| Sans brume volumétrique | — | 0,54 | 0,58 |
| SSAO « low » | — | 0,52 | 0,28 |
| Arbres sans ombre | 0,18 | 0,46 | 0,45 |
| Arbres détaillés jusqu'à 300 m | 0,12 | 0,44 | 0,39 |
| Moitié des arbres | 0,13 | 0,43 | 0,07 |
| 2 cascades d'ombre au lieu de 4 | — | 0,41 | 0,30 |
| Ombres jusqu'à 200 m | — | 0,41 | 0,22 |
| Tri du visible (S1) | 0,17 | 0,37 | 0,14 |
| Brume éclairée par le ciel | — | 0,28 | 0,04 |

Le p99 du temps d'image reste à 16,7 ms pour presque toutes les variantes (17,05 en high de référence). Données : `mesures/2026-11-05-cout-rendu/cout.md`, planche `planche_high_variantes.jpg`.

**Réglages Godot « presque gratuits » et embellissements (06/11, `mesures/2026-11-06-optim/cout_godot/`).** Feuillage en Lambert sans reflets (G1), arbres lointains sans vent (G3), anisotrope 8× en high (G5), halo à 3 niveaux (G6), ajouts visuels (halo du soleil dans la brume, prés plus ou moins mûrs, dégradé des touffes). Tous dans le bruit, de −0,7 à +0,45 ms selon la variante et le préréglage (seul le halo à 3 niveaux gagne 0,45 ms en medium). Gardés pour l'aspect ou le principe (feuillage sans reflets, arbres lointains sans vent, halo 3 niveaux, anisotrope 8× en high), pas pour le gain.

**Combinaisons sur le tour des biomes (nuit du 6/11, 2027b30).** L1 = réglages Godot + brume éclairée ; M1 / H1 = idem + MSAA 2× ; H2 = H1 + SSIL low.

| Combinaison | Plage GPU (biome le plus léger → cultures) | Écart |
| --- | --- | --- |
| L1 | 5,71 → 7,92 | inchangé |
| M1 | 11,50 → 16,41 | ≈ −1,8 ms partout |
| H1 | 15,38 → 18,41 | −1,8 à −2,2 ms |
| H2 | 15,01 → 18,19 | −0,2 à −0,4 ms de plus |

Le gain vient presque entièrement du MSAA 2×. Captures : `mesures/2026-11-06-optim/planche_avant_apres_*.jpg`.

**Pistes du 6/11, une par une (banc tout en cultures, 2 répétitions, `mesures/2026-11-06-optim2/pistes/`).** Référence proposée 5,15 / 9,96 / 10,69 ms.

| Piste | low | medium | high | Verdict |
| --- | --- | --- | --- | --- |
| SSAO « low » | — | −0,34 | +0,07 (bruit) | rejetée (bruit) |
| Niveaux de détail des maillages plus tôt | — | −0,32 | +0,53 (bruit) | rejetée |
| Pierres et fleurs sans ombre | −0,10 | −0,13 | +0,41 (bruit) | rejetée |
| Brume à la grille du medium en high | — | — | +0,57 (bruit) | rejetée |
| Ciel en mode incrémental | −0,13 | −0,48 | −0,18 | adoptée |
| Ciel allégé (nuages hors rayonnement, demi-résolution, incrémental) | −0,40 | −0,39 | −0,50 | adoptée |
| Carte de rayonnement du ciel en 128 | +0,04 | −0,20 | +0,06 | rejetée (bruit) |

Découverte : le `Sky` de `scenes/main.tscn` était en `PROCESS_MODE_REALTIME` (carte de rayonnement recalculée à chaque image, ≈ 0,8 ms dans les trois préréglages). Temps GPU par passe : la passe opaque domine (3,1 / 4,2 / 5,4 ms), puis la prépasse de profondeur (0,2 / 1,25 / 1,8 ms). Autre « loupé » corrigé : le globe du menu Monde ouvert (SubViewport 560 px) était dessiné à chaque image hors menu.

**Allègement du low (06/11).** 70 % de l'herbe et arbres sans ombre : aucun gain mesuré (chiffres exacts non retrouvés ; commit e94270b1). **Rejeté** : le propriétaire garde l'herbe pleine et les ombres des arbres en low.

**Ombres simplifiées du relief (06/11, PR #724).** Relief d'ombre en maille de 40 m (1 450 triangles au lieu de 21 600). Primitives −35 à −45 %, mais GPU −0,25 à +0,34 ms ; relief sans aucune ombre : au plus 0,3 ms ; captures identiques, cultures et alpin. **Rejeté** (PR fermée) : la passe d'ombre de la GTX 1060 n'est pas limitée par les triangles. Données : `mesures/2026-11-06-ombres-relief/`.

**Image : contraste et brume (06/11, `reglage_image.py`, `mesures/2026-11-06-optim2/image2/`).** La brume éclairée à pleine lumière ambiante rendait l'image « trop claire, pas assez contrastée ». Variantes : B brume éclairée à moitié, C / D contraste relevé, E sans halo, F = brume à 0,5 + courbe en S 0,35, G = F + embellissements. Coût identique à 0,1–0,2 ms près ; F sur le tour : low 6,60, medium 12,57, high 13,89 ms (seconde valeur du relevé 8,51 / 16,19 / 17,51 ms, probablement le p99 GPU, non confirmé). **F adoptée** (choix du propriétaire, 06/11 13 h 30). Défaut trouvé sur ces captures : route cachée par le terrain lointain en montée (`carve_under_route`), corrigé.

**Passe finale de la PR #729 (06/11, aec82922, `mesures/2026-11-06-final/`).** Préréglages adoptés : medium et high en MSAA 2×, atlas 2048, high sans SSIL et anisotrope 8×, low inchangé, ciel allégé, image F.

| Biome | low | medium | high |
| --- | --- | --- | --- |
| Côte | 5,89 | 10,59 | 13,73 |
| Méditerranéen | 5,49 | 9,41 | 13,63 |
| Prairie tempérée | 5,78 | 11,16 | 13,73 |
| **Cultures** | **7,83** | **14,18** (p99 17,5) | **16,52** (57,8 i/s, p99 22,3) |
| **Forêt tempérée** | **7,27** | **12,98** | **15,94** (p99 21,4) |
| Alpin | **6,89** | 11,83 | 13,80 |
| Frontières | 6,33 | 11,65 | 14,15 |
| Côte avec la mer | 4,63 | 7,90 | 9,73 |

Avant / après sur le tour : medium 13,3–18,2 → 9,4–14,2 ms ; high 17,2–20,4 → 13,6–16,5 ms ; low inchangé. Restent au-dessus : cultures et forêt dans les trois préréglages, alpin en low, frontières en high (14,15). Textures du décor en high 330 → 206 Mo. **Adopté** (« Ok mis à part herbe », PR #729 fusionnée le 06/11).

### 2.5 Lots de développement ciblés (6–7 novembre)

**Y5 – Forêts lointaines en imposteurs (06/11, PR #723).** Bouquets de 4 arbres en un quadrilatère, de 1 500 m au brouillard. `biome_temperate_forest`, forêt on / off : low 5,19 / 5,28, medium 9,25 / 9,07 (+0,18), high 11,38 / 11,19 (+0,19). Critère (< 1 ms en medium) tenu. À-coup de 100–133 ms à la première forêt dessinée, corrigé par préchauffage. Captures caméra haute (120 m) validées. **Adopté.** Données : `mesures/2026-11-06-foret/`.

**Y22 – Herbe et rangs de vigne allégés au loin (06/11, PR #721, puis #736).** Gerbe simplifiée au-delà de 40 m, MultiMesh par tronçon écarté hors du champ, vigne en haie au-delà de 200 m, puis, sur les retours du propriétaire, bandes d'herbe élargies jusqu'à 80 m, fondu en densité et en couleur sans lisière, prés peints au sol. Neuf bancs (r721 à r721i), cultures :

| Banc (6/11) | Contenu | low | medium | high |
| --- | --- | --- | --- | --- |
| r721 | LOD de l'herbe seule | 5,21 → 5,22 | 10,91 → 10,71 | 14,12 → 13,57 |
| r721b | + prés plus ou moins mûrs | 5,35 → 5,24 | = | 14,06 → 13,77 |
| r721e | touffes peintes au sol, vigne en haie | 5,27 → 5,57 | 10,96 → 11,32 | 14,12 → 14,13 |
| r721f | bande devant jusqu'à 250 m, budgets × 1,5 | 5,13 → 5,52 | 8,57 → 9,08 | 10,41 → 10,77 |
| r721h | bande large 80 m, fondu sans lisière | 5,27 → 5,46 | 8,64 → 9,56 | 10,29 → 11,69 |

Primitives −5 / −13 / −20 % au premier banc. Bilan : l'herbe va plus loin sans limite nette pour +0,2 / +0,9 / +1,4 ms par rapport à main (dernier banc). Captures validées (« Ok », 06/11 22 h 23). **Adopté.** Le correctif #736 (ordre de remplissage des tronçons) ne change pas le rendu. Données : `mesures/2026-11-06-herbe-y22*/`.

**#732 – Cultures et forêt sous le budget (en cours, PR brouillon).** Banc `cout_rendu.py --troncon farmland,temperate_forest,alpine` (nuit du 6 au 7/11, 9146ea93, sans #721, `mesures/2026-11-07-cultures-foret/`). Référence par biome : cultures 7,80 / 13,06 / 15,89, forêt 7,07 / 12,91 / 16,34 ms (alpin non couvert, banc trop court). Gains en forêt :

| Variante (forêt) | low | medium | high |
| --- | --- | --- | --- |
| Arbres sans ombre | +0,18 | +1,18 | +1,86 |
| Moitié des arbres | +0,10 | +0,84 | +1,91 |
| Arbres détaillés jusqu'à 300 m | +0,04 | +0,51 | +1,25 |
| Sans imposteurs (Y5) | −0,05 | +0,06 | +0,22 |
| **Sans aucun arbre proche** | **−0,95** | **−0,97** | −0,28 |

En cultures, aucune variante sur les arbres ne bouge (±0,2 ms) : l'hypothèse « c'est la forêt devant qui coûte » est réfutée pour les cultures ; la cause est à chercher dans l'herbe, le sol ou la vigne. La bascule à 300 m n'est pas retenue (450 m choisis le 01/11). Passes en high : passe opaque 8,05 ms (54 %), prépasse de profondeur 3,31 ms (22 %), ombres 0,63 ms.

Remède essayé : `ombres_arbres_m=M`, ombres des arbres coupées au-delà de M mètres (cases de 250 m, plus repli de l'ombre dans le shader).

**Banc b (07/11, 0fa13490, qui contient #721, `mesures/2026-11-07-cultures-foret-b/`, 42 bancs).** Même tronçon cultures → forêt → alpin (alpin toujours non couvert). Référence du tronçon : **8,04 / 13,72 / 17,06 ms** (budgets 8 / 12 / 14 depuis le 7 novembre), high à 56 images/s et p99 19,8 ms. Avec l'herbe de #721, la référence a monté d'environ +0,5 / +0,7 / +1,0 ms par rapport au premier banc. Gain de chaque variante, tronçon entier puis cultures / forêt :

| Variante | low | medium | high | medium cultures / forêt | high cultures / forêt |
| --- | --- | --- | --- | --- | --- |
| Aucune ombre (borne) | 0,75 | 1,49 | 2,34 | 0,82 / 1,95 | 1,15 / 3,12 |
| Arbres sans ombre | 0,12 | 0,74 | 1,39 | −0,05 / 1,31 | 0,02 / 2,13 |
| Moitié de l'herbe | 0,26 | 0,60 | 1,28 | 0,69 / 0,63 | 1,24 / 1,29 |
| Ombre des arbres jusqu'à 100 m | 0,13 | 0,23 | 0,29 | −0,04 / 0,34 | 0,00 / 0,40 |
| Ombre des arbres jusqu'à 150 m | 0,12 | 0,17 | 0,28 | 0,06 / 0,31 | 0,00 / 0,34 |
| Ombre des arbres jusqu'à 250 m | 0,05 | −0,01 | −0,03 | −0,01 / 0,01 | 0,00 / 0,00 |

Par biome, la référence est cultures 8,39 / 14,20 / 17,23 et forêt 7,54 / 13,63 / 17,11 ms.

Lecture :
- Raccourcir l'ombre des arbres ne gagne que 0,3 à 0,4 ms en forêt, à 100 comme à 150 m. À 250 m, rien ne change : la coupure se fait par cases de 250 m, et le gros du coût des ombres d'arbres vient des arbres les plus proches.
- Couper toutes les ombres d'arbres gagne 1,3 ms en medium et 2,1 ms en high en forêt, mais rien en cultures.
- **En cultures, c'est l'herbe qui coûte** : la moitié des touffes gagne 0,7 ms en medium et 1,2 ms en high, et c'est la seule variante qui bouge dans ce biome. C'est la réponse à la question laissée ouverte par le premier banc.
- Même sans aucune ombre, aucune variante seule ne ramène medium et high sous leur budget : il faudrait combiner (par exemple ombres d'arbres et herbe), ou toucher à la passe opaque.

Captures : `planche/` du banc, une par variante et par biome.

**Correctif de la coupure (07/11, a2a87ad4).** La première coupure gagnait peu parce que la passe d'ombre est limitée par les sommets : replier un sommet dans le shader ne lui évite pas d'être traité, et une case de 250 m à cheval sur la limite gardait tous ses arbres. Nouvelle version : le modèle proche des arbres ne projette plus d'ombre ; un MultiMesh « ombre seule » par essence reçoit les arbres des carrés de 25 m à moins de M mètres de la caméra, reconstruit tous les 10 m de déplacement, et le shader fond l'ombre sur les derniers mètres. Vérifié dans le cloud (Vulkan logiciel) : ombres proches au même endroit, ombres au-delà de M absentes.

**Banc c (07/11, a2a87ad4, `mesures/2026-11-07-cultures-foret-c/`, 32 bancs).** Gain en forêt, low / medium / high :

| Variante (forêt) | low | medium | high |
| --- | --- | --- | --- |
| Ombre des arbres jusqu'à 100 m | +0,16 | +1,05 | +1,89 |
| Ombre des arbres jusqu'à 150 m | +0,17 | +0,84 | +1,64 |
| Arbres sans ombre (borne) | +0,20 | +1,24 | +2,29 |
| 2 cascades d'ombre au lieu de 4 | — | +0,59 | +1,13 |
| Ombres jusqu'à 200 m | — | +0,09 | +0,65 |

La coupure corrigée rend presque tout le gain d'« arbres sans ombre ». Cultures : aucune variante ne bouge (14,2 / 17,3 ms). Planche forêt low / medium / high (`planche_foret_ombres.jpg`) : **aspect validé par le propriétaire le 7 novembre à 12 h 41**.

**Banc d (07/11, f0c1fe42, avec #741 « bande large d'herbe moitié moins dense », `mesures/2026-11-07-cultures-foret-d/`, 22 bancs).** Ombre des arbres à 100 m : forêt +1,11 / +1,72 (medium / high). Avec 2 cascades en plus : +1,11 / +1,94, soit presque rien de plus : **non retenu**. Herbe effacée à 150 m au lieu de 250 (`herbe_fin_m=150`) : ≈ 0 partout, l'herbe coûte par sa densité et pas par sa distance : **rejeté**. Avec l'ombre à 100 m, par biome : forêt 7,23 / 12,32 / 15,26 ms, cultures 8,18 / 13,90 / 16,73 ms (low / medium / high).

Verdict : **ombre des arbres limitée à 100 m adoptée** dans les trois préréglages (`TreeRenderer.TREE_SHADOW_M`, 188e44cb ; essai `ombres_arbres_m=0` pour l'ancien comportement). **Budgets medium 13 ms et high 16 ms** (choix du propriétaire, 8 novembre). Avec ces budgets, la forêt passe (12,3 / 13 et 15,3 / 16) ; **les cultures dépassent encore** de 0,2 / 0,9 / 0,7 ms (8,18 / 8, 13,90 / 13, 16,73 / 16). Banc des effets d'écran (r732e) annulé et reporté en 5.0.

## 3. Récapitulatif par réglage

Valeurs de gain en ms (low / medium / high) ; « — » = sans objet dans ce préréglage.

| Réglage | Essais (date, PR) | Impact mesuré | Effet visuel | Verdict | État actuel |
| --- | --- | --- | --- | --- | --- |
| **MSAA** | Y13 4× en medium (28/10, #446) ; 2× (05–06/11, #729) | 4× → 2× : −1,84 / −1,67 (medium / high) ; sans MSAA : −3,3 / −3,7 | 2× : bords un peu moins lisses, validé sur captures | 2× adopté | medium et high en 2× |
| **SMAA / FXAA** | FXAA en low (28/10) ; SMAA (30/10, #608) | low +0,03 | panneaux et fenêtres plus nets | SMAA adopté | low en SMAA ; pas d'anticrénelage d'écran en high |
| **SSAO** | Y13 (28/10) ; SSAO low (05–06/11) ; garde-fou | sans SSAO −0,76 / −0,78 ; SSAO low −0,52 puis −0,34 / bruit | pieds des arbres, coins des maisons | gardé | medium et high, demi-résolution |
| **SSIL** | Y13 (28/10) ; 2.0.1 V3 (05/11, #717) ; étude (06/11) | sans SSIL −1,36 / −1,60 ; un cran plus bas −1,9 / −0,7 (démo) | indirect discret, rien de visible coupé | coupé en medium (#717) et en high (#729) | aucun préréglage |
| **Halo (glow)** | Y13 (28/10) ; 3 niveaux (06/11) | sans halo −1,24 / −0,98 ; 3 niveaux +0,45 medium, bruit high | soleil et zones claires | gardé, 3 niveaux | medium et high |
| **Ombres : atlas** | 4096 (Y13) → 2048 (#729) | −0,96 / −0,81 | ombres un peu moins fines, validé | 2048 adopté | medium et high 2048 |
| **Ombres : filtre doux** | Y13 ; 2.0.1 V1 (#717) | filtre un cran plus bas −0,87 / −0,66 (démo) ; filtre low −0,58 / −0,44 | bords des ombres | un cran plus bas adopté | medium low, high medium |
| **Ombres : cascades / distance** | 4 cascades (Y13), 400 m (Y13 étape 2) ; essais 2 cascades et 200 m (05/11, puis forêt 07/11) | 2 cascades −0,41 / −0,30 ; 200 m −0,41 / −0,22 ; en forêt (07/11) 2 cascades −0,59 / −1,13, 200 m −0,09 / −0,65, 2 cascades en plus de l'ombre des arbres à 100 m ≈ 0 / −0,2 | ombres lointaines | gardées (gain faible) | inchangées |
| **Ombres du relief** | proxy maille 40 m (06/11, #724) | −0,25 à +0,34 (bruit), primitives −40 % | aucun | rejeté | ombres pleines |
| **Ombres des arbres** | sans ombre (05/11, 07/11) ; coupure par cases à 100 / 150 / 250 m (banc b) ; groupe « ombre seule » par carrés de 25 m (bancs c et d, 07/11, #732) | cultures ≈ 0 ; forêt sans ombre −0,2 / −1,3 / −2,3 ; coupure par cases −0,1 / −0,3 / −0,4 ; « ombre seule » à 100 m −0,16 / −1,1 / −1,7 à −1,9 | ombres des arbres lointains (au-delà de 100 m) | « ombre seule » à 100 m adoptée (aspect validé 07/11) | ombre des arbres jusqu'à 100 m, les trois préréglages |
| **Ombres des pierres et fleurs** | 06/11 | −0,10 / −0,13 / bruit | aucun | rejeté (bruit) | inchangées |
| **Brume volumétrique** | Y13 étape 3 (28/10) ; sans brume, grille medium en high (05–06/11) ; lumière du ciel 1 puis 0,5 (05–06/11) | +0,2 à l'ajout ; sans brume −0,54 / −0,58 ; lumière du ciel ≈ 0 | profondeur de l'air ; montagnes plus noires une fois éclairée | adoptée, éclairée à 0,5 | medium light, high full |
| **Rendu des tons** | Filmic (28/10) ; AgX (29/10) ; courbe en S 0,35 (06/11) | ≈ 0 | ciel moins délavé ; contraste | AgX + courbe en S | Forward+ |
| **Anisotrope** | 16× global (28/10) ; 4 / 8 / 16 (29/10) ; 8× en high (06/11) ; ÷ 2 (05/11) | 8× en high : bruit ; ÷ 2 : −0,8 / −0,3 (démo) | route nette au loin | 4 / 8 / 8 | low 4×, medium 8×, high 8× |
| **Ciel** | incrémental, demi-résolution, nuages hors rayonnement (06/11) | −0,40 / −0,39 / −0,50 | aucun | adopté | `PROCESS_MODE_INCREMENTAL` |
| **Brouillard opaque** | 4 / 6 / 9 km (27/10, Y1) | non mesurable sur le banc de l'époque | horizon | adopté | inchangé |
| **Seuil LOD des maillages** | Y13 (28/10) ; plus tôt (06/11) | low −38 % de primitives, GPU −0,16 ; plus tôt : −0,32 medium, bruit high | aucun | seuil Y13 gardé, « plus tôt » rejeté | inchangé |
| **LOD des arbres** | 300 → 450 m (01/11, #689) ; 300 m remesuré (05/11, 07/11) | 450 m : ≈ +0,4 medium ; revenir à 300 m : jusqu'à −1,25 en high en forêt | arbres détaillés plus loin | 450 m adopté (choix du propriétaire) | 450 m partout |
| **Imposteurs de forêt** | Y5 (06/11, #723) | +0,18 / +0,19 | forêts jusqu'à l'horizon | adopté | 1 500 m → brouillard |
| **Herbe : quantité** | budgets Y11 (27/10) ; moitié (05/11, 07/11) ; 70 % en low (06/11) | moitié −0,27 / −0,77 / −0,96 (05/11), puis −0,35 / −0,69 / −1,24 en cultures après #721 (07/11) ; 70 % en low : aucun gain | herbe pleine | budgets gardés ; levier principal en cultures | low herbe pleine |
| **Herbe : niveau de détail au loin** | Y22 (06/11, #721) ; bande large moitié moins dense (07/11, #741) ; effacée à 150 m au lieu de 250 (07/11, #732) | premier banc −0,2 / −0,6 en medium / high ; version finale +0,2 / +0,9 / +1,4 ; #741 −0,4 / −0,55 (medium / high) ; 150 m ≈ 0 | herbe jusqu'à 80 m sans lisière | adopté | `main` |
| **Vigne** | haie au-delà de 200 m (Y22) | primitives −25 % caméra haute | aucun saut validé | adopté | 200 m |
| **Densité de végétation / arbres** | Y13 étape 2 (0,8, 70 000) ; moitié (05/11, 07/11) | +0,2 à l'ajout ; moitié : bruit en cultures, −0,84 / −1,91 en forêt | paysage plus plein | gardée | inchangée |
| **Tri du visible (S1)** | 28/10, 05/11 | −0,17 / −0,37 / −0,14 | aucun | livré coupé | `--culling=on` pour essayer |
| **Parallaxe de la route** | Y17 (30/10, #603) | high +3,8 à +5,2 | visible à 2–3 m | rejeté | non |
| **Feuillage simplifié (Lambert, sans reflets)** | G1, G3 (06/11) | bruit | aucun | adopté (principe) | `tree_sway.gdshader` |
| **Embellissements** (halo du soleil dans la brume, prés mûrs, dégradé des touffes) | 06/11 | bruit | léger | prés mûrs repris par Y22 ; le reste non retrouvé dans les préréglages | — |
| **Garde-fou de charge** | Y6 (30/10, #612) | medium 13,69 → 11,85 au pic | coupe SSIL / SSAO temporairement | adopté | `[render] load_guard` |

## 4. Enseignements

1. **Le rendu est limité par les pixels, pas par les objets.** MSAA, SSIL et halo pèsent 1 à 3,7 ms chacun ; le tri du visible, la densité des arbres, les cascades et les ombres du relief gagnent quelques dixièmes au plus. Retirer 40 % des primitives (ombres du relief) ne change rien au GPU de la GTX 1060.
2. **Le MSAA 2× a été le levier principal** des préréglages medium et high (≈ −1,8 ms partout), pour une perte visuelle validée sur captures.
3. **Sans arbres, la forêt coûte plus cher** (−0,95 ms en low et medium) : les arbres cachent le sol et l'herbe, plus chers par pixel. Supprimer de la végétation n'est donc pas un remède en soi.
4. **En forêt, les ombres des arbres proches sont le levier principal** (jusqu'à −2,1 ms en high), devant la densité et le niveau de détail. Une coupure par cases de 250 m ne gagnait que 0,3–0,4 ms (la passe d'ombre traite encore les sommets repliés) ; un groupe « ombre seule » limité aux arbres à moins de 100 m rend presque tout le gain (−1,1 / −1,9 ms). **En cultures, c'est l'herbe** (moitié des touffes : −0,7 ms en medium, −1,2 ms en high) ; les arbres n'y pèsent rien.
5. **Les ombres coûtent 0,5 / 1,9 / 2,3 ms au total** et font la moitié des primitives : c'est le coût par pixel (atlas, filtre) qui compte, pas le nombre de triangles.
6. **Les « loupés » valent plus que les réglages fins** : ciel recalculé à chaque image (0,8 ms), globe du menu dessiné hors menu, shader dupliqué par essence d'arbre (×4 sur le GPU), banc qui mesurait du low.
7. **Les réglages « presque gratuits » de Godot sont dans le bruit** (±0,6 ms sur le banc tout en cultures) : à garder pour le principe, sans en attendre de gain.
8. **Le p99 ne bouge presque jamais** (60 images/s plafonnées) : les vrais risques sont les à-coups (premiers dessins de shaders, construction de tuiles), traités par préchauffage (Y19, Y20, Y5, Y21) et par le garde-fou `hitches`.
9. **Toujours trois préréglages, au bon endroit, avec captures** : le pire cas est le bloc cultures du tour des biomes ; un banc d'un seul biome ou à 720p donne des chiffres plus bas.
10. **Les choix d'aspect du propriétaire priment sur le gain** : herbe pleine et ombres d'arbres en low, arbres détaillés à 450 m, herbe sans lisière (+1,4 ms en high), parallaxe refusée plutôt qu'un préréglage « ultra ».

## 5. Encore ouvert

- **Cultures encore au-dessus des budgets du 8 novembre** (banc d, avec #741 et l'ombre des arbres à 100 m) : 8,18 / 13,90 / 16,73 ms pour 8 / 13 / 16. Reporté en 5.0 avec les autres essais de gain.
- **Historique, budgets dépassés après #729 et #721** : cultures 14,2 / 16,5 ms et forêt 13,0 / 15,9 ms en medium / high (passe finale du 06/11, avant #721 qui ajoute environ +0,2 / +0,9 / +1,4 ms). En low, cultures 7,8, forêt 7,3 et alpin 6,9 ms dépassaient le budget de 6 ms ; avec le budget de 8 ms décidé le 7 novembre, ils passent tout juste (cultures 7,8 + 0,2 de #721 ≈ 8,0 ms, à confirmer au banc). Banc b du 7 novembre (avec #721) : tronçon 8,0 / 13,7 / 17,1 ms. Suite dans #732 : aucune variante seule ne suffit ; leviers mesurés : ombres des arbres en forêt, quantité d'herbe en cultures.
- **Reporté en 5.0 (choix du propriétaire, 8 novembre)** : tout nouvel essai de gain de performance. Prévu et non lancé : banc des effets d'écran sur le tronçon cultures → forêt → alpin, en low, medium et high (`cout_rendu.py --troncon farmland,temperate_forest,alpine --variantes base,sans_ssao,ssao_low,sans_brume,brume_light,msaa0_smaa,sans_glow,ciel_128 --repetitions 2`), bloc alpin du tronçon (banc d'environ 400 s), prépasse de profondeur.
- **Essais jamais mesurés** (cahiers sans résultat retrouvé) : Y3 (HLOD des villages), Y4 (ombres par sorte d'objet), Y7 (moteur Mobile en low), Y12 (lumière et particules), tableau du protocole `ESSAI_RENDU_Y11_Y12.md`, coût de la circulation AS6 avec véhicules à l'écran.
- **Pistes notées pour plus tard** : même passage propre de l'herbe pour les buissons nains, roseaux et herbes hautes (`ground_details.gd`) ; prépasse de profondeur (22 % du GPU en medium et high) ; S1b (occlusion par le relief) et S1c (décor hors vue) si un cas réellement chargé apparaît.

## 6. Où trouver les données

| Essai | Dossier partagé du projet | Dépôt |
| --- | --- | --- |
| Y13, Y2, Y6, Y16, Y17 | `qualite-graphique/` (`pc_gtx1060*`, `y2_godot47`, `y13_etape4_agx`, `y6_smaa`, `y16_parallaxe`) | cahiers `LOT_Y13`, `LOT_Y2`, `LOT_Y6`, `LOT_Y17` |
| Y8 | `mesures/2026-10-28/` | `LOT_Y8_toits_facades.md` |
| S1 | `culling/` | `ETUDE_RENDU_INVISIBLE.md` |
| #689, endurances 7bw / 7bx | `plans/FILE_MESURES_PC.md` ; PC `~/OpenRide/mesures/2026-11-01-auto-1-0/` | — |
| #706 | PC `captures/r706-rendu-harmonise/` | — |
| #710 | `mesures/2026-11-04-saccades-40m/` | `LOT_Y20` |
| #717 | `captures/r201-2-0-1/`, `captures/r717-controle-2-0-1/` | — |
| Y21 | `captures/r715-personnages/` | `LOT_Y21` |
| Étude U18 | `mesures/2026-11-05-u18/`, `2026-11-05-cout-rendu/`, `2026-11-06-optim/`, `2026-11-06-optim2/`, `2026-11-06-final/` | `ETUDE_OPTIMISATION_RENDU_2026-11-05.md` |
| #724 | `mesures/2026-11-06-ombres-relief/` | — |
| Y5 | `mesures/2026-11-06-foret/` | `LOT_Y5` |
| Y22 | `mesures/2026-11-06-herbe-y22*/` | `LOT_Y22` |
| #732 | `mesures/2026-11-07-cultures-foret/`, `-b/`, `-c/` (planche forêt validée), `-d/` | PR #732, étude § 8 |
