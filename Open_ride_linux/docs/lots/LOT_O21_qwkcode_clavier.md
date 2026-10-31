# Lot O21 – Saisie du QWKcode au clavier dans le menu ERG

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| QWKcode de GoldenCheetah tapé au clavier dans Session ERG (commande `create_workout_qwk`, fichier `.qwk` écrit par le core) | Python + GDScript | O20 (livré) | Petite | Choix « Les deux » du propriétaire du 30 octobre ; en PR |

## 1. Objectif

Le 30 octobre, le propriétaire a demandé de pouvoir créer un entraînement avec la syntaxe QWKcode de GoldenCheetah. Sur la carte de décision (saisie au Click), il a choisi « Les deux ». Le lot O20 a apporté le fichier `.qwk` importé. Ce lot ajoute la saisie directe au clavier dans **Session ERG**, sur le même analyseur (`workout_formats.parse_qwk`).

## 2. Spécification

| # | Règle |
| --- | --- |
| O21-1 | La liste **Session ERG** gagne la ligne « Saisir du QWKcode (clavier) », entre « Créer » et « Importer ». Sa carte montre l'aide QWKcode du lot O20. |
| O21-2 | L'écran **Saisir du QWKcode** montre une ligne de menu par ligne de texte. La dernière porte le curseur `▌`. Suivent « Enregistrer et choisir » (avec le nombre de segments, désactivé sans segment) et « Tout effacer ». La carte de droite rappelle la syntaxe. |
| O21-3 | Clavier : une touche imprimable s'écrit à la fin de la dernière ligne, même `+`, `-`, `a` ou `y`, qui sont utiles au QWKcode. Entrée commence une ligne, mais jamais deux lignes vides de suite, et 40 lignes au plus. Retour arrière efface, ou retire une ligne vide. Les flèches ← → et Échap restent des boutons. Entrée sur « Enregistrer » ou « Tout effacer » les choisit, comme A maintenu ou un clic. |
| O21-4 | Bornes : 60 caractères par ligne, 3 000 octets en tout. La commande tient ainsi dans un datagramme de 4 096 octets (contrat §2). |
| O21-5 | « Enregistrer » envoie `create_workout_qwk {text}`. Le core relit le texte. S'il est invalide, il répond `workout_invalid` avec le numéro de ligne : la ligne d'état affiche « Échec : … » et le texte est gardé. S'il est valide, il écrit `<nom>.qwk`, nommé d'après la ligne `#` (`qwkcode` sans elle), sans écraser un autre entraînement, et répond `workout_saved`. Retour à la liste, focus sur l'entraînement, texte vidé. |
| O21-6 | Le texte en cours est gardé quand on quitte l'écran (Échap) et vidé après un enregistrement réussi. L'engine n'analyse rien : le core reste seul juge et seul à écrire (décision D4). |
| O21-7 | Au Click seul, l'écran ne permet pas d'écrire. L'aide renvoie alors au fichier `.qwk` importé (lot O20). |

## 3. Contrat

Révision 1.5, ajout compatible : commande `create_workout_qwk` `{ "text": chaîne }`, réponse `workout_saved` (`docs/contracts/ipc_v1.md`, `cmd.schema.json`). Requête idempotente comme `create_workout` : un même texte retrouve le même fichier.

## 4. Fichiers

- Core : `workout_menu.py` (`create_qwk_workout`, `qwk_stem`), `session.py`, `ipc_server.py`.
- Engine :
  - `qwk_editor.gd` (nouveau : texte, bornes, éléments) ;
  - `menu_flow.gd` (écran, `qwk_key`) ;
  - `menu_model.gd` (ligne de la liste) ;
  - `main.gd` (touche, commande) ;
  - `ipc_client.gd` ;
  - `workout_help.gd` (aide).
- Docs : `GUIDE_UTILISATION.md` §5, contrat IPC.
- Tests :
  - `core/tests/test_workout_menu.py` ;
  - `engine/tests/unit/test_menu_flow.gd` (`_test_qwk_entry`), `test_menu_model.gd` ;
  - banc des menus `engine/tests/menu_scenarios/erg_qwkcode.json` (voie clavier : texte tapé, fichier écrit, ligne d'état).
