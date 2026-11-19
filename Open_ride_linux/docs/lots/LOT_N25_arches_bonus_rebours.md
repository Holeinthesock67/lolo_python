# Lot N25 – Arches de bonus comptées à rebours

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 1.x série N : arches de bonus franchies à rebours après un demi-tour | Python | N17 | Petite | **Livré le 17 novembre** (PR #888), **version 1.x** |

## 1. Objectif

Audit du décor dans les deux sens (8 novembre, point 7) : après un demi-tour (N17), les arches de bonus restaient
affichées mais le core ne comptait que les franchissements vers l'avant (`ArchSchedule.crossed`, `s <= s_prev → 0`).
Choix du propriétaire le 8 novembre : **les compter à rebours** (plutôt que les cacher).

## 2. Travail fait

- `powerups.ArchSchedule.passes(s_prev, s)` : arches franchies dans un sens ou dans l'autre, `(indice, tour)` ;
  `crossed` en donne le nombre (inchangé vers l'avant).
- `classic.ClassicRace.step` : une arche rapporte un bonus une seule fois par tour, quel que soit le sens du premier
  passage ; un aller-retour par demi-tours sous la même arche ne rapporte rien de plus. La distance du pas (`ds`,
  fondu du Rouleau compresseur) compte aussi à rebours.
- Aucun changement de contrat ni d'engine : les arches sont déjà affichées à rebours, bandeau lisible des deux côtés
  depuis N21.

## 3. Critères d'acceptation

1. Tests du core au vert (`test_powerups.py` : `test_arches_crossed_backwards_after_u_turn`,
   `test_classic_race_pays_each_arch_once_in_either_direction`).
2. Pas de capture : rien ne change à l'écran (règle seulement).

## Livraison

Fusionné dans `main` : PR #888 (17 novembre). Statut relevé par la mise à jour de la documentation du 19 novembre 2026.
