# Lot BC7 – Recette de la collection sur le PC

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série BC : recette sur le PC cible avec le profil d'essai (séances simulées), puis ouverture du vrai profil (cartes des séances passées), low, medium et high | – | BC5, BC6 | Petite | Prêt après BC5 et BC6 ; par le propriétaire, via la file du PC |

Série BC (version 5.0, badges et cartes à collectionner, demande du propriétaire du 7 novembre 2026). Plan de la série : `docs/5.0/PLAN_SERIE_BC.md`.

## 1. Objectif

Vérifier sur le PC que la collection du vrai profil correspond à `openride-core collection`, et que rien ne bouge dans les séances (budgets GPU inchangés).

## 2. Critères d'acceptation

1. Profil d'essai : une séance simulée de 25 minutes avant 7 h donne « Lève-tôt » dans ce profil seulement.
2. Vrai profil : même liste à l'écran et dans `openride-core collection`.
3. Mesures en low, medium et high passées par le fil de la file du PC.
