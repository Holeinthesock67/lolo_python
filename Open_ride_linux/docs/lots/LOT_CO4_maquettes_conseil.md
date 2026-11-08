# Lot CO4 – Maquettes de la séance conseillée

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Séance conseillée : maquettes au rendu du jeu (conseil, détail, autre besoin, prochaine course), validées par le propriétaire | GDScript | CO0 | Petite | Livré le 8 novembre (PR #770, version 5.0), planche validée par le propriétaire le 7 novembre |

Série CO (version 5.0, séance conseillée par OpenRide). Plan de la série : `docs/5.0/PLAN_SERIE_CO.md`.

## 1. Objectif

Montrer les écrans au propriétaire au rendu réel du menu (jetons `ui_theme.gd`, 1280 × 720 et 1024 × 600) avant CO5, à partir de la maquette de principe de CO0.

## 2. Critères d'acceptation

Planche des captures déposée dans les fichiers du projet ; date de validation du propriétaire notée dans ce cahier. Aucun code d'affichage de CO5 n'est fusionné avant.

## 3. Réalisation (7 novembre, en PR avec CO3, CO6 et CO9)

- `engine/tests/maquette_conseil.gd` : la vraie vue des menus (`menu_view.gd`, carte de détail, bandeau des boutons, thème `ui_theme.gd`) reçoit les sept écrans prévus pour CO5, remplis avec un conseil fabriqué : accueil avec la ligne « Séance conseillée », conseil (entraînement puis course en focus), détail du calcul (barres de répartition), autre besoin, prochaine course, suggestion de la montre. Rien n'est branché au core.
- Rendu Forward+ sous Xvfb (Vulkan logiciel), 1280 × 720 et 1024 × 600 ; menus en 2D sur le voile, identiques en low, medium et high (pas de vue 3D derrière la maquette).
- Planche : `/mnt/project-files/menus/co4-maquettes-conseil/` (fichiers du projet), `planche_1280x720.png` et `planche_1024x600.png`.
- Validation du propriétaire : planche validée le 7 novembre à 23 h 04 (« Ok »), CO5 lancé.

## Livraison

PR #770 (fusionnée le 8 novembre) : maquettes au rendu du jeu, planche validée par le propriétaire le 7 novembre. Statut corrigé par le bilan du 8 novembre au soir.
