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

## 5. Suite

Mesures du vendredi 6 novembre, 7 h (PC) : variantes Godot de `cout_rendu.py` sur le parcours tout en cultures, puis la recette U18 complète avec les combinaisons retenues, planche avant/après en trois qualités pour le propriétaire. Le préréglage ne change dans `quality_presets.gd` et `render_quality.gd` qu'après sa validation des captures.
