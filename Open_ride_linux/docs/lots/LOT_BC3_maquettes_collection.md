# Lot BC3 – Maquettes de l'écran Collection

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série BC : maquettes de l'écran « Collection », de la carte agrandie, de l'annonce au bilan et de la première ouverture, en low, medium et high | GDScript | BC1 | Petite | Prêt ; validation du propriétaire avant BC5 et BC6 |

Série BC (version 5.0, badges et cartes à collectionner, demande du propriétaire du 7 novembre 2026). Plan de la série : `docs/5.0/PLAN_SERIE_BC.md`.

## 1. Objectif

Faire valider la présentation avant tout code d'affichage (règle des captures du 28 octobre).

## 2. Travail demandé

Planche de captures (`engine/tests/visual_check.py`, faux core) : accueil avec la ligne « Collection » ; album par familles ; carte agrandie gagnée, pas encore gagnée et de saison ; annonce au bilan (une carte et « + 2 autres ») ; première ouverture. Visuels provisoires (pictogrammes) tant que BC4 n'a pas livré.

## 3. Critères d'acceptation

1. Lisible au Click à 2 m : titre et rareté identifiables sans lire la ligne d'ambiance.
2. Une seule information nouvelle par écran.
3. Captures en low, medium et high validées par le propriétaire.
