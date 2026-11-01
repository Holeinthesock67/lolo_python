# Lot WTF5 – Engine : gags physiques du mode WTF

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série WTF : engine, gags physiques (gravité, monde à l'envers, route qui s'effondre, fromage, tempête) | GDScript | WTF2, WTF4 | Grande | En PR le 31 octobre (version 2.0), captures et banc à faire sur le PC |

Série WTF (mode « What the fuck », demande du propriétaire du 29 octobre 2026). Plan de la série : `docs/2.0/PLAN_SERIE_WTF.md`.

## 1. Objectif

Afficher les événements qui touchent la route et le vélo : gravité (Lune grise, bonds, Jupiter rougeâtre), monde à l'envers (caméra retournée en douceur), route qui s'effondre (tronçons qui tombent derrière), fromage géant, tempête de vaches et recul visuel.

## 2. Travail demandé

Scène du mode chargée seulement quand `state.wtf` est présent ; un script par gag, piloté par `wtf.event` ; transitions de 1 s au moins ; niveaux `low`, `medium` et `high`.

## 3. Critères d'acceptation

1. Tests Godot et `visual_check` passent.
2. Banc simulé en `low`, `medium` **et** `high` sur la GTX 1060, avant et après, captures montrées au propriétaire.

## 4. Livraison (31 octobre, en PR)

- `engine/scripts/wtf/wtf_scene_model.gd` (sans nœud) : voile de couleur (Lune grise, Jupiter rougeâtre, tempête sombre), bonds sur la Lune (`hop_m`), roulis de 180° du monde à l'envers, tronçons de route qui tombent derrière le front de l'effondrement, meule de fromage qui roule (sur le cycliste quand il est écrasé), tornade de vaches qui se remplit (8, 16 ou 24 vaches en `low`, `medium`, `high`).
- `engine/scripts/wtf/wtf_scene.gd` : formes simples aux couleurs des maquettes, sans ombres, créées à la première utilisation puis réutilisées ; roulis et vues imposées amenés en 1 s ; rien n'existe hors mode WTF. Branché dans `main.gd` après la caméra de la séance.
- Tests : `engine/tests/unit/test_wtf_scene.gd` (route droite factice).
- Reste : captures en `low`, `medium` et `high` et banc sur la GTX 1060 (file du PC).
