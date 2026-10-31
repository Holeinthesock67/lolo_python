# Lot U12 – Engine : faune par biome (extension de P11)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Engine : faune par biome (extension de P11) | GDScript | U5, P11 | Moyenne | Oui, après U5, **version 3.0** (issue #342) |

## 1. Objectif

**Version 3.0.** Étendre la faune de P11 aux biomes : marmottes et bouquetins en montagne, rennes en toundra, flamants et hérons en zone humide, mouettes au littoral, zèbres et girafes au loin en savane, dromadaires près des oasis, perroquets en jungle.

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §2, `docs/lots/LOT_U5_modele_biome_engine.md`, `docs/lots/LOT_P11_animaux.md`.
2. Code : `engine/scripts/fauna_placer.gd`, `engine/scripts/fauna_behaviour.gd`, `engine/scripts/fauna_renderer.gd` (P11).

## 3. Prérequis

U5 et P11 livrés.

## 4. Travail demandé

- Nouvelles espèces construites par code dans `fauna_renderer.gd` (silhouettes simples, moins de 200 triangles), comportements tirés de ceux de P11 (oiseau qui tourne, animal immobile, animal qui fuit).
- `fauna_placer.gd` : densités par biome lues dans `fauna` du thème 2.0, pondérées par les poids de biome ; grands animaux de savane seulement à plus de 150 m de la route.
- Budget `living(preset).animals` et `.birds` inchangé.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/fauna_placer.gd`, `engine/scripts/fauna_behaviour.gd`, `engine/scripts/fauna_renderer.gd`, leurs tests dans `engine/tests/unit/`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd` (U17), core, compilateur, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe.
2. Tuile `savanna` : girafes et zèbres seulement à plus de 150 m de la route ; tuile `temperate_grassland` : faune identique à P11.
3. Aucun animal sur la chaussée.
4. Budgets respectés en `low`.

## 8. Hors périmètre

Animaux qui traversent devant le cycliste, interactions.
