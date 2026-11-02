# Lot GP7 – Engine : boîtes, objets, projectiles, effets et sons

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : rendu des boîtes, des objets et des projectiles, effets de glissade, d'averse et de super-forme, sons | GDScript | GP2, GP6 | Grande | Prêt (version 4.0 proposée) |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Afficher ce que le core envoie dans `state.gp` et `gp_hit`, selon les maquettes validées.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` §8 ; maquettes GP6 ; `engine/scripts/segment_markers.gd`, `engine/scripts/bots_view.gd`, `engine/scripts/sound_player.gd` ; scène des gags WTF (WTF5, WTF6) pour la réserve d'instances.

## 3. Travail demandé

- Boîtes en `MultiMesh`, deux rangées au plus dans la scène ; réserve d'instances par sorte d'objet, aucune création en course.
- Effets par préréglage : `low` sans particules, `medium` limité, `high` complet.
- Sons : roulette, lancer, glissade, averse, sonnette, klaxon.

## 4. Critères d'acceptation

1. Banc au pire cas (départ, tous les bots, six boîtes, douze objets) en `low`, `medium` et `high` : budgets GPU de 6, 12 et 14 ms tenus.
2. Captures validées par le propriétaire avant fusion.
3. Tests de modèle sans scène (objet affiché à la bonne voie, disparition hors trame).
