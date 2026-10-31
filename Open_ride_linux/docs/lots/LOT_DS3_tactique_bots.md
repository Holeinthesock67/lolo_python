# Lot DS3 – Tactique de survie des bots

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série DS : tactique de survie des bots (sprint avant l'arche selon la réserve W′, économie quand ils sont à l'abri) | Python | DS1 | Moyenne | **Livré le 31 octobre** (version 3.0) |

Série DS (mode « Dernier survivant », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/3.0/PLAN_SERIE_DS.md`.

## 1. Objectif

Donner aux bots à profil une règle de course à l'élimination : sprinter avant l'arche quand ils sont menacés, s'économiser dans les roues quand ils sont loin du dernier, sans jamais d'élastique.

## 2. À lire

`docs/3.0/PLAN_SERIE_DS.md` §3 ; `core/src/openride_core/bots.py` (`ProfileBot`, roue suivie de l'AS1) ; `core/src/openride_core/rogue/wbal.py` ; `docs/lots/LOT_Y10_comportement_bots_core.md` (ce que Y10 ajoutera plus tard).

## 3. Travail demandé

- Danger : à moins de 400 m de l'arche (seuil tiré entre 250 et 400 m), parmi les deux derniers en course ou à moins de 2 s du dernier : puissance de sprint du profil (120 à 150 % de la CP) tant que la réserve W′ dépasse 10 %.
- Économie : à plus de 5 s du dernier, 95 % de la CP et roue suivie.
- La règle ne s'applique qu'au mode `survivor` ; les autres modes gardent la stratégie T12.

## 4. Critères d'acceptation

1. Sur 100 courses simulées (même niveau pour tous), l'ordre d'élimination n'est pas toujours le même ; avec un écart de niveau large, le bot le plus faible sort le premier dans au moins 80 % des cas.
2. Aucun bot ne ralentit à cause de l'écart avec le joueur (test négatif).
3. La réserve W′ d'un bot ne descend jamais sous 0.

## Livraison

Livré le 31 octobre 2026 (branche `claude/project-thread-ewr5b6-ds3`, après DS1) : `core/src/openride_core/survivor.py` (`SurvivorRace.survival_hints`, `sprint_from_m`, graine `seed`), `core/src/openride_core/bots.py` (champ `survival` de `ProfileBot`, fraction de sprint `survival` de chaque profil : grimpeur 1,25, rouleur 1,30, sprinteur 1,50, diesel 1,20 × CP), `core/tests/test_survivor_tactics.py`. La séance pose `bot.survival` à chaque pas au lot DS2 ; hors du mode, `survival` vaut `None` et rien ne change.

Écart assumé : un bot qui a déjà passé l'arche en cours vise la suivante ; un bot entre 2 et 5 s du dernier n'est ni menacé ni à l'abri et garde la stratégie T12.
