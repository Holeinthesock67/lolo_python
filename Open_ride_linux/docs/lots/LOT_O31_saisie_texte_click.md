# Lot O31 – Saisie de texte partagée au Click

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Saisie de texte partagée au Click (text_entry.gd) : nom d'un profil et recherche d'un lieu du monde ouvert ; prête pour le QWKcode (O21) | GDScript | MJ8, W11 (livrés) | Petite | Livré le 31 octobre (PR #660) |

## 1. Objectif

Audit des options du 31 octobre (`docs/AUDIT_OPTIONS_MENUS_2026-10-31.md`, validé par le propriétaire) : la recherche d'un lieu du monde ouvert ne se faisait qu'au clavier. Avec le Click seul, impossible de chercher un lieu ni de choisir une destination. Seul le nom d'un profil (lot MJ8) avait une grille de lettres pensée pour le Click. Ce lot en fait un composant unique, partagé par tous les champs de texte.

## 2. Spécification

| # | Règle |
| --- | --- |
| O31-1 | `engine/scripts/text_entry.gd` : texte, longueur maximale, signes en plus des cases (apostrophe d'un lieu), grille de 10 colonnes, « Effacer » et « Valider ». Une lettre s'écrit en majuscule en début de mot. Au clavier, on tape le texte. |
| O31-2 | Le nom d'un profil (`profiles_view_model.gd`) passe par ce composant, sans changement visible. |
| O31-3 | Monde ouvert : Z sur le globe ouvre la recherche sur la grille. + et − changent de case, maintenus ils changent de ligne ; Z écrit ; Y efface (texte vide : retour au globe) ; A maintenu (ou « Valider ») passe aux résultats s'il y en a. Dans les résultats, − et + choisissent, A valide, Z revient à la grille, Y quitte la recherche. La recherche de la destination (A sur « Destination : à choisir ») suit les mêmes règles. |
| O31-4 | Au clavier, rien ne change : on tape le nom, la liste garde la main (− et + choisissent, Entrée valide, Échap revient). |
| O31-5 | L'aide des boutons (`button_help.gd`) décrit une seule grille, `text_grid()`, pour le nom (« Valider le nom ») et pour la recherche (« Voir les résultats ») ; Z : Chercher sur le globe. |
| O31-6 | Le champ QWKcode au clavier (lot O21, à faire) utilisera ce composant pour être aussi saisi au Click. |

## 3. Fichiers

- Engine : `text_entry.gd` (nouveau), `profiles_view_model.gd`, `world_menu_model.gd`, `world_menu_view.gd` (grille en lignes de texte, case en focus entre crochets), `button_help.gd`, `main.gd` (texte du globe exporté pour le banc des menus).
- Tests : `engine/tests/unit/test_world_menu_model.gd`, `test_profiles_view_model.gd` ; banc des menus `monde_ouvert` (voie Click : grille, écriture, effacement) et `profils`.
- Docs : `GUIDE_UTILISATION.md` §4 bis, `CHANGELOG.md`.

## 4. Critères d'acceptation

1. Au Click seul : Z, quelques lettres, A maintenu, puis A sur un résultat ouvrent la carte du lieu.
2. Le nom d'un profil se saisit comme avant (banc `profils`).
3. La grille de la recherche est validée sur capture par le propriétaire.

## Livraison

PR #660, fusionnée le 31 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Audit des options du 31 octobre, validé par le propriétaire ; en PR ».
