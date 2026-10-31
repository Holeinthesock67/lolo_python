# Lot L1 – Maillage des bâtiments extrudés (sans affichage)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Maillage des bâtiments extrudés, sans affichage (prépare E4) | GDScript | K1 (livré) | Petite | **Livré le 24 octobre** (PR #64, issue #53) |

## 1. Objectif

Préparer le rendu des bâtiments du lot E4 (SRS §8, « Bâtiments ») : transformer les bâtiments d'un tronçon `buildings/chunk_<k>.json` en tableaux de maillage (sommets, normales, indices, couleurs) prêts pour un `ArrayMesh`, dans un script GDScript pur testé sans écran. E4 n'aura plus qu'à créer le nœud et le matériau.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/SRS_v1.1.md` §8 (paragraphe « Bâtiments ») ; `docs/contracts/world_format_v1.md` §3 (repère : x est, y haut, z sud), §6 (couche bâtiments), §9 (palette `buildings.walls` et `buildings.roofs`) ; `docs/contracts/world/buildings.schema.json`.
3. Code : `engine/scripts/theme_loader.gd`, `engine/themes/default/theme.json` ; après K4 : `engine/scripts/osm_layers.gd` (forme des éléments lus, lecture seule) ; `engine/scripts/erg_view_model.gd` (style d'un script sans nœud).

## 3. Prérequis

Lot K1 livré (le test se dépose dans `engine/tests/unit/`). K4 n'est pas nécessaire : le script reçoit les bâtiments sous forme de tableaux de dictionnaires, au format du §6.

## 4. Travail demandé

Nouveau `engine/scripts/building_mesh.gd` (`extends RefCounted`, sans `class_name`, chargé par `preload`), qui ne crée aucun nœud :

```gdscript
static func build(buildings: Array, theme: Dictionary) -> Dictionary
# {vertices: PackedVector3Array, normals: PackedVector3Array, colors: PackedColorArray,
#  indices: PackedInt32Array, built: int, skipped: int, errors: PackedStringArray}
```

- **Murs :** un quadrilatère par arête de `outer` et de chaque trou, de `base_y` à `base_y + height_m`, normales horizontales tournées vers l'extérieur du bâtiment (vers l'intérieur de la cour pour un trou). Sommets non partagés entre deux murs (arêtes vives).
- **Toit plat :** triangulation par `Geometry2D.triangulate_polygon` (SRS §8 : pas de bibliothèque externe). Les polygones avec trous sont traités à part : par exemple, couture de chaque trou à l'anneau extérieur par un pont avant triangulation, ou triangulation de Delaunay puis élimination des triangles dont le centre tombe hors de `outer` ou dans un trou. La méthode est libre et décrite dans le rapport.
- **Sens :** les triangles sont orientés pour être vus de l'extérieur (convention de Godot) ; un anneau `outer` reçu dans le sens horaire est retourné, et ce retournement est compté.
- **Couleurs :** mur et toit choisis dans `buildings.walls` et `buildings.roofs` du thème, de façon stable à partir de `id` (hachage de la chaîne, jamais `randi()`) : le même bâtiment a la même couleur à chaque séance.
- **Toits `gabled` :** traités comme `flat` en v1 (format §6), et comptés à part dans le rapport.
- **Robustesse :** anneau de moins de 3 points, aire nulle, triangulation impossible ou `height_m` non positif : bâtiment ignoré (`skipped`, message dans `errors`), jamais une erreur Godot.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/building_mesh.gd`, `engine/tests/unit/test_building_mesh.gd`.
- **Modifiés :** `engine/tests/README.md` (une ligne), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, scripts de rendu d'E1, `run_engine_tests.sh`.

## 6. Modifications de contrat autorisées

Aucune. Si un cas du §6 n'est pas tranché (anneau auto-intersecté, trou qui touche le bord), choisir « bâtiment ignoré » et le signaler.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Boîte de 10 m × 8 m × 6 m : 4 murs, aire des toits égale à 80 m² à 0,01 près, sommets du toit tous à `base_y + 6`, normales des murs unitaires et tournées vers l'extérieur (produit scalaire avec le vecteur centre → milieu du mur positif).
3. Bâtiment en L (6 sommets, concave) et cour intérieure (un trou de 4 m × 4 m dans 20 m × 20 m) : aire du toit égale à aire(`outer`) − aire(trous) à 0,01 m² près ; aucun triangle de toit dont le centre tombe dans le trou.
4. Un anneau horaire donne le même maillage (à l'ordre près) que l'anneau antihoraire.
5. Déterminisme : deux appels identiques donnent des tableaux égaux ; la couleur d'un `id` donné est figée dans le test.
6. Cinq cas invalides (2 points, aire nulle, `height_m` 0, points non numériques, anneau croisé) : `skipped` = 5, aucune erreur Godot dans la sortie.
7. 500 bâtiments rectangulaires se maillent en moins de 100 ms (mesure affichée, seuil large en intégration continue).

## 8. Hors périmètre

- Création du `MeshInstance3D`, matériaux, ombres, niveaux de détail (E4).
- Toits à deux pans (`gabled`, `roof_dir_deg`) : évolution future (SRS §14).
- Lecture des fichiers `buildings/chunk_<k>.json` (K4).

## 9. Livraison (24 octobre 2026, PR #64)

- `engine/scripts/building_mesh.gd` : module pur de maillage 3D des bâtiments (murs extrudés à normales horizontales sortantes, toits plats triangulés avec normales vers le haut, découpe des cours intérieures, couleurs par hachage déterministe de `id`).
- `engine/tests/unit/test_building_mesh.gd` : 18 vérifications sans écran (15 ms pour 500 bâtiments).
- Intégration continue GitHub Actions verte.
