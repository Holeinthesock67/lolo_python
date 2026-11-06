# Étude : optimisation du rendu des biomes (5 novembre 2026)

Point de départ : la recette U18 (partie PC, étape 7bt) dépasse les budgets GPU de `perf_targets.json` en medium et en high sur tous les biomes, et en low sur la côte, les cultures, la forêt et l'alpin. Demande du propriétaire (5 novembre) : un vrai travail de recherche d'optimisation, sans trop nuire à la qualité graphique, selon les règles de l'art du métier, et tout documenter. Document de recherche détaillé, avec les sources Web : Claude Doc « Optimisation graphique d'OpenRide : techniques du métier » (hors dépôt). Recherche précédente : `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` (27 octobre, techniques T1 à T14).

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
6. Lots de développement à part : niveau de détail de l'herbe au loin (lot herbe), ombres simplifiées du terrain, forêt lointaine en imposteurs.

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

Couper 30 % de l'herbe et les ombres des arbres en low ne gagne rien : le propriétaire les garde. Les cultures et la forêt restent au-dessus du budget : lots Y22 (herbe au loin, ombres simplifiées du relief) et Y5 (forêt lointaine). Le relief alpin est aussi plus lourd que les cultures (banc de la PR #724).

Revue des autres « loupés » du même genre : le globe du menu « Monde ouvert » (SubViewport de 560 px en `UPDATE_ALWAYS`) était dessiné à chaque image pendant la sortie ; corrigé, il ne l'est plus que menu ouvert.

## 7. Décisions (6 novembre)

Captures validées par le propriétaire : medium et high (MSAA 2×, atlas 2048, high sans SSIL), low inchangé, ciel allégé. Ces réglages sont dans `quality_presets.gd`, `render_quality.gd`, `tree_sway.gdshader`, `sky_clouds.gdshader` et `scenes/main.tscn` ; les essais correspondants ont quitté `render_diag.gd`. Reste à choisir sur captures le contraste et la part de lumière du ciel dans la brume (`RenderQuality.VOLUMETRIC_AMBIENT_INJECT`, à 1 en attendant ; image jugée trop claire), avec `reglage_image.py`.
