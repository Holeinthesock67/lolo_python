# Lot Y12 – Effets de lumière et particules

**Statut : validé par le propriétaire le 27 octobre** (« OK pour tout » aux neuf questions de `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §10) ; issue #386. Fin de projet, après Y2 (Godot 4.7.x), soumis aux budgets X2, X13 et X16.

## 1. Objectif

Demande du propriétaire du 27 octobre : « quelques effets lumières et particules ». Aujourd'hui l'image n'a ni glow, ni rayons de soleil, ni reflets ; les seules particules sont la pluie et la neige (P8, `weather_particles.gd`, budget `living(preset).weather_particles` 600 / 1 500 / 4 000) ; l'ombre des nuages existe mais seulement en `high` (P6, `terrain.gdshader`). Le Cyber-Rogue a sa charte (R17) avec glow, bloom et un pourcentage de particules par préréglage, encore à coder (R10 à R13).

## 2. Règles communes (pas d'exception)

- **Un seul endroit par sorte de réglage :**
  - effets d'image (glow, rayons, reflets, reflet du soleil) : clés du dictionnaire `IMAGE` de `quality_presets.gd`, à côté de `ssao` et `fog_volumetric`, appliquées par `render_quality.gd` ;
  - particules : budgets dans `LIVING` (comme `weather_particles`), donc coupées avec tout le décor vivant par `[render] living = false` ;
  - **échelle des particules** `particles_scale` = 0,25 / 0,60 / 1,00 en `low` / `medium` / `high`, **les valeurs de R17 §4.3** : la même clé sert au mode route et au Cyber-Rogue, R17 la lit au lieu d'avoir sa propre table.
- **Une seule fabrique de particules** : `engine/scripts/effects_particles.gd` (`GPUParticles3D`, maillages et matériaux dessinés par le code, aucune image), sur le modèle de `weather_particles.gd`, qui y est rangée. R10 et R12 (étincelles, éclats, arche de Perfect Shift) l'utilisent avec les couleurs de `neon_palette.gd`.
- **Vent unique** : toutes les particules qui flottent suivent le vent du modèle P4 (`wind_model.gd`), comme la pluie.
- **Lien avec le brouillard Y1** : aucune particule ni effet au-delà de 60 m de la caméra (boîte autour de la caméra, `visibility_range_end`) ; les rayons de soleil prennent la couleur et la densité du brouillard du thème ; un effet ne doit jamais éclairer ce que le brouillard cache.
- **Jour et nuit, saisons** : version 2.0 (P18, P19). Décision du 27 octobre : les lucioles (P3), qui dépendent de l'heure, attendent la 2.0 ; elles ne font pas partie d'Y12 en 1.x.

## 3. Lumière : effets chiffrés

Coûts : **estimations** GTX 1060, 1080p, `medium` ; à confirmer par l'essai (`docs/ESSAI_RENDU_Y11_Y12.md`).

| # | Effet | Gain visuel | Coût GPU estimé | `low` | `medium` | `high` | Lien |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L1 | **Glow léger** (`Environment.glow`, seuil haut : seuls le soleil, ses reflets et les surfaces mouillées brillent) | Moyen : lumière plus naturelle, soleil qui « bave » | 0,3–0,6 ms (3 à 5 niveaux) | Non | 3 niveaux | 5 niveaux | Glow refait en 4.6 : réglé après Y2 ; mêmes clés que R17 |
| L2 | **Rayons de soleil** : en `high`, lumière du soleil dans le brouillard volumétrique (déjà payé en `high`, `light_volumetric_fog_energy`) ; en `medium`, post-traitement radial en quart de résolution (masque de profondeur, seulement quand le soleil est dans le champ ou juste à côté) | Fort à contre-jour, à travers les arbres | `medium` 0,3–0,5 ms quand actif, 0 sinon ; `high` +0,2 ms | Non | Radial ¼ | Volumétrique | Couleur et densité du brouillard (Y1) |
| L3 | **Ombre des nuages** étendue à `medium` (existe en `high`, P6) | Fort : paysage animé, profondeur | < 0,1 ms | Non | Oui | Oui | Même bruit que `sky_clouds.gdshader` |
| L4 | **Reflet du soleil** sur la route et l'eau : vient de la rugosité variable d'Y11 (A3) et du glow L1 ; rien à ajouter | Fort au soleil bas | 0 | Oui | Oui | Oui | Y11 |
| L5 | **Reflets SSR** (eau, route mouillée) : SSR refait en 4.6, demi-résolution | Fort sous la pluie et près de l'eau | 0,5–1,5 ms | Non | Demi-rés., seulement si eau ou route mouillée à l'écran | Pleine rés. | Y11 A7, Y2 |
| L6 | **Halo du soleil** (petits quads dans l'axe du soleil, sans texture) | Faible, question de goût | < 0,05 ms | Non | Non par défaut | Oui | Coupé si le soleil est caché (profondeur) |

## 4. Particules : effets chiffrés

Coût CPU quasi nul (`GPUParticles3D`) ; coût GPU surtout en taux de remplissage, donc petites particules, alpha scissor quand c'est possible, pas de lumière par particule.

| # | Effet | Quand | Gain visuel | Coût GPU estimé | `low` | `medium` | `high` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | **Poussière dans la lumière** : grains qui brillent à contre-jour près de la caméra | Soleil devant, temps sec | Moyen, se marie avec L2 | < 0,05 ms | 80 | 180 | 300 |
| P2 | **Pollen et graines** dans les prés, **feuilles qui tombent** en forêt (tuiles de forêt d'OSM), **insectes** au-dessus de l'eau | Selon le décor proche ; biome automatique de la 3.0 ensuite (série U) | Moyen : le décor vit | 0,05–0,15 ms | 150 | 360 | 600 |
| P3 | **Lucioles** près des haies et de l'eau (**version 2.0**, avec le jour et la nuit) | Le soir | Fort le soir, nul le jour | < 0,05 ms | 30 | 70 | 120 |
| P4 | **Éclaboussures** derrière les roues (joueur, bots proches, voitures P13) et **ronds de gouttes** (dans le shader d'Y11 A7, pas en particules) | `wetness` > 0,3 (P8) | Fort sous la pluie | 0,1–0,3 ms | Joueur seul, 20 | Joueur + 4 plus proches, 40 chacun | Joueur + 8, 60 chacun |
| P5 | **Poussière soulevée** sur le gravier et les chemins (gravel de la série U), bas-côtés | Revêtement non goudronné | Moyen | < 0,1 ms | 40 | 90 | 150 |
| P6 | **Ambiance des foules** dans les cols (P15) : fumigènes colorés, confettis au sommet | Montée répertoriée, spectateurs présents | Moyen, festif | 0,1–0,3 ms (fumée = transparence) | 0 | Confettis | Confettis + fumigènes |
| P7 | **Cyber-Rogue (R17)** : étincelles sous les roues au sprint, éclats de la cible [Z], arche de Perfect Shift qui éclate, grésillement du Firewall ; traînées néon en **rubans** (R10), pas en particules | Mode Cyber-Rogue | Fort : lisibilité des actions | 0,1–0,3 ms | `particles_scale` 0,25 | 0,60 | 1,00 |

Les nombres ci-dessus sont ceux du préréglage `high` multipliés par `particles_scale`, arrondis à la dizaine : une seule règle pour tous les effets. Seuls le nombre de vélos qui éclaboussent (P4) et la sorte d'effet de foule (P6) changent en plus selon le préréglage.

## 5. Enveloppe et budgets

- **Enveloppe pour Y12** (validée) : au plus **+1,5 ms de GPU en `medium`** dans le pire cas mesuré (contre-jour avec L2, pluie avec P4 et L5), +0,5 ms en `low` ; p99 au plus +1 ms. `low` garde la règle de la spécification (55 images/s, p99 sous 25 ms) et R14 (60 images/s dans le Cyber-Rogue). Ensemble Y11 + Y12 : **au plus +2,5 ms en `medium`**, soit environ 15 % d'une image à 60 images/s.
- **Compilation des shaders** : chaque effet est créé au chargement (derrière l'écran de chargement), jamais à sa première apparition ; avec les ubershaders de 4.4, le p99 ne doit pas bouger quand un effet démarre (§5 de la recherche).
- **X2** : budget `effects_particles_build` (création des émetteurs, ≤ 5 ms). **X13** : nombre de particules actives ajouté à la sonde (`get_active_count`, comme P8). **X16** : endurance d'une heure en `medium` avec météo changeante, sans dérive de mémoire.

## 6. Travail demandé (le jour du lot)

1. Mesure de référence (scénarios de l'essai, `medium` puis `low`).
2. `effects_particles.gd` (fabrique commune, `weather_particles.gd` rangée dedans), clés `PRESETS` (`glow_levels`, `sun_shafts`, `cloud_shadow`, `ssr`, `sun_halo`) et `LIVING` (`dust_motes`, `ambient_particles`, `fireflies`, `spray`, `gravel_dust`, `crowd_fx`), `particles_scale` partagé avec R17.
3. Effets L1 à L6, puis P1 à P6 ; P7 fourni à R10 et R12 par la même fabrique.
4. Mesure après, captures, rapport.

## 7. Dépendances

Y2 (glow 4.6, SSR 4.6, ubershaders), Y1, P4 (vent), P6 (nuages), P8 (pluie), P13 et P15 (voitures, foules), P17 (branchement dans `main.gd`), R17 (palette, `particles_scale`), Y11 (rugosité et route mouillée). Fichiers partagés : `quality_presets.gd`, `render_quality.gd`, `weather_particles.gd`, `terrain.gdshader`.

## 8. Taille et découpage

Moyenne : **Y12a** lumière (L1–L6), **Y12b** particules (P1–P6), **Y12c** kit pour R10 et R12 (P7). Délégable (shaders et particules) ; recette visuelle sur le PC du propriétaire.

## 9. Hors périmètre

Éclairage global (SDFGI, VoxelGI : trop cher pour la GTX 1060 et inutile en plein air de jour), lumières des villages la nuit et phares (2.0), particules qui entrent en collision avec le décor, fumée volumineuse.
