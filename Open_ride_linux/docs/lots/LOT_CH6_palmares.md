# Lot CH6 – Ligue d'hiver : palmarès des saisons closes

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CH : palmarès des saisons closes (place, points, vainqueur, trophée), ligne « Palmarès » de l'écran de la ligue, contrat IPC 1.40 | Python, GDScript | CH3c (#1020), CH4a | Petite | **Livré le 27 novembre** (PR #1047) |

Ce lot répond au choix du propriétaire du 24 novembre 2026 : rappel d'abord (CH7), palmarès ensuite. Cadrage :
`plans/ch-ligue/CADRAGE_PALMARES_RAPPEL_2026-11-23.md` (dossier du projet).

## 1. Ce que le lot fait

- **Core** (`league.py`) :
  - `history(path, current)` lit les saisons closes. Elles sont gardées dans `ligue_saison_<n>.json` par
    `league_new` (revue F1-07), auxquelles s'ajoute la saison de `ligue.json` si elle est close.
  - Les saisons vont de la plus récente à la plus ancienne, 8 au plus (`HISTORY_MAX`). Un fichier illisible est
    sauté et jamais déplacé.
  - Chaque ligne donne : numéro, dates, fin (`fin` ou `pause`), ta place sur 12, tes points, le vainqueur et ses
    points, `winner_me`, et le trophée écrit ou null.
  - `archive_path` donne le nom du fichier d'une saison close.
- **Contrat**, révision 1.40 (train de protocole du 26 novembre, au-dessus des 1.37 à 1.39) : la réponse `league` à
  `league_status` et `league_new` porte un champ facultatif `history` (schéma `league`). Avec 8 saisons, le
  message tient sous 4 096 octets (test).
- **Engine** (`league_view_model.gd`) :
  - la ligne « Palmarès » apparaît dès qu'une saison est close, par exemple avec « 2 saisons closes » ;
  - au focus, la fiche de droite écrit une ligne par saison, tout en mots. Exemple : « Saison 1 (23 nov. 2026 –
    17 janv. 2027) : 3e sur 12, 142 pts · Trophée de bronze · vainqueur Fabien Lacroix, 188,5 pts » ;
  - quand tu as gagné la saison, la ligne dit « tu as gagné la saison ».

## 2. Recette

- Core :
  - `test_league.py` : lignes, archives et saison close courante, saison en cours absente, fichier abîmé
    sauté, plafond de 8, taille du message ;
  - `test_league_session.py` : `history` dans la réponse, validé par le schéma.
- Engine : `test_league_menu.gd` (`_test_palmares`) teste la ligne, la fiche, la victoire écrite et la fiche au
  focus dans le flux du menu.
- Menus seuls : scénario `menu_scenarios/ligue_palmares.json`, avec deux saisons closes fictives et la capture
  `ch6_palmares` (banc medium) à valider.

## 3. Pour plus tard

- Ta meilleure place à chaque manche du calendrier, et ton record de points.

## Livraison

Fusionné dans `main` le 27 novembre 2026 (PR #1047), relevé par la passe de doc du 27 novembre 2026 (statut précédent : « En revue »).
