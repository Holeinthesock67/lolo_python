# Lot W18 – Départ direct de la balade en monde ouvert

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Départ direct en monde ouvert : après le préchargement, la balade part au pédalage sans repasser par l'accueil | GDScript | W11, O36 (livrés) | Petite | En revue (PR à valider : essai sur le PC) |

## 1. Objectif

Constat du banc des biomes en monde ouvert (PR #852, 13 novembre) : après **Démarrer** sur l'écran du cap, le monde se précharge, puis le menu du monde ouvert se fermait sur l'**accueil**, le parcours `ow:…` chargé ; il fallait encore choisir **Session libre**, puis **Démarrer** sur l'écran **Prêt**. Accord du propriétaire le 13 novembre : la balade part directement.

## 2. À lire

`engine/scripts/world_menu_model.gd`, `engine/scripts/main.gd` (`_on_state`, fermeture du menu du monde ouvert), `docs/lots/LOT_O36_*` (départ au pédalage), `docs/GUIDE_UTILISATION.md` §4 bis.

## 3. Travail

- `world_menu_model.gd` : `on_session(état, parcours)`. Pendant le préchargement, une séance `READY` sur un parcours `ow:…` rend `{action: "start"}` une seule fois ; `RUNNING` ou `PAUSED` (séance déjà partie) rend `{action: "close"}` ; tout autre cas (préchargement en cours, parcours de fond du menu) rend `{}`.
- `main.gd` : à chaque trame, le menu du monde ouvert visible demande `on_session` ; une action ferme le menu et, pour `start`, envoie la commande `start` (sans argument : balade libre). Le départ au pédalage (O36) prend la main : écran « START YOUR ENGINES », chrono parti après 3 s de pédalage ; avec `[depart] mode = "immediat"`, la balade part tout de suite.
- Pas de changement du contrat IPC ni du core.

## 4. Tests

`engine/tests/unit/test_world_menu_model.gd` : préchargement en cours, parcours de fond, monde prêt (départ demandé une fois), séance déjà en route, hors préchargement.

## 5. Recette

Sur le PC : monde ouvert, départ choisi, **Démarrer** : après le préchargement, l'écran « START YOUR ENGINES » paraît sans passer par l'accueil ; pédaler : la balade part. Le scénario `w17_cap` (PR #852) passe encore par **Session libre** ; après fusion des deux lots, il attendra seulement « -> RUNNING ».

## 6. Livraison

- Branche `claude/project-thread-oft1se-w18`, PR à valider.
