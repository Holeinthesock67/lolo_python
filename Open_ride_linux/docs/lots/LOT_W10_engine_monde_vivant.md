# Lot W10 – Engine : lecture du monde vivant, amorces de branches, recentrage de l'origine

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Engine : lecture du monde vivant, amorces de branches, recentrage tous les 10 km | GDScript | W1 (W15 pour les tests) | Grande | Livré le 27 octobre (PR #422) |

## 1. Objectif

Afficher un monde ouvert avec le même rendu qu'un parcours compilé : route lue par parties qui s'ajoutent ou se remplacent, terrain et couches rangés par carré, amorces de 500 m des branches aux carrefours, et recentrage de l'origine tous les 10 km pour garder la précision des flottants 32 bits.

## 2. À lire

1. `LOT_W1_contrat_monde_vivant.md` §4.2 et §4.3, `docs/contracts/world_format_v1.md` (§13 du monde vivant), `docs/2.0/PLAN_SERIE_W.md` §3.4.
2. Code : `engine/scripts/route_data.gd`, `world_streamer.gd`, `osm_streamer.gd`, `osm_layers.gd`, `road_builder.gd`, `terrain_tiles.gd`, `tree_renderer.gd`, `camera_follow.gd`, `main.gd`, `ipc_client.gd`.

## 3. Prérequis

W1 livré. W15 fournit un monde vivant synthétique pour les tests sans générateur.

## 4. Travail demandé

- **`route_data.gd` :** chargement d'un dossier `live` (manifeste) : parties `route/part_<k>.json` assemblées en colonnes ; `reload_from_part(k)` remplace les parties à partir de `k` (lecture en tâche de fond, échange sur le fil principal) ; mêmes fonctions `sample`, `sample_point`, `sample_heading_deg` qu'aujourd'hui.
- **Révision :** à chaque nouveau `state.open_world.rev`, relecture de `live.json` puis des parties depuis `changed_from_part` et de `junctions.json` ; les tronçons de ruban touchés sont reconstruits, les autres gardés.
- **Couches par carré :** `osm_streamer.gd` et le placement des arbres lisent `<couche>/tile_<ix>_<iz>.json` (coordonnées relatives au coin de tuile, W1 §4.2) quand le monde est `live`, avec la même fenêtre de 1 500 m que le terrain proche ; les mondes compilés gardent les `chunk_<k>.json`.
- **Amorces :** pour chaque carrefour de `junctions.json` à moins de 1 500 m, ruban de route de 500 m par branche non suivie (même matériau, même `road_builder.gd`), fondu en transparence sur ses 100 derniers mètres ; supprimé quand le carrefour est dépassé.
- **Recentrage :** quand la caméra s'éloigne de plus de `recenter_m` (10 km, reçu par la configuration) de l'origine de rendu, toutes les positions du monde affiché sont décalées d'un multiple de 1 000 m (nœud racine déplacé, données en flottants 64 bits retranchées avant conversion en `Vector3`) ; aucune saute visible, aucun fichier modifié.
- Pas de `class_name` ; code de calcul séparé de l'affichage pour les tests sans écran.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/route_data.gd`, `world_streamer.gd`, `osm_streamer.gd`, `osm_layers.gd`, `tree_renderer.gd` (lecture par carré), `main.gd` (branchement), `ipc_client.gd` (champ `open_world`, message `world_status`).
- **Nouveaux :** `engine/scripts/live_world.gd` (révisions, carrefours, recentrage, sans affichage), `engine/tests/unit/test_live_world.gd`, `engine/tests/unit/test_route_parts.gd`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe (Godot 4.3 sans écran), tests existants compris.
2. Vecteurs de `route_test_vectors.json` découpés en parties : `sample` donne les mêmes valeurs à 1e-6 près.
3. Remplacement depuis la partie 3 : parties 0 à 2 inchangées (même objet), parties suivantes relues.
4. Recentrage : un point du monde garde sa position à l'écran à 1 mm près avant et après ; en flottants 32 bits, à 60 km de l'origine, l'erreur de position reste sous 1 mm.
5. Bâtiment d'un fichier de carré : position absolue = coin de tuile + coordonnées relatives.
6. Au banc simulé (`engine/tests/sim_bench.py`) sur le monde vivant synthétique de W15 : temps d'image comparables à un parcours compilé de même contenu (écart sous 5 %).

**Sur le PC (le propriétaire) :** contrôle visuel des amorces et absence de saute au recentrage (W16).

## 8. Hors périmètre

Menu globe (W11), HUD du carrefour (W12).

## Livraison

PR #422, fusionnée le 27 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Non : interne (rendu) (issue #265) ».
