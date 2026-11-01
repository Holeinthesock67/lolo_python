# Lot DS4 – Maquettes de l'arche, du HUD et du bilan

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série DS : maquettes de l'arche d'élimination, du HUD de course, des bandeaux et du bilan, validées par le propriétaire | Maquettes | DS1 | Petite | **Livré le 31 octobre** (version 3.0), maquettes validées par le propriétaire |

Série DS (mode « Dernier survivant », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/3.0/PLAN_SERIE_DS.md`.

## 1. Objectif

Montrer au propriétaire, avant tout code d'affichage, l'arche d'élimination, le bloc de course, la liste des coureurs, les bandeaux (élimination d'un bot, joueur dernier, joueur éliminé, vainqueur) et le bilan.

## 2. À lire

`docs/3.0/PLAN_SERIE_DS.md` §5 ; `engine/scripts/segment_markers.gd` (styles d'arche) ; `engine/scripts/hud_view.gd` ; `engine/scripts/summary_view.gd`.

## 3. Travail demandé

- Planches en 1680×1050 et 1024×600, en `low`, `medium` et `high`.
- Arche gonflable de la famille des portiques, style propre (bandes rouges et noires, bandeau « ÉLIMINATION »).
- Pas de flash plein écran ; le rouge « DERNIER ! » reste lisible sans clignoter vite.

## 4. Critères d'acceptation

1. Le propriétaire valide les planches ; la date de validation est notée dans ce cahier avant le début de DS5 et DS6.

## Livraison

Livré le 31 octobre 2026 (branche `claude/project-thread-ewr5b6-ds4`). **Maquettes validées par le propriétaire le 31 octobre 2026 à 10:26 UTC** (« ok ») : DS5 et DS6 peuvent commencer.

- Six scènes : approche de l'arche, joueur dernier, élimination d'un bot, joueur éliminé, vainqueur, bilan ; en `low`, `medium` et `high`, en 1680×1050 et 1024×600 (36 images), plus deux planches en `medium` et une planche des trois qualités.
- Dessins posés sur de vraies captures du lot Y18 (bots dessinés comme l'avatar) : l'arche, le HUD et les bandeaux ne sont pas un rendu du jeu. Images et script (`maquettes_ds4.py`) dans le dossier partagé du projet, `captures/ds4-maquettes/`, hors du dépôt.
- Choix retenus : arche gonflable de la famille des portiques, bandes rouges et noires, bandeau rouge foncé « ÉLIMINATION » avec damier ; bloc « SURVIVANT » sous la vitesse (arche, distance, barre, rang, écart avec le dernier ; cadre rouge et « DERNIER ! » quand le cycliste est dernier) ; liste des coureurs sous la puissance (cycliste surligné en jaune, dernier marqué d'un point rouge, éliminés grisés et barrés avec leur arche) ; bandeau d'élimination d'un bot en bas de l'écran, bandeaux du joueur éliminé (rouge) et du vainqueur (vert) au milieu ; bilan arche par arche avec « A : continuer · Y : rejouer la course ».
