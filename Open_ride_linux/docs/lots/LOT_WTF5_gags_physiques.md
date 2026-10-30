# Lot WTF5 – Engine : gags physiques du mode WTF

Série WTF (mode « What the fuck », demande du propriétaire du 29 octobre 2026). Plan de la série : `docs/2.0/PLAN_SERIE_WTF.md`.

## 1. Objectif

Afficher les événements qui touchent la route et le vélo : gravité (Lune grise, bonds, Jupiter rougeâtre), monde à l'envers (caméra retournée en douceur), route qui s'effondre (tronçons qui tombent derrière), fromage géant, tempête de vaches et recul visuel.

## 2. Travail demandé

Scène du mode chargée seulement quand `state.wtf` est présent ; un script par gag, piloté par `wtf.event` ; transitions de 1 s au moins ; niveaux `low`, `medium` et `high`.

## 3. Critères d'acceptation

1. Tests Godot et `visual_check` passent.
2. Banc simulé en `low`, `medium` **et** `high` sur la GTX 1060, avant et après, captures montrées au propriétaire.
