# Lot VD5 – Bâtiment et tribunes

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : salle, tribunes, public, éclairage et pelouse centrale | GDScript | VD2 | Grande | Prêt (version 4.0) |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Plan validé par le propriétaire le 6 novembre (lot VD0).

## 1. Objectif

Construire le décor unique du vélodrome, une salle couverte (décision du propriétaire du 6 novembre), sans ciel, météo, jour et nuit ni saison, à partir de la couche `venue`, sans terrain, végétation ni biome, sous 70 % du budget GPU en salle.

## 2. À lire

§7.2 et §7.3 du plan ; `engine/scripts/world_streamer.gd`, `crowd_renderer.gd`, `quality_presets.gd`.

## 3. Travail demandé

- Salle procédurale (murs, toit à arcs, rampes émissives), tribunes en gradins, pelouse centrale (bancs, home trainers d'échauffement), tableau d'affichage.
- Public par `MultiMesh` (1 000, 3 000, 6 000 selon le préréglage), aucune création pendant l'épreuve.
- Couches du monde ouvert et de la route coupées quand `venue.kind = velodrome` (terrain, végétation, biome, OSM, eau, circulation, faune).
- Captures `low`, `medium`, `high` validées par le propriétaire.

## 4. Critères d'acceptation

1. Salle couverte sous 70 % du budget (environ 4,2, 8,4 et 9,8 ms) au banc.
2. Aucun à-coup au-dessus du garde-fou de `perf_targets.json`.
3. Routes existantes inchangées.

## 5. Fichiers touchés

- `world_streamer.gd`, `crowd_renderer.gd`, nouveaux scripts `velodrome_*.gd`, `quality_presets.gd` (clé `velodrome_crowd`).

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 6, 12 et 14 ms) et ses captures sont validées par le propriétaire avant la fusion.
