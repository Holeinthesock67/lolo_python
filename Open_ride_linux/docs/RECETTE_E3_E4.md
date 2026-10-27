# Protocole de recette et consignes de test – Lots E3 et E4

Date : 24 octobre 2026  
Branche : `lot-e3-e4`  
Demande de fusion (PR) : [#91](https://github.com/Holeinthesock67/lolo_python/pull/91)  
Machine cible : PC du propriétaire (GPU NVIDIA GeForce GTX 1060 6 Go, écran 1 920 × 1 080)

---

## 1. Périmètre des livraisons

### Lot E3 : Ciel physique, brouillard, arbres par bruit et HUD final
- **Shader de terrain** : modulation procédurale de l'herbe par bruit ($\pm 8\%$) et normales à facettes configurables sur la roche.
- **Atmosphère & Horizon** : ciel physique `PhysicalSkyMaterial`, brouillard de profondeur calé sur la teinte d'horizon (densité 1.0, fin à 4 / 6 / 9 km en `low` / `medium` / `high` depuis le lot Y1), brouillard volumétrique activé uniquement en mode `high` avec la densité du thème.
- **Arbres par bruit** : double niveau de détail LOD0 (0–300 m avec ombres $\le 120$ tris) et LOD1 (300–1 500 m sans ombre 4 tris), partitionnement en cases de 250 m, hauteur exacte du relief, respect strict du budget d'instances (20 000 en `low`, 50 000 en `medium`, 100 000 en `high`).
- **Préréglages unifiés** : pilotage centralisé (`quality_presets.gd` / `render_quality.gd`) des ombres, du budget d'arbres et de la visibilité des bâtiments.
- **HUD final** : typographie agrandie ($\ge 48$ px pour les valeurs, $\ge 24$ px pour les libellés), profil altimétrique 120 colonnes coloré par `grade_class`, prochaine montée et temps écoulé.
- **Télémétrie de performance** : mesure périodique émise toutes les 30 secondes via la ligne de log `[perf-rendu]`.

### Lot E4 : Couches OSM (bâtiments, eau, forêts) et modèle sonore
- **Jupe des bâtiments** : extension de 3 m sous la base (`skirt_m = 3.0`) pour une insertion naturelle dans le relief sans coupure ni flottaison.
- **Forêts OSM** : priorité aux polygones de végétation OSM (densité nominale), semis de bruit complémentaire hors zones (`p_region`) diminuant sous la limite des arbres.
- **Plans d'eau et cours d'eau** : maillage continu des rivières et lacs avec textures semi-transparentes du thème.
- **Modèle sonore spatialisé** : synthèse sonore procédurale au démarrage en moins de 100 ms (seuil 500 ms) pour le vent, la roue libre, la cloche d'église, la rivière, le bétail et le village ; gestion de 4 lecteurs 3D actifs avec atténuation et fondu ; surcharge optionnelle via `~/OpenRide/Sounds/<nom>.ogg`.
- **Diffusion continue OSM** : chargement asynchrone par `osm_streamer.gd` en arrière-plan, fusion à au plus 3 maillages par tronçon (bâtiments, cours d'eau, plans d'eau).

---

## 2. Consignes de test local (PC du propriétaire)

### Étape 1 : Récupérer la branche et vérifier l'environnement
```bash
git checkout lot-e3-e4
git pull origin lot-e3-e4
```

Vérifier la validité des suites de tests unitaires et headless :
```bash
# Lancement de la suite complète engine sans écran (avec Xvfb)
REQUIRE_RENDER=1 engine/tests/run_engine_tests.sh
```
*Résultat attendu : 16/16 étapes OK, 0 échec.*

---

### Étape 2 : Lancement visuel avec parcours de démonstration (Préréglage `low`)

Lancer l'engine avec les options de base :
```bash
# En mode fenêtré ou plein écran 1080p
./build/Godot_v4.3-stable_linux.x86_64 --path engine --routes-dir=~/.local/share/openride/routes --quality=low
```

Points de contrôle à valider :
1. **Compilations des shaders** :
   - Vérifier dans la console l'absence d'erreurs ou d'avertissements de compilation GLSL/Godot Shading Language (moteur Forward+).
2. **Ciel et horizon (Lot E3)** :
   - Le ciel affiche un dégradé physique naturel (`PhysicalSkyMaterial`).
   - La coupure du terrain lointain (fin du brouillard du préréglage plus une tuile, lot Y1) est parfaitement invisible, fondue dans la couleur d'horizon par le brouillard de profondeur.
3. **Arbres et niveau de détail (Lot E3)** :
   - Aucun arbre flottant au-dessus du sol ou planté dans le ruban d'asphalte (couloir de sécurité de $\ge 7$ m de l'axe respecté).
   - Observer la transition à 300 m : pas de pop brusque ni de saut visuel géométrique gênant entre LOD0 (modèle ombré) et LOD1 (croix 4 triangles).
