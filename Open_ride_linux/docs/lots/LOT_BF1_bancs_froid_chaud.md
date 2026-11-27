# Lot BF1 : bancs d'à-coups séparés à froid et à chaud

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série AC (à-coups) : bancs d'à-coups séparés à froid et à chaud, une image lente tolérée, modes de diagnostic froid-pilote et froid-godot | Python | PI1, PL1 | Petite | **Livré le 26 novembre** (PR #1094) |

Décision du 26/11 (le user a choisi « les deux lots ») : BF1 pour le banc, et un lot à part pour la préparation des
graphismes au premier lancement. Analyse complète : `statut/ACOUPS_CAUSE_GENERALE_2026-11-26.md` (dossier du projet).

## 1. Constat

- Toutes les grosses images des bancs à froid (rAC6, rJ25J, w24, pile #1066 c57b9746) sont des compilations de
  pipelines au premier dessin. Sur la GTX 1060 à cache vide, elles prennent 100 à 250 ms par pipeline, et jusqu'à
  0,7 s pour un seul. Le seuil de 150 ms au départ est donc intenable à froid, quel que soit le correctif.
- À chaud (caches gardés, comme le jeu au quotidien et les manches de la ligue), le même banc DB1 passe le départ
  à 55 ms : les 71 pipelines sortent du cache en 0,18 s.
- « Pire image 100 ms » sur toute la séance : la pile échouait sur **une seule** image de 101 à 139 ms en 18 min,
  et le verdict changeait d'un passage à l'autre.

## 2. Spécification

| # | Règle |
| --- | --- |
| BF1-1 | `perf_probe.hitch_checks(..., shaders=)` et `write_report(..., shaders=)` : `sim_bench.py` passe `--shaders`. |
| BF1-2 | À chaud (défaut) : départ jugé à `start_freeze_ms` (150 ms), inchangé. C'est le critère de la ligue. |
| BF1-3 | À froid : départ jugé à `cold_start_freeze_ms` (1 000 ms, écran qui reste animé). La pire image du chargement (avant `warmup_s` général) est relevée en INFO (« à-coups : chargement à froid »). |
| BF1-4 | Pire image de la séance : au plus `freeze_tolerated_count` (1) image entre `freeze_ms` (100) et `freeze_tolerated_ms` (200 ms) est tolérée et écrite dans la mesure. Deux images, ou une au-delà de 200 ms, échouent. |
| BF1-6 | Diagnostic : `--shaders froid-pilote` garde seulement le cache de Godot (shaders traduits en SPIR-V, celui qu'un export pourrait livrer) et vide ceux du pilote et des pipelines Vulkan ; `--shaders froid-godot` fait l'inverse. Les deux sont jugés comme « froid ». Deux bancs DB1 medium (après un banc chaud de la même tête) disent quelle étape coûte, avant de choisir la forme de la préparation des graphismes. |
| BF1-7 | Un passage `chaud` (ou `froid-pilote`, `froid-godot`) dont les caches gardés sont encore vides (premier passage d'une PR sur son cache séparé) est un premier lancement : ligne INFO « caches de shaders : vides avant ce passage », et jugé à froid (banc PC du 26/11 : chaud passé en premier, 16 s au chargement et 9,9 s au départ, 71 et 56 pipelines). |
| BF1-5 | Seuils dans `engine/tests/perf_targets.json` (`hitches`), avec leur raison. |

## 3. Fichiers

`engine/tests/perf_targets.json`, `engine/tests/perf_probe.py`, `engine/tests/sim_bench.py`,
`core/tests/test_perf_probe_hitches.py`, `core/tests/test_sim_bench_fiabilite.py`.

## 4. Critères d'acceptation

- Tests `test_perf_probe_hitches` verts en CI.
- Ne corrige aucun à-coup : la pile #1066 c57b9746 échoue encore à froid (6,5 s au départ en medium), jusqu'au lot
  de la préparation des graphismes.

## 5. Banc PC du 26/11 (r1094, DB1 medium, même dossier de caches, dans cet ordre)

| Passage | Chargement | Départ | Lecture |
| --- | --- | --- | --- |
| chaud (passé en premier, caches vides) | 16,2 s (71 pipelines) | 9,9 s (56) | en fait un premier lancement (BF1-7) |
| froid-pilote (cache de Godot plein, pilote vide) | 13,1 s (71) | 8,1 s (44 à 48) | le coût reste |
| froid-godot (pilote et pipelines Vulkan pleins, Godot vide) | 1,9 s (71) | 43 ms | OK |

Le coût du premier lancement est presque tout dans le pilote (création des pipelines). La traduction des shaders
par Godot coûte peu. Le « shader baker » de l'export ne suffirait donc pas : c'est la préparation des graphismes
(PG1, #1097) qui porte le gain, parce qu'elle fait créer les pipelines un par image.

## Livraison

Fusionné dans `main` le 26 novembre 2026 (PR #1094), relevé par la passe de doc du 27 novembre 2026 (statut précédent : « **En revue** (PR #1094) »).
