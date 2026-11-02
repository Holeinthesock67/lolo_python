# Lot GP8 – Engine : HUD, avertissements et bilan

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : case d'objet et roulette, place et tours, bande de course, choix de voie, avertissements et bilan | GDScript | GP2, GP6 | Moyenne | Prêt (version 4.0 proposée) |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Afficher le HUD et le bilan du mode selon les maquettes validées.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` §8.2 ; maquettes GP6 ; `engine/scripts/hud_view.gd`, `engine/scripts/summary_view.gd`.

## 3. Travail demandé

- Case d'objet, place, tours et écart, bande de course, trois traits de voie, avertissements avec flèche et contour d'écran.
- Bilan : place, objets lancés, reçus et esquivés, temps gagné et perdu par objet.

## 4. Critères d'acceptation

1. Captures en 1680×1050 et 1024×600, en `low`, `medium` et `high`, validées par le propriétaire.
2. Tests de modèle du HUD et du bilan (valeurs absentes, 12 coureurs).