4. **Lisibilité du HUD (Lot E3)** :
   - Les valeurs numériques (puissance, cadence, FC, vitesse) sont immédiatement lisibles sans se pencher sur l'écran.
   - Le profil d'altitude en bas de l'écran avance de manière fluide et ses colonnes adoptent les teintes attendues (vert pour plat, jaune/orange/rouge pour les pourcentages de montée).
5. **Cadence d'images (Critère 8 d'E3)** :
   - Surveiller les lignes `[perf-rendu]` affichées dans la console toutes les 30 secondes :
     ```text
     [perf-rendu] images/s moy 58.4 ; temps d'image p50 16.8 / p99 22.1 / max 28.4 ms ; arbres 7420 ; appels de dessin 84 ; préréglage low
     ```
   - **Critère de validation** : moyenne $\ge 55$ FPS, p99 $\le 33$ ms, aucun passage sous 30 FPS.

---

### Étape 3 : Contrôle des couches OSM et de l'ambiance sonore (Lot E4)

Lancer une trace réelle contenant un village et un cours d'eau (ex. trace d'entraînement avec relief) :
```bash
./build/Godot_v4.3-stable_linux.x86_64 --path engine --routes-dir=~/.local/share/openride/routes --quality=low
```

Points de contrôle à valider :
1. **Intégration des bâtiments (Lot E4)** :
   - Les bâtiments construits sur terrain en pente présentent une assise propre grâce à la jupe de 3 m ; aucun vide sous les murs n'est visible.
2. **Eau et forêts OSM (Lot E4)** :
   - Les ruisseaux et rivières coupant ou longeant le parcours restent à la surface sans clignotement z-fighting avec le sol.
   - Les massifs boisés correspondent aux zones denses de la carte, avec quelques arbres isolés naturels dans les clairières.
3. **Environnement sonore (Lot E4)** :
   - Le souffle du vent s'élève avec la prise de vitesse en descente et faiblit en montée lente.
   - En arrêtant de pédaler (cadence = 0, vitesse > 10 km/h), le cliquetis de la roue libre se fait entendre distinctement.
   - Au passage à proximité d'un village ou d'un clocher (POI), le son spatialisé 3D monte dans les haut-parleurs puis s'atténue progressivement.
   - Aucun craquement audio ni artefact sonore.

---

### Étape 4 : Test de bascule des préréglages de qualité

Tester successivement les options `--quality=medium` et `--quality=high` :
```bash
./build/Godot_v4.3-stable_linux.x86_64 --path engine --quality=medium
./build/Godot_v4.3-stable_linux.x86_64 --path engine --quality=high
```
- En `medium` : ombres étendues à 300 m, densité d'arbres augmentée (jusqu'à 50 000 instances).
- En `high` : brouillard volumétrique actif, portée des ombres à 600 m, portée des bâtiments augmentée à 1 500 m.

---

## 3. Synthèse des critères d'acceptation validés

| Lot | Critère | Statut automatique (CI) | Statut recette locale (GTX 1060) |
| --- | --- | --- | --- |
| **E3** | Ciel physique & brouillard horizon (4 / 6 / 9 km, Y1) | Conforme (`test_render_quality`) | À observer à l'écran |
| **E3** | Modulation herbe $\pm 8\%$ et facettes roche | Conforme (`test_terrain_render`) | À observer à l'écran |
| **E3** | Arbres LOD0/LOD1 & budget d'instances | Conforme (`test_tree_renderer`) | À observer à l'écran |
| **E3** | HUD grand format & profil d'altitude | Conforme (`test_hud_view`) | À observer à l'écran |
| **E3** | Performance $\ge 55$ FPS sur GTX 1060 | Logs `[perf-rendu]` intégrés | À relever sur séance de 20 min |
| **E4** | Jupe de 3 m sous les bâtiments | Conforme (`test_building_mesh`, `test_osm_streamer`) | À vérifier dans un village |
| **E4** | Forêts OSM & semis hors zones | Conforme (`test_vegetation_placer`, `test_tree_renderer`) | À vérifier sur trace réelle |
| **E4** | Synthèse procédurale sonore & 4 lecteurs 3D | Conforme (`test_sound_player`) | À écouter au casque / enceintes |
| **E4** | Streaming fluide des tronçons OSM | Conforme (`test_osm_streamer`) | À vérifier à l'entrée de tronçon |
