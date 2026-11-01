# Lot W15 – Monde ouvert synthétique pour les essais sans réseau

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Monde ouvert synthétique : relief analytique, base de routes, monde vivant et faux générateur | Python | W1 | Moyenne | Livré le 27 octobre (PR #314) |

## 1. Objectif

Permettre de développer et de tester core (W9) et engine (W10, W12) sans le vrai générateur ni réseau : un relief analytique, une base de routes synthétique au schéma de W3, un monde vivant écrit au format de W1, et un faux `openride-worldgen` qui parle le dialogue de W1 avec des carrefours scriptés. C'est aussi la doublure du banc simulé pour le monde ouvert.

## 2. À lire

1. `LOT_W1_contrat_monde_vivant.md` (en entier), `docs/contracts/worldgen_v1.md`, `docs/contracts/world_format_v1.md` (§13).
2. Code : `compiler/src/openride_compiler/elevation.py` (`SyntheticProvider`, `default_relief`), `core/src/openride_core/demo_world.py`, `engine/tests/make_sim_world.py`, `engine/tests/sim_bench.py`.

## 3. Prérequis

W1 livré. Ne dépend d'aucun autre lot W : le lot écrit lui-même les fichiers du format vivant. Le schéma de la base (W3 §4.1) est repris tel quel si W3 n'est pas encore livré.

## 4. Travail demandé

- **`worldgen/synthetic.py`** (compilateur, numpy autorisé) :
  - `synthetic_db(path, size_km=10, spacing_m=400, seed)` : base au schéma W3 avec une grille de routes déformée (sinusoïdes), classes variées, deux ponts, un tunnel, une impasse, un rond-point, quelques bâtiments, forêts et un lac ; coordonnées autour d'un point fictif en mer (aucun lieu réel) ;
  - `write_live_world(dir, script)` : monde vivant valide (manifeste, `live.json`, parties de route, tuiles proches et lointaines, couches par carré, `junctions.json`) depuis un scénario `script` : longueur, carrefours (position, branches, pentes), relief analytique ;
  - `fake_worldgen` : point d'entrée `openride-worldgen-fake` qui lit le dialogue W1 sur l'entrée standard, répond `status` puis `ready`, prolonge la route de façon scriptée à chaque `progress` (horizon de 3 km), honore `choose` avant le verrouillage, et peut simuler `offline`, `missing` et un plantage (options) ;
- **Banc simulé :** `engine/tests/make_sim_world.py --live` écrit un monde vivant synthétique de 20 km, pour que `sim_bench.py` mesure le rendu du monde ouvert (W10).
- Tout est déterministe pour une graine donnée ; aucun accès réseau.

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/worldgen/synthetic.py`, `compiler/tests/test_world_synthetic.py`.
- **Modifiés :** `compiler/pyproject.toml` (point d'entrée `openride-worldgen-fake`), `engine/tests/make_sim_world.py` (option `--live`), `docs/OUTILS_DE_TEST.md`, `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest` passe dans `compiler/`.
2. Chaque fichier du monde vivant écrit est valide pour son schéma (W1) ; parties de route lisibles par `route.py` une fois assemblées.
3. Faux générateur lancé en sous-processus : `open` → `status` → `ready` → `revision` ; `progress` de 0 à 10 km : horizon de 3 km tenu ; `choose` honoré avant le verrouillage, `branch_locked` après ; options `offline`, `missing`, plantage observables.
4. Base synthétique : requêtes par emprise valides (mêmes résultats qu'un filtre en Python pur) ; aucun lieu réel.
5. `make_sim_world.py --live` écrit un monde vivant de 20 km valide.

## 8. Hors périmètre

Le vrai générateur (W8).

## Livraison

PR #314, fusionnée le 27 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Oui, après W1 (issue #270) ».
