# Lot GP4 – Voiture d'équipe et Furtif

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : Voiture d'équipe (remorquage dans l'abri d'un véhicule d'AS6) et Furtif (Échappée de TT4 plus vol d'objet) | Python + GDScript | GP1, AS6, TT4 | Petite | Prêt (version 4.0 proposée) |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Ajouter les deux objets qui reposent sur d'autres séries : la Voiture d'équipe, qui réutilise le véhicule et l'abri du lot AS6, et le Furtif, qui reprend l'Échappée (`breakaway`) de TT4 et ajoute le vol de l'objet du coureur devant.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` §3 ; cahier AS6 ; plan TT (`docs/4.0/PLAN_SERIE_TT.md`, lot TT4).

## 3. Travail demandé

- Voiture d'équipe : 6 s à 1,5 × la vitesse d'équilibre, invincible, tirée seulement à plus de 15 s du premier ; véhicule et ressenti d'abri d'AS6 (supplément négatif seulement, borné).
- Furtif : effet `breakaway` de la table, 10 s, plus vol de l'objet du coureur devant à moins de 50 m.
- Les deux objets entrent dans le catalogue par ce lot : avant lui, ils n'existent pas, et le tirage de GP1 répartit leurs poids sur les autres objets, comme pour un objet désactivé (aucun test spécial dans le code).

## 4. Critères d'acceptation

1. Tests : gain de la voiture d'équipe à ± 10 % du tableau du plan ; vol refusé sans coureur à moins de 50 m.
2. Ressenti : supplément de pente de la voiture toujours négatif ou nul, rampes respectées.
