# Lot CT10 – Effets cartoon dans l'engine

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`.

## 1. Objectif

Coder dans Godot les effets de la charte CT9 validée, pilotés par les champs du contrat CT1, avec un coût mesuré en `low`, `medium` et `high`.

## 2. À lire

1. `docs/5.0/PLAN_SERIE_CT.md` (décisions du propriétaire du 29 octobre), `docs/SPECIFICATION_GENERALE.md` §6.1 et §7.1, `docs/contracts/ipc_v1.md`.
2. Charte `docs/5.0/CHARTE_CARTOON_CT9.md` et maquettes validées ; code `engine/scripts/bots_view.gd`, `avatar_view.gd`, `render_quality.gd`, `quality_presets.gd`.

## 3. Prérequis

CT9 validé par le propriétaire ; CT2 à CT8 livrés (champs remplis par le core).

## 4. Travail demandé

- Scène et scripts du mode (`tactical_view.gd`), instanciés seulement quand `state.mode` vaut `TACTICAL`.
- Matériaux cel shading et contour du mode, sans toucher aux matériaux du classique ni du Cyber-Rogue.
- Chaque effet de la charte, avec ses niveaux `low`, `medium` et `high` et le réglage « Effets ».
- **Mesure obligatoire** : banc simulé (sonde X13) en `low`, `medium` **et** `high` sur la GTX 1060, avant et après, sous les seuils d'X2 (55 images/s en `low`) ; captures des six scènes de CT9 montrées au propriétaire avant fusion.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/tactical_view.gd`, shaders et scènes du mode, tests Godot.
- **Modifiés :** `main.gd` (instanciation), ce cahier, `00_INDEX.md`.
- **Interdits :** le core, le rendu des autres modes.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Tests Godot (`run_engine_tests`) et `visual_check` passent.
2. Mesure en `low`, `medium` et `high` jointe à la PR, dans les seuils.
3. Captures validées par le propriétaire avant fusion.
4. Règles de confort tenues (fréquence mesurée, opacité).

## 8. Hors périmètre

HUD et menus (CT11).
