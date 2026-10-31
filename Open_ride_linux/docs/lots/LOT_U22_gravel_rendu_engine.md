# Lot U22 – Option « gravel » : ruban de terre et de gravier, poussière et sons

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Gravel : ruban de terre et de gravier, poussière et sons | GDScript | U1, U19, P10 | Petite | Oui, après U19, **version 3.0** (issue #352) |

## 1. Objectif

**Version 3.0.** Montrer et faire entendre les portions non revêtues quand l'option « gravel » est active : ruban plus étroit aux bords irréguliers, texture de terre ou de gravier du thème, légère poussière par temps sec, crissement des pneus.

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §10, `docs/lots/LOT_U1_contrat_biomes.md` §4.4 et §4.5 (`surfaces`), `docs/lots/LOT_P10_sons_velo.md`, `docs/lots/LOT_P8_meteo_legere.md`.
2. Code : `engine/scripts/road_builder.gd`, `engine/scripts/route_data.gd`, `engine/scripts/sound_player.gd`, `engine/scripts/weather_particles.gd` (P8).

## 3. Prérequis

U1 livré ; U19 pour les données de test ; P10 pour les sons.

## 4. Travail demandé

- `route_data.gd` : lecture de la colonne `surface` (absente → `paved`).
- `road_builder.gd` : surface effective selon `config.gravel` (IPC 1.6) : `off` → bitume partout ; `auto` → colonne `surface` ; `compacted`, `gravel` ou `dirt` → toute la route dans cette surface (U-Q8). Portions non revêtues avec la couleur, la texture et la largeur de `surfaces` du thème (largeur par défaut : 3 m pour `dirt`, 3,5 m pour `gravel`, 4 m pour `compacted`), bords irréguliers par bruit déterministe, raccord en biseau de 5 m avec le bitume ; option coupée : ruban actuel partout.
- Poussière : quelques particules derrière la roue sur `dirt` et `gravel` par temps sec (P8 : pas de pluie), bornées par `living(preset)`.
- Son : crissement de gravier synthétisé, mêlé au son de roulement de P10, volume selon la vitesse.

## 5. Fichiers concernés

- **Nouveaux :** `engine/tests/unit/test_road_surface.gd`, `engine/tests/render/test_gravel_render.gd`.
- **Modifiés :** `engine/scripts/route_data.gd`, `engine/scripts/road_builder.gd`, `engine/scripts/weather_particles.gd`, `engine/scripts/sound_player.gd`, leurs tests, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd` (U17), core, compilateur, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Route sans colonne `surface` en `auto`, ou option coupée : maillage du ruban identique à aujourd'hui ; même route en `gravel` : ruban de gravier de bout en bout.
3. Portion `dirt` : largeur moyenne 3 m à 0,2 m près, raccords sans trou ni recouvrement.
4. Rendu : teinte moyenne de la portion à moins de 10 % de la couleur `surfaces.dirt` du thème.
5. Pluie active : aucune poussière.

## 8. Hors périmètre

Ornières en relief, flaques, boue qui salit le vélo.
