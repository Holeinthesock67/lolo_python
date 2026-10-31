# Lot O17 – Boutons de l'ERG et clavier selon le plan commun

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Boutons de l'ERG et clavier selon le plan commun : ± long = biais ± 10 %, Z = bloc suivant, Y = pause ; clavier touche pour touche (décision D6) | Python + GDScript | PR #287 (boutons décodés, révision 1.3) | Petite | Oui, avant la 1.0 (décision D3 du 27 octobre, issue #367 ; plan des boutons des menus livré par la PR #287) ; livré le 28 octobre, essai J7 sur le PC à faire |

## 1. Objectif

Mettre les boutons du mode ERG au plan de boutons commun à tous les modes, avant la 1.0, pour que le guide d'utilisation (O6), les notes de version et la recette (O8) décrivent les gestes définitifs (décision D3 de l'audit de cohérence du 27 octobre). Aujourd'hui, en ERG, l'appui long + passe au bloc suivant et l'appui long − met l'entraînement en pause à 0 %, alors que dans tous les autres modes les appuis longs sont un grand pas de la même grandeur que les appuis courts, Z est l'action du mode et Y la pause.

| Bouton | Avant (SRS §4.4) | Après (spécification générale §7.1) |
| --- | --- | --- |
| + / B, court | Biais ± 2 % | Inchangé |
| + / B, long | + : bloc suivant ; − : pause ERG à 0 % | Biais ± 10 % (cinq pas), borné à 80 % et 120 % |
| Z court | Rien | Bloc suivant |
| Y court | Pause et reprise de la séance (N6) | Inchangé |

La pause propre à l'ERG (pente 0 %, temps du bloc arrêté) disparaît : la pause de la séance par Y fait déjà la même chose pour le cycliste, et une seule pause évite deux états différents.

Le lot met aussi le **clavier** au plan commun (décision D6 du 27 octobre) : il double le Click touche pour touche, selon le tableau du clavier de la spécification générale §7.1. Aujourd'hui, l'engine a ses propres touches (flèches haut et bas pour le braquet, Page haut et bas pour les appuis longs, P, Espace et Échap pour la pause, Entrée et Échap pour valider et revenir dans les menus) et le fournisseur du terminal n'a que + et −.

## 2. À lire

