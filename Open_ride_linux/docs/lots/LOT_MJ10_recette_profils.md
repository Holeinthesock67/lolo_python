# Lot MJ10 – Recette des profils sur le PC

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série MJ : recette sur le PC (migration réelle, deux profils, séance de 10 min) | — | MJ5, MJ9 | Petite | Non : propriétaire |

Série MJ, plan `docs/2.0/PLAN_SERIE_MJ.md` §8.

## 1. Objectif

Vérifier sur le PC du propriétaire la migration réelle, deux profils, le changement de profil au Click et une séance courte.

## 2. Prérequis

MJ5, MJ9 ; passage par la file des mesures PC (fil « Fusionner les PR et séquencer les mesures »).

## 3. Déroulé

1. Sauvegarde, puis migration réelle ; `openride-core xp --compare` sans écart.
2. Création d'un second profil au Click (nom saisi dans la grille), changement de profil, réglages différents.
3. Séance de 10 min au plus sur le vélo sur le second profil ; vérifier que le premier n'a pas bougé.
4. Session simulée : bandeau ESSAI, rien d'écrit dans les profils joueurs.

## 4. Critères d'acceptation

Tous les points du déroulé ; captures et journal joints au suivi.
