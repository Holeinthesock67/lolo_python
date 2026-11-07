# Lot BC3 – Maquettes de l'écran Collection

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série BC : maquettes de l'écran « Collection », de la carte agrandie, de l'annonce au bilan et de la première ouverture, en low, medium et high | GDScript | BC1 | Petite | Livré le 7 novembre (maquettes validées par le propriétaire) ; captures du jeu en low, medium et high avec BC5 et BC6 |

Série BC (version 5.0, badges et cartes à collectionner, demande du propriétaire du 7 novembre 2026). Plan de la série : `docs/5.0/PLAN_SERIE_BC.md`.

## 1. Objectif

Faire valider la présentation avant tout code d'affichage (règle des captures du 28 octobre).

## 2. Travail demandé

Planche de captures (`engine/tests/visual_check.py`, faux core) : accueil avec la ligne « Collection » ; album par familles ; carte agrandie gagnée, pas encore gagnée et de saison ; annonce au bilan (une carte et « + 2 autres ») ; première ouverture. Visuels provisoires (pictogrammes) tant que BC4 n'a pas livré.

## 3. Critères d'acceptation

1. Lisible au Click à 2 m : titre et rareté identifiables sans lire la ligne d'ambiance.
2. Une seule information nouvelle par écran.
3. Captures en low, medium et high validées par le propriétaire.

## Livraison

Maquettes validées par le propriétaire le 7 novembre 2026 (20 h 37), dessinées hors du moteur dans le style des menus actuels (fond bleu nuit, ligne choisie en cyan, rappel des touches Click et clavier en pied d'écran) avec les visuels de BC4 :

1. Accueil : ligne « Collection » sous « Historique », détail « 17 / 42 cartes » et point orange quand une carte n'a pas été vue.
2. Album : une ligne par famille (titre et « n / total »), trois familles à l'écran, rappel des familles au-dessus et au-dessous ; carte à gagner en silhouette grise, carte nouvelle marquée d'un point orange.
3. Carte gagnée agrandie : visuel, titre, rareté (couleur du cadre), n° x / 42 ; à côté, ligne d'ambiance, date et heure, séance, condition, bouton « Voir la séance ».
4. Carte pas encore gagnée : silhouette grise, condition, barre et valeur d'avancement (« 612 / 1 000 km »), récompense du défi quand la carte en vient.
5. Carte de saison : titre suivi de l'année d'édition, période, éditions gagnées et prochaine édition, rappel « exclusive à sa période ».
6. Fin de séance : bilan à gauche, une seule carte annoncée à droite (« Nouvelle carte », visuel, titre, rareté) et « + n autres dans la Collection ».
7. Première ouverture : « n cartes déjà gagnées par vos séances passées », cinq visuels, bouton « Ouvrir la Collection ».

Critère 3 : la planche validée vaut pour la mise en page. Les captures du jeu en low, medium et high se font avec BC5 et BC6 et sont validées avant leur fusion (règle des captures du 28 octobre).