1. `docs/SPECIFICATION_GENERALE.md` §7.1 (tableau des boutons, seule référence) ; `docs/SRS_v1.1.md` §4.2, §4.4 et §6 ; `docs/lots/LOT_F_erg_zwo.md` (comportement d'origine) ; `docs/lots/LOT_N6_affichage_menus.md` (pause par Y).
2. Code : `engine/scripts/main.gd` (`_unhandled_input`), `engine/scripts/menu_model.gd` (`key_to_event`), `core/src/openride_core/input_providers.py` (`KeyboardProvider`), `core/src/openride_core/session.py` (`_handle_input`, `_skip_block`, `_sync_erg_state`), `core/src/openride_core/workout.py` (`ErgController.change_bias`, `toggle_pause`, `BIAS_STEP_PCT`), `core/src/openride_core/zwift_click.py` (décodage de Z, apporté par la PR #287 réécrite).

## 3. Prérequis

La PR #287, réécrite selon le §7.1, fusionnée : elle décode A, Y, Z et les flèches et ajoute leurs événements à la révision 1.3 du contrat (`Z_SHORT` notamment, aussi utilisé par le clavier de l'engine via `input_event`).

## 4. Travail demandé

- `session.py`, mode ERG (hors roue libre) : `PLUS_LONG` et `MINUS_LONG` appellent `change_bias(+5)` et `change_bias(-5)` ; `Z_SHORT` appelle `_skip_block()` ; plus aucun appel à `toggle_pause` depuis le Click.
- `Z_SHORT` en mode SIM ne fait rien tant que la série T n'a pas branché le bonus (T1) ; en roue libre ERG, les appuis courts restent des braquets, comme aujourd'hui.
- `workout.py` : retirer `toggle_pause` et l'état `paused` de `ErgController` s'il ne sert plus ailleurs ; sinon le garder pour la reprise après un plantage (N8) et le dire dans le rapport. La reprise d'une séance (`resume_after_crash`) ne doit plus restaurer une pause ERG.
- Journal : l'événement de saut de bloc garde son nom ; le biais continue d'être écrit après chaque changement.
- **Clavier, engine :** un seul module `engine/scripts/key_map.gd` (test `engine/tests/unit/test_key_map.gd`) traduit touche et durée d'appui en événement du Click selon le tableau du §7.1, avec les mêmes seuils (court sous 0,5 s, long à 0,9 s ou plus, `PLUS_UNCLEAR` et `MINUS_UNCLEAR` entre les deux) mesurés à l'appui et au relâchement ; synonymes Page haut, Page bas, Maj+A, Entrée, Maj+Z, Échap. `main.gd` et `menu_model.gd` l'utilisent tous deux : en menu, l'événement pilote le menu (§7.1) ; en séance, il part au core par `input_event`, sauf A et les flèches haut et bas, qui restent dans l'engine pour les vues de caméra (sans effet avant V12). `key_to_event` et les touches propres de `main.gd` disparaissent.
- **Clavier, terminal :** `KeyboardProvider` suit le même tableau ; ne pouvant mesurer la durée, il prend les synonymes pour les appuis longs.
- Documentation : SRS §4.2 (ligne Z), §4.4 (tableau ERG) et §6 (HUD) ; `README.md` (commandes du Click) ; `CHANGELOG.md` (ligne « biais ± 2 % et saut de bloc au Click ») ; spécification générale (statut de 1.0-ERG-5) ; index et suivi.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/key_map.gd`, `engine/tests/unit/test_key_map.gd`.
- **Modifiés :** `engine/scripts/main.gd`, `engine/scripts/menu_model.gd`, `engine/tests/unit/test_menu_model.gd`, `core/src/openride_core/input_providers.py`, `core/tests/test_drivers_session.py` (fournisseur clavier), `core/src/openride_core/session.py`, `core/src/openride_core/workout.py`, `core/tests/test_drivers_session.py`, `core/tests/test_contract_ipc.py`, `core/tests/test_journal_devices.py`, `core/tests/test_workout.py`, `docs/SRS_v1.1.md`, `docs/SPECIFICATION_GENERALE.md`, `README.md`, `CHANGELOG.md`, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** le reste de l'engine (l'aide des commandes à l'écran suit le §7.1 avec la PR #287), le format `.world`.

## 6. Modifications de contrat autorisées

Aucune : les événements des boutons sont ajoutés à la révision 1.3 par la PR #287.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/` ; `run_engine_tests.sh` passe (hors échec connu `test_tree_renderer`, #119) ; `test_key_map.gd` couvre chaque ligne du tableau du clavier, les seuils et la zone floue.
2. Séance ERG simulée : deux appuis longs + font passer le biais de 100 % à 120 % (butée) ; un appui long − le ramène à 110 % ; aucun bloc n'est sauté.
3. `Z_SHORT` (Click simulé ou `input_event` de l'engine) passe au bloc suivant avec le lissage de 2 s ; au dernier bloc, l'entraînement se termine.
4. Y met en pause et reprend la séance ERG, temps du bloc arrêté pendant la pause ; aucun autre geste ne met l'ERG en pause.
5. En SIM, les appuis longs restent ± 10 braquets et Z ne change rien.
6. Au clavier, sans Click : les mêmes gestes donnent les mêmes effets qu'au Click, en menu et en séance ; les flèches haut et bas ne changent plus le braquet.
7. Essai court du propriétaire sur le PC cible (`--trainer mock` puis le vélo) : biais au grand pas et bloc suivant au Click et au clavier.

## 8. Hors périmètre

Le bonus de la série T sur Z en SIM (T1, T6), les vues de caméra elles-mêmes (V12).

## 9. Livraison (28 octobre)

- **Core :** `session.py` : ± court et ± long changent le biais d'un et de cinq pas (`BIAS_STEPS`, ± 2 % et ± 10 %), Z court passe au bloc suivant (roue libre comprise), Y reste la pause de la séance. `ErgController.toggle_pause` a disparu ; l'état `paused` reste, posé par la session quand la séance passe en pause ou en sort (`_set_state`) : le champ `erg.paused` du contrat garde son sens (« ERG en pause ») sans modification de contrat, `RampWatch` l'utilise toujours, et la reprise après un plantage repart en pause de séance, plus jamais en pause ERG à 0 %. La branche « pause ERG : pente 0 % » de `_step` est retirée.
- **Clavier de l'engine :** `key_map.gd` (tables `MEASURED`, `FIXED`, `SHIFT_LONG`, seuils de `PressClassifier`), événement au relâchement comme au Click. Choix de lecture : en séance, **toutes** les touches partent au core par `input_event`, A et les flèches comprises ; le core les relaie à l'engine comme un appui du Click, et l'engine les traite par le même chemin (`_on_input_event` : bip, vues de caméra de V12). Le clavier n'a ainsi aucun chemin propre, en séance comme en menu (en menu, `_on_input_event` est appelé directement, sans le core). Les flèches gauche et droite au carrefour passent donc par `OpenWorld.on_input`, comme celles du Click ; la commande `choose_branch` du contrat reste, sans appelant au clavier.
- **Clavier du terminal :** `TERMINAL_KEYS` et `split_terminal_keys` (`input_providers.py`) : séquences d'échappement des flèches et de Page haut et bas ; `SimClickKeyboard` passe + et − par le Click simulé, les autres boutons en événements directs (le Click simulé n'a que + et −).
- **Textes à l'écran :** rappel des commandes du HUD (`controls_text`), explication de l'appui ambigu, aide de l'écran de modification d'un réglage (« A long : enregistrer, Y : annuler », conforme à `menu_flow._handle_edit`).
- **Docs :** guide §6 réécrit (tableaux des actions au Click, tableau unique du clavier) et son test `test_guide_shortcuts_match_code_and_negative`, qui relit maintenant `key_map.gd` ; SRS §4.2, §4.4, §6 ; contrat (`erg.paused`, `skip_block`) ; README, CHANGELOG, protocole (C, E, G3, J7), spécification générale.
- **Reste sur le PC :** `test_key_map.gd` et `run_engine_tests.sh` (Godot ne tourne pas dans le conteneur de développement), puis l'essai J7.
