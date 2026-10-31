# Lot X18 – Contrôle d'apparition et comparaison avant/après

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : Contrôle d'apparition (« pop ») et comparaison avant/après (outils livrés par S1) | Python + GDScript | S1 | Petite | Non : livré par le lot S1 ; issue #216 |

## 1. Objectif

S1 (culling) doit prouver qu'aucune réduction ne change l'image ni ne fait apparaître d'objet (« pop »). Les séries P et U en ont besoin aussi.

## 2. Répartition (28 octobre)

Le fil S1 livre dans sa PR (#465 et suivantes), à la demande du coordinateur : les lignes `[test] pop clé=… dist=…` (tuile ou case d'arbres instanciée déjà dans le champ et plus près que la distance de fondu) et l'échec du banc au-delà de 0 ; les captures tous les N mètres (`sim_bench.py --every-m`) ; la colonne `culled_near` de la sonde ; un monde de banc à épingles ; `compare_captures.py` générique (deux dossiers, captures au même nom, seuil, rapport HTML).

Ce lot ne garde que ce qui sert aux autres séries : documentation commune, branchement de `compare_captures.py` dans X14 (comparateur des bancs) et X20 (références), et un test qui vérifie le comptage des `pop` sur un journal fabriqué.

## 3. Fichiers

- **Modifiés :** `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`.
- **Livrés par S1 :** `engine/tests/compare_captures.py`, `sim_bench.py --every-m`, `perf_probe.gd` (`culled_near`).

## 4. Critères d'acceptation

1. Après S1 : `sim_bench.py --every-m 50` sur `main` puis sur la branche, `compare_captures.py` sur les deux dossiers : rapport lisible, aucun `pop`.

## 5. Livraison

Livré par le lot S1 pour la partie outil ; ce cahier ne fait que relier.
