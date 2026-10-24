# Lot L2 – Maillage de l'eau : rivières en ruban et lacs avec îles (sans affichage)

## 1. Objectif

Préparer l'eau du sprint 6 (SRS §13) : transformer les éléments de `water/chunk_<k>.json` (format `.world` §8) en tableaux de maillage, sans affichage. Les cours d'eau deviennent des rubans qui suivent leur polyligne ; les plans d'eau, des surfaces planes à `level_y`, îles comprises.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_L1_maillage_batiments.md` (même démarche, triangulation des polygones à trous).
2. `docs/contracts/world_format_v1.md` §3 (repère) et §8 (eau : `lines` en points (x, z, y), `width_m` à 2 m par défaut, `areas` avec `level_y`) ; `docs/contracts/world/water.schema.json`.
3. Code : `engine/scripts/route_data.gd` (construction d'un ruban le long d'une polyligne, à titre d'exemple) ; après K4 : `engine/scripts/osm_layers.gd` (lecture seule).

## 3. Prérequis

Lot K1 livré. L1 n'est pas nécessaire : si les deux lots ont besoin de la même triangulation à trous, L2 garde sa propre fonction et le rapport le signale (mise en commun après la fusion des deux).

## 4. Travail demandé

Nouveau `engine/scripts/water_mesh.gd` (`extends RefCounted`, sans `class_name`), sans nœud :

```gdscript
static func build_lines(lines: Array) -> Dictionary
static func build_areas(areas: Array) -> Dictionary
# chacune : {vertices, normals, uvs, indices, built, skipped, errors}
```

- **Rubans :** pour chaque point, deux sommets à ± `width_m / 2` perpendiculairement à la direction locale (moyenne des segments voisins), à l'altitude `y` du point plus 0,05 m ; `width_m` absent : 2 m. Les UV portent la distance cumulée le long de la ligne (u) et la position en travers (v de 0 à 1), pour un futur défilement de l'eau.
- **Coudes serrés :** la demi-largeur appliquée au coude est bornée (au plus 2 × `width_m / 2`) pour éviter les pointes ; points confondus consécutifs ignorés.
- **Plans d'eau :** triangulation de `outer` moins les `holes` (îles), surface plane à `level_y`, normales vers le haut, UV = (x, z) en mètres.
- **Robustesse :** ligne de moins de 2 points distincts, anneau invalide, `level_y` absent ou non numérique : élément ignoré et compté, jamais une erreur Godot ; `kind` inconnu accepté (le maillage ne dépend pas de `kind`).

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/water_mesh.gd`, `engine/tests/unit/test_water_mesh.gd`.
- **Modifiés :** `engine/tests/README.md` (une ligne), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, scripts de rendu d'E1, `run_engine_tests.sh`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Rivière droite de 100 m, `width_m` 6 : aire du ruban égale à 600 m² à 1 % près ; tous les sommets à ± 3 m de l'axe ; u final égal à 100.
3. Rivière en angle droit : aucun sommet à plus de `width_m` de la polyligne ; aucun triangle retourné (normales toutes vers le haut).
4. Lac de 100 m × 50 m avec une île de 10 m × 10 m : aire égale à 4 900 m² à 0,1 m² près ; tous les sommets à `level_y` ; aucun triangle sur l'île.
5. `width_m` absent : largeur de 2 m.
6. Cas invalides (ligne d'un point, points tous confondus, anneau de 2 points, `level_y` texte) : comptés dans `skipped`, aucune erreur Godot.
7. Déterminisme : deux appels identiques donnent des tableaux égaux.

## 8. Hors périmètre

- Matériau et shader de l'eau, reflets, sons des rivières (sprint 6).
- Creusement du terrain sous la rivière.

## 9. Livraison (24 octobre 2026, PR #65)

- `engine/scripts/water_mesh.gd` : maillage 3D des cours d'eau (rubans à largeur et normales contrôlées) et plans d'eau triangulés avec découpe des îles.
- `engine/tests/unit/test_water_mesh.gd` : 12 vérifications sans écran.
- Intégration continue GitHub Actions verte.
