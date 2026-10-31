# Lot U17 – Intégration des biomes dans la scène principale

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Intégration des biomes dans la scène principale, budgets par préréglage | GDScript | U5 à U15, U19, U22 | Grande | Non : interne (rendu), **version 3.0** (issue #347) |

## 1. Objectif

**Version 3.0.** Brancher dans la scène principale tout ce que les lots U5 à U15 et U22 ont livré en modules : modèle de biome, terrain multi-biome, végétation, détails de sol, mer, atmosphère, sons, faune, saisons, variantes et ruban de gravel ; régler les budgets pour tenir 55 images/s en `low` sur la GTX 1060.

**Lot interne (rendu).**

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` (en entier), cahiers U5 à U15 et U22, `docs/lots/LOT_P17_integration_decor_complet.md` et `docs/lots/LOT_P19_integration_jour_nuit_saisons.md` (même rôle pour la série P).
2. Code : `engine/scripts/main.gd`, `engine/scripts/world_streamer.gd`, `engine/scripts/osm_streamer.gd`, `engine/scripts/terrain_tiles.gd`, `engine/scripts/quality_presets.gd`, `engine/tests/sim_bench.py`.

## 3. Prérequis

U5 à U15 livrés (U8, U9, U10 et U12 peuvent suivre dans un second temps, d'après l'ordre du plan §8) ; U19 pour les parcours d'essai ; U22 pour le gravel.

## 4. Travail demandé

- Création du modèle de biome au chargement du parcours, transmis aux flux de tuiles et aux couches OSM ; chargement des tableaux de textures avant le départ (écran de chargement de N6), jamais pendant la séance.
- Mise à jour par image : biome sous la caméra (atmosphère, sons), sans allocation ; tout le reste au chargement des tuiles.
- Budgets par préréglage ajustés au banc simulé (`engine/tests/sim_bench.py`) avec un scénario par biome du premier jalon ; ligne `[perf-rendu]` complétée de la mémoire vidéo estimée des textures du décor.
- Parcours sans couche `biome` et thème 1.x : rendu identique à la 2.0.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/main.gd`, `engine/scripts/world_streamer.gd`, `engine/scripts/osm_streamer.gd`, `engine/scripts/terrain_tiles.gd`, `engine/scripts/quality_presets.gd`, `engine/tests/sim_bench.py` et ses scénarios, `engine/tests/run_visual_tests.sh` (une capture par biome du premier jalon), `README.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** core, compilateur, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. Toutes les suites passent, rendu et bout en bout compris.
2. Banc simulé, `low`, scénario de chaque biome du premier jalon : 55 images/s ou plus en moyenne, p99 sous 25 ms (mesure de la machine de test, à confirmer sur le PC à la recette U18).
3. Changement de biome en roulant : aucune saccade de plus de 33 ms au chargement d'une tuile.
4. Parcours de la 2.0 : captures visuelles identiques.

## 8. Hors périmètre

Recette sur le matériel (U18).
