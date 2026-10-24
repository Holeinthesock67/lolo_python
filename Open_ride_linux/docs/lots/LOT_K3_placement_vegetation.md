# Lot K3 – Placement déterministe de la végétation (sans affichage)

## 1. Objectif

Préparer les arbres du lot E3 et les forêts d'E4 : calculer **où** poser les arbres, de façon déterministe, à partir des polygones `vegetation` du `.world` ou, à défaut, d'un bruit de densité sous la limite des arbres du thème (format `.world` §7). L'affichage (`MultiMeshInstance3D`, modèles d'arbres) reste à E3/E4.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/contracts/world_format_v1.md` §3 (repère), §5 (terrain), §7 (végétation), §9 (thèmes) ; `docs/contracts/world/vegetation.schema.json`, `theme.schema.json`.
3. Code : `engine/scripts/route_data.gd`, `engine/scripts/theme_loader.gd` (section `vegetation` : `treeline_m`, `max_density_per_ha`), `engine/themes/default/theme.json` ; après E1 : `engine/scripts/terrain_tiles.gd` (hauteur du terrain, lecture seule).

## 3. Prérequis

Lot K1 livré. Le lot K4 (lecture des couches OSM) n'est pas nécessaire : le placeur reçoit les polygones sous forme de tableaux.

## 4. Travail demandé

Nouveau `engine/scripts/vegetation_placer.gd` (`extends RefCounted`, sans `class_name`), sans nœud :

```gdscript
func place_tile(tile_x: int, tile_z: int, tile_size_m: float, height_at: Callable,
                route, theme: Dictionary, areas: Array = []) -> PackedVector4Array
# chaque élément : (x, y, z, échelle) dans le repère du monde
```

- **Graine stable :** dérivée de `(tile_x, tile_z)` pour le bruit, de l'`id` du polygone pour les zones OSM (format §7). Même entrée, même sortie, d'une exécution à l'autre et d'une machine à l'autre (pas de `randi()` global : `RandomNumberGenerator` avec `seed` explicite, ou hachage maison).
- **Densité :** zones OSM : `density × max_density_per_ha` du thème ; `kind` `wood` 100 %, `scrub` 40 %, `orchard` 60 % (constantes) ; autres valeurs ignorées. Sans zone : bruit de densité (`FastNoiseLite` à graine fixe, ou bruit de valeur maison), à au plus 50 % du maximum.
- **Exclusions :** couloir de la route (moitié de `road.width_m` + 4 m), altitude au-dessus de `treeline_m`, pente du terrain au-dessus de `terrain.slope_threshold_deg` du thème, trous des polygones.
- `y` = `height_at.call(x, z)` (la fonction de hauteur est fournie : tests avec une fonction analytique).
- Échelle entre 0,7 et 1,3, dérivée de la même graine.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/vegetation_placer.gd`, `engine/tests/unit/test_vegetation_placer.gd`.
- **Modifiés :** `engine/tests/README.md` (une ligne), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, scripts de rendu d'E1.

## 6. Modifications de contrat autorisées

Aucune. Si une règle du §7 est ambiguë (par exemple la densité par `kind`), garder la valeur du cahier et le signaler.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Déterminisme : deux appels identiques donnent des tableaux égaux élément par élément ; une empreinte (somme de contrôle) d'une tuile de référence est figée dans le test.
3. Densité : sur une zone `wood` de 1 ha à `density` 1, le nombre d'arbres est à ± 10 % de `max_density_per_ha` ; à `density` 0, aucun arbre.
4. Exclusions : aucun arbre à moins de `road.width_m / 2 + 4 m` de l'axe (vérifié par `route`) ; aucun au-dessus de `treeline_m` (fonction de hauteur en pente) ; aucun dans un trou.
5. Une tuile de 500 m × 500 m à densité maximale se calcule en moins de 50 ms (mesure affichée, seuil large en intégration continue).

## 8. Hors périmètre

- Modèles, matériaux, `MultiMeshInstance3D`, niveaux de détail (E3, E4).
- Lecture des fichiers `vegetation/chunk_<k>.json` (K4).

## 9. Livraison (24 octobre 2026, PR #40)

- `engine/scripts/vegetation_placer.gd` et `engine/tests/unit/test_vegetation_placer.gd` (19 vérifications, empreinte figée de la tuile de référence).
- **Écarts assumés :** la pente est lue sur une grille de 10 m de la tuile (hauteurs aux quatre coins de la maille) plutôt que par trois appels de `height_at` par arbre ; `y` reste `height_at.call(x, z)`. Le bruit ne sert que si `areas` est vide (format §7, couche absente ou vide). Densités par `kind` : valeurs du cahier, que le format ne fixe pas.
- Mesure : tuile de 500 m × 500 m à densité maximale (10 000 arbres) en 27 ms environ (seuil 50 ms, 150 ms en intégration continue).
