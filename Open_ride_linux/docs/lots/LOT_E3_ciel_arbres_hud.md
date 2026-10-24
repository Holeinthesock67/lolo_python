# Lot E3 – Ciel, arbres par bruit et HUD final avec profil d'altitude

## 1. Objectif

Terminer le MVP visuel du sprint 3 (SRS §8 « MVP visuel », §13 sprint 3) : ciel physique et soleil fixe, brouillard qui masque vraiment la limite du terrain, arbres instanciés selon un bruit de densité sous la limite des arbres, HUD final lisible depuis le vélo avec le profil d'altitude. Ce lot **branche et affiche** ce que les lots K2, K3, L3 et L4 ont préparé sans affichage ; il ne réécrit pas leurs calculs.

À la fin du lot, le propriétaire pédale sur une trace compilée avec terrain, ciel, arbres et HUD, à au moins 55 images par seconde en préréglage `low` sur la GTX 1060.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/REVUE_E2_2026-10-24.md` (constats R2, R7, R8, R11 et R12, repris ici).
2. `docs/SRS_v1.1.md` §8 (MVP visuel, performance), §8.1 (shader), §11 (`[render]`), §12 et §13 (sprint 3 : 30 images/s, 1 h sans plantage).
3. `docs/contracts/world_format_v1.md` §3 (repère), §5 (terrain), §7 (végétation « sans polygones »), §9 (thème : `vegetation`, `sky`), §10 (couche absente).
4. Cahiers livrés : `LOT_E1_rendu_route_terrain.md`, `LOT_K2_modele_hud_profil.md`, `LOT_K3_placement_vegetation.md`, `LOT_L3_parametres_rendu_theme.md`, `LOT_L4_prereglages_qualite.md`, et le cahier E2 de la PR #75.
5. Code : `engine/scripts/world_streamer.gd`, `engine/scripts/terrain_tiles.gd`, `engine/scripts/render_quality.gd`, `engine/scripts/quality_presets.gd`, `engine/scripts/vegetation_placer.gd`, `engine/scripts/hud_view_model.gd`, `engine/scripts/erg_view_model.gd`, `engine/scripts/main.gd`, `engine/scenes/main.tscn`, `engine/tests/test_world_streamer.gd`.

## 3. Prérequis

- E2 fusionné (PR #75, corrigée après la revue) : shader `terrain.gdshader`, `terrain_material.gd`, `set_theme` du gestionnaire de tronçons, test de rendu sous Xvfb (`engine/tests/render/`), que ce lot étend pour le décor du §4.1.
- K2, K3, L3 et L4 livrés (c'est le cas sur `main`).
- Pas de prérequis matériel pour coder ; la recette visuelle se fait sur le PC cible.

## 4. Travail demandé

### 4.1 Décor du terrain (SRS §8.1, reste d'E2)

Dans `terrain.gdshader` :
- **Variation de l'herbe :** bruit de valeur à deux échelles (environ 8 m et 60 m), calculé dans le shader à partir de la position monde (pas de texture de bruit, pas d'appel aléatoire). Il module la luminosité de l'herbe de ± 8 % au plus.
- **Facettes de la roche :** la roche utilise la normale de la face (`cross(dFdx(pos), dFdy(pos))`) mêlée à la normale lissée, réglée par un `uniform` `rock_facet_strength` (0,6 par défaut).
- Un `uniform` `detail_strength` (1 par défaut) met ces deux effets à 0 ; il sert aux tests et au préréglage `low` si la mesure le justifie.
- La fonction de mélange herbe / roche / neige de L3 n'est **pas** modifiée : le décor change la couleur, jamais les poids.

Retirer les couleurs de sommet devenues inutiles des tuiles (`ARRAY_COLOR` dans `terrain_tiles.gd`, constat R8), sauf si E2 l'a déjà fait.

### 4.2 Ciel, soleil et brouillard

- **Ciel :** `PhysicalSkyMaterial` à la place du `ProceduralSkyMaterial` d'E1 (SRS : « ciel physique avec soleil fixe »). Le soleil est la `DirectionalLight3D` déjà orientée par `sky_params` (E2) ; il ne bouge pas pendant la séance, donc le rayonnement du ciel est calculé une fois (`Sky.process_mode` en qualité, taille de radiance 256 en `low`).
- **Lumière ambiante** tirée du ciel ; aucune valeur réglée à la main dans le code.
- **Brouillard de limite (constat R2) :** brouillard en profondeur d'E1 conservé (début 3 000 m, fin au rayon des tuiles lointaines) avec `fog_density = 1.0`, pour que la limite à 12 km soit entièrement couverte (déjà fait le 24 octobre pour l'essai d'E2, `render_quality.gd`). Couleur du brouillard égale à la couleur d'horizon du ciel, pour que les montagnes lointaines se fondent dans le ciel et non dans une bande grise.
- **Brouillard du thème :** `sky.fog_density` ne règle que le brouillard volumétrique (`volumetric_fog_density`), activé seulement quand le préréglage le demande (`fog_volumetric`, préréglage `high`). La ligne d'E2 qui écrit cette valeur dans `fog_density` est supprimée.

### 4.3 Arbres par bruit (format §7 « sans polygones »)

Nouveau `engine/scripts/tree_renderer.gd` (sans `class_name`), qui affiche ce que calcule `vegetation_placer.gd` (K3) :
- **Calcul dans les tâches de fond :** pour chaque tuile proche chargée, `place_tile(...)` est appelé dans la même tâche `WorkerThreadPool` que le maillage de la tuile, ou dans une tâche à part de la même file. Les `MultiMesh` et `MultiMeshInstance3D` se créent sur le fil principal, dans le budget de `MAX_NEW_PER_FRAME` d'E1.
- **Hauteur exacte :** `height_at` lit les hauteurs de la tuile avec **la même découpe en triangles** que `terrain_tiles.gd`, pas une interpolation bilinéaire : le pied de l'arbre est sur la surface dessinée.
- **Densité :** `vegetation.max_density_per_ha` du thème multiplié par `vegetation_density_factor` du préréglage (L4 : 0,3 / 0,6 / 1,0).
- **Sans couche terrain :** arbres posés sur le sol plat d'E1, à son altitude.
- **Niveaux de détail :** `visibility_range` s'applique à **toute** une `MultiMeshInstance3D` (distance au centre de sa boîte), pas à chaque arbre. Chaque tuile proche est donc découpée en cases de 250 m × 250 m, chacune avec deux `MultiMesh` :
  - de 0 à 300 m : modèle bas en polygones (tronc et deux ou trois cônes, au plus 120 triangles), ombres portées ;
  - de 300 à 1 500 m : deux quadrilatères croisés (4 triangles), sans ombre ;
  - au-delà : pas d'arbre (les tuiles lointaines n'en portent pas).
- **Modèles générés par le code** (aucun fichier 3D, aucune licence à gérer), deux ou trois variantes de silhouette et une teinte par arbre tirée de façon déterministe de sa position. Échelle : la quatrième composante de `place_tile`.
- **Budget d'instances** (constantes documentées, ajustables après la mesure du §7) : au plus 20 000 arbres affichés en `low`, 50 000 en `medium`, 100 000 en `high`. Au-delà, les cases les plus lointaines sont retirées en premier.
- **Libération :** les arbres d'une tuile sont libérés avec la tuile ; un changement de parcours vide tout, comme dans E1.
- **Couche `vegetation` présente et non vide :** hors de ce lot (E4). E3 n'appelle `place_tile` qu'avec `areas = []`.

### 4.4 Préréglages de qualité : une seule table (constat R7)

- `render_quality.gd` applique les valeurs de `quality_presets.gd` (L4) : SSAO, MSAA, brouillard volumétrique, densité de végétation, tronçons de route devant et derrière. La table interne d'E1 est supprimée ; la distance des ombres (150 / 300 / 600 m) rejoint la table de L4.
- Le préréglage vient de `--quality` (L4) ; `low` par défaut.
- `renderer_hint` (moteur Mobile ou Forward+) **n'est pas** appliqué ici : il se choisit au lancement de Godot (lanceur, lot G).

### 4.5 HUD final (SRS §8 « HUD de base »)

Nouveau `engine/scripts/hud_view.gd`, attaché au `CanvasLayer` du HUD dans `main.tscn`, qui **dessine** sans rien calculer :
- **Valeurs :** puissance lissée 3 s, cadence, fréquence cardiaque, vitesse, distance, pente (couleur selon `grade_class` de K2 : plat, montée, raide, mur), braquet `k/24`, temps écoulé. Le temps manque aujourd'hui dans `session_lines`.
- **Une seule source de textes :** `hud_view_model.gd` a deux chemins (`on_state`/`evaluate` de K2, `session_lines` de la PR #73). Les fusionner en gardant le comportement de `session_lines` en ERG (cible, biais d'intensité, braquet fixe), validé sur le vélo le 24 octobre. Les tests existants du modèle passent sans être affaiblis.
- **Profil d'altitude :** bande en bas de l'écran, `profile(route, s)` de K2 (500 m derrière, 4 500 m devant), une couleur par classe de pente, repère de la position, altitudes minimale et maximale écrites. Le profil se recalcule au plus 5 fois par seconde, ou quand `s` a avancé d'une colonne.
- **Prochaine montée :** une ligne tirée de `next_climb` (K2) : distance avant le pied, longueur, pente moyenne ; « en cours » avec ce qui reste quand on y est.
- **Lisibilité à 2,5 m de l'écran** (1 920 × 1 080) : chiffres principaux d'au moins 48 px de haut, libellés d'au moins 24 px ; fond semi-transparent ; rien ne masque le centre de l'image ni la route à moins de 50 m.
- **Mise à l'échelle :** la mise en page suit la taille de la fenêtre (ancres et conteneurs, pas de positions en pixels écrites en dur).
- **Hors périmètre du HUD :** bandeau ERG détaillé, histogramme des blocs et bip à T − 3 s (lot F2). La ligne ERG actuelle reste affichée telle quelle.

### 4.6 Mesure des images par seconde

Toutes les 30 s pendant la séance, l'engine écrit sur sa sortie une ligne :

```text
[perf-rendu] images/s moy 61.2 ; temps d'image p50 15.9 / p99 22.4 / max 41.0 ms ; arbres 18450 ; appels de dessin 412 ; préréglage low
```

Temps d'image mesurés sur la fenêtre de 30 s (pas `Engine.get_frames_per_second()` seul, qui lisse trop) ; appels de dessin par `RenderingServer.get_rendering_info`. Le coût de la mesure reste négligeable (aucune allocation par image).

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/tree_renderer.gd`, `engine/scripts/hud_view.gd`, `engine/tests/unit/test_tree_renderer.gd`, `engine/tests/unit/test_hud_view.gd`, `engine/tests/unit/test_render_quality.gd`.
- **Modifiés :**
  - `engine/shaders/terrain.gdshader` (décor, §4.1) ;
  - `engine/scripts/terrain_tiles.gd` (couleurs de sommet retirées, lecture de hauteur exacte pour les arbres) ;
  - `engine/scripts/world_streamer.gd` (arbres par tuile, budget, libération) ;
  - `engine/scripts/render_quality.gd`, `engine/scripts/quality_presets.gd` (une seule table, §4.4) ;
  - `engine/scripts/hud_view_model.gd` (fusion des deux chemins, temps écoulé) ;
  - `engine/scripts/main.gd`, `engine/scenes/main.tscn` (ciel, brouillard, HUD) ;
  - `engine/tests/render/test_terrain_render.gd` (décor : couleurs d'E2 inchangées avec `detail_strength = 0`, variation de l'herbe bornée à ± 8 % sinon) ;
  - `engine/tests/test_world_streamer.gd`, `engine/tests/unit/test_hud_view_model.gd`, `engine/tests/README.md` ;
  - `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne chacun).
- **Interdits :** `vegetation_placer.gd` (lecture seule ; un défaut trouvé est signalé), `theme_render_params.gd`, le core, le compilateur, les contrats.

## 6. Modifications de contrat autorisées

Aucune. Les couleurs des arbres et l'azimut du soleil ne sont pas dans le format §9 : constantes documentées, signalées dans le rapport comme candidates pour une version 1.1 du thème.

## 7. Critères d'acceptation

**Automatiques (intégration continue) :**
1. `engine/tests/run_engine_tests.sh` passe en entier ; `pytest` passe dans `core/` et `compiler/`.
2. Arbres :
   - même parcours, même thème, même préréglage : mêmes positions d'arbres d'une exécution à l'autre (empreinte des transformations) ;
   - aucun arbre à moins de `road.width_m / 2 + 4 m` de l'axe, au-dessus de `treeline_m` ou sur une pente au-dessus du seuil (vérifié sur la sortie réelle de `tree_renderer.gd`, pas seulement sur K3) ;
   - pied de chaque arbre à moins de 5 cm de la surface dessinée de la tuile ;
   - nombre d'arbres affichés jamais au-dessus du budget du préréglage ; chaque case de 250 m a ses deux niveaux avec les distances du §4.3.
3. Défilement du parcours de démonstration avec terrain de bout en bout à 20 m/s simulés (comme le test 2 d'E1) : `MultiMeshInstance3D` vivantes bornées, nombre d'objets en fin de parcours à ± 5 % de sa valeur au premier tiers.
4. Préréglages : pour `low`, `medium` et `high`, l'environnement, le viewport et le gestionnaire de tronçons reçoivent exactement les valeurs de `quality_presets.gd` ; un préréglage inconnu donne `low`.
5. Brouillard : en profondeur, `fog_density` vaut 1 et la fin du brouillard égale le rayon des tuiles lointaines ; `volumetric_fog_enabled` n'est vrai qu'en `high`, avec la densité du thème.
6. HUD :
   - pour une trame d'état de référence, chaque libellé affiche le texte attendu, temps écoulé compris ; une valeur absente donne « — » ;
   - profil : autant de points que de colonnes, repère à la position, couleurs selon `grade_class` ;
   - à 1 280 × 720 et à 1 920 × 1 080, aucun libellé ne sort de l'écran ni ne chevauche un autre (boîtes des contrôles comparées) ;
   - les tests du modèle du HUD existants passent sans être modifiés, sauf l'ajout du temps écoulé.
7. Temps CPU sans écran, relevés dans le rapport : placement et `MultiMesh` d'une tuile proche à la densité du préréglage `high` (seuil 150 ms en intégration continue), recalcul du profil (seuil 2 ms).

**Sur le PC cible (le propriétaire, GTX 1060, 1 920 × 1 080) :**
8. Préréglage `low`, démo puis trace réelle compilée avec relief : lignes `[perf-rendu]` sur 20 min, moyenne ≥ 55 images/s, p99 du temps d'image ≤ 33 ms, jamais sous 30 images/s (SRS §12).
9. Aucune limite de terrain visible à l'horizon ; aucun arbre flottant ou planté dans la route ; pas de saut visible au changement de niveau de détail à 300 m.
10. HUD lisible depuis le vélo sans se pencher ; profil d'altitude qui avance avec le coureur.
11. Séance d'1 h sans plantage ni montée continue de la mémoire (SRS §13 sprint 3).

## 8. Hors périmètre

- Forêts OSM, bâtiments, eau et sons (E4).
- Bandeau ERG détaillé, histogramme des blocs, bip à T − 3 s (F2).
- Menus, écran de fin de séance, choix du moteur de rendu au lancement (G).
- Herbe en brins, vent dans les arbres, cycle jour-nuit.
## 9. Livraison (24 octobre 2026, branche lot-e3-e4)

- **Ciel physique et brouillard** : PhysicalSkyMaterial avec 
adiance_size = 1 dans engine/scenes/main.tscn et main.gd ; brouillard de profondeur avec og_density = 1.0 et og_depth_end = 12000.0 (teinte d'horizon) ; brouillard volumétrique activé uniquement en préréglage high avec la densité du thème (
ender_quality.gd).
- **Variation du terrain** : modulation procédurale de l'herbe par bruit (+- 8 %) et facettes de la roche dans engine/shaders/terrain.gdshader et 	errain_material.gd (detail_strength = 1.0, 
ock_facet_strength = 0.6).
- **Arbres par bruit** : engine/scripts/tree_renderer.gd avec deux niveaux de détail (LOD0 0–300 m avec ombres <= 120 triangles, LOD1 300–1 500 m sans ombres 4 triangles en croix), partitionnement par cellules de 250 m, hauteur exacte extraite par TerrainTiles.mesh_height_at, respect strict du budget d'instances (20 000 en low, 50 000 en medium, 100 000 en high).
- **Préréglages unifiés** : table centralisée dans engine/scripts/quality_presets.gd et 
ender_quality.gd pilotant distance d'ombres, budget d'arbres et visibilité des bâtiments.
- **HUD final** : engine/scripts/hud_view.gd sur le canvas $HUD, typographie grande taille (>= 48 px pour les valeurs, >= 24 px pour les unités), bandeau profil d'altitude 120 colonnes teinté selon grade_class, prochaine montée et temps écoulé.
- **Métriques périodiques** : émission de lignes [perf-rendu] toutes les 30 secondes dans engine/scripts/main.gd.
- **Tests unitaires et headless** :
  - engine/tests/unit/test_tree_renderer.gd (9 vérifications) ;
  - engine/tests/unit/test_hud_view.gd (24 vérifications) ;
  - engine/tests/unit/test_render_quality.gd (28 vérifications) ;
  - test de rendu terrain 	est_terrain_render.gd mis à jour (10 vérifications).
- **Reste à faire par le propriétaire** : validation visuelle et de performance sur la machine cible (critères 8 à 11).
