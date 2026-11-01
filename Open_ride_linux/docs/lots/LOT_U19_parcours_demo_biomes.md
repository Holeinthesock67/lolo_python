# Lot U19 – Parcours de démonstration fictifs, un par biome

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Parcours de démonstration fictifs, un par biome, portions non revêtues et côte | Python | U1 | Petite | Livré le 30 octobre (PR #623), **version 3.0** |

## 1. Objectif

**Version 3.0.** Fournir des parcours `.world` fictifs, générés par code, qui couvrent chaque biome du premier jalon et quelques transitions, pour tester tous les lots de rendu sans trace réelle et pour la recette U18 (risque 5 du plan : biomes invisibles sur des traces françaises). Le même générateur produit des portions non revêtues pour l'option « gravel ».

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §9, `docs/lots/LOT_U1_contrat_biomes.md`, `docs/lots/LOT_W15_monde_synthetique.md` (relief analytique).
2. Code : `core/src/openride_core/demo_world.py`, `core/src/openride_core/tools/fake_world.py`, `engine/tests/make_sim_world.py`, `engine/tests/make_osm_world.py`.

## 3. Prérequis

U1 livré.

## 4. Travail demandé

- Script `engine/tests/make_biome_world.py` : `--biome ID` (un biome partout) ou `--tour` (tous les biomes du premier jalon à la suite, 2 km chacun, transitions de 300 m), `--gravel` (un tiers de la route en `gravel` ou `dirt`), `--sea` (côte fictive le long du biome `coast`), relief analytique adapté (montagne pour `alpine`, collines pour `farmland`).
- Coordonnées fictives arrondies au degré entier, choisies hors de toute ville (latitude utile pour le climat et l'hémisphère, longitude sans importance) ; aucune trace réelle.
- Bâtiments, végétation et points d'intérêt fictifs de densité réaliste par biome ; manifeste avec `layers.biome`, `shares` et `forced` vide.
- Quatre parcours rangés par `openride-core demo-biomes` (ou option du lanceur) dans `~/OpenRide/Routes/demo-biomes/`.

## 5. Fichiers concernés

- **Nouveaux :** `engine/tests/make_biome_world.py`, `core/tests/test_biome_demo_world.py`.
- **Modifiés :** `core/src/openride_core/demo_world.py` (si la commande y vit), `core/src/openride_core/__main__.py`, `README.md`, `docs/OUTILS_DE_TEST.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** engine hors de `engine/tests/`, compilateur, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `pytest` passe dans `core/` ; les parcours produits sont valides pour tous les schémas (`verify` du compilateur quand il est installé).
2. `--tour` : chaque biome du premier jalon a une part entre 10 et 25 % ; somme des poids 255 partout.
3. `--gravel` : colonne `surface` présente, un tiers des points non revêtus à 5 % près.
4. Toutes les coordonnées écrites dans le dépôt sont des degrés entiers.
5. Deux générations : fichiers identiques au bit près.

## 8. Hors périmètre

Biomes lointains (ajout ultérieur, simple option), parcours réels.

## Livraison

PR #623, fusionnée le 30 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Oui, après U1, **version 3.0** (issue #349) ».
