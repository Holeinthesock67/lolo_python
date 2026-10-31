# Lot O20 – Aide du menu ERG et QWKcode de GoldenCheetah (`.qwk`)

## 1. Objectif

Demandes du propriétaire du 30 octobre : « Faudra expliquer cela dans le menu erg », « Le menu erg devra expliquer les moyens de saisie et d'import », et « J'aimerais avoir la possibilité d'utiliser la syntaxe GoldenCheetah pour créer un entraînement ». Sur la carte de décision (saisie au Click), le propriétaire a choisi « Les deux » : d'abord un fichier `.qwk` importé (ce lot), puis un champ de saisie au clavier branché sur le même analyseur (lot suivant, O21).

## 2. Spécification

| # | Règle |
| --- | --- |
| O20-1 | La liste **Session ERG** se termine par « Comment ça marche ? ». Cette ligne ouvre l'écran **Aide ERG**, avec un sujet par ligne : Choisir un entraînement, Créer des intervalles, Saisie QWKcode (GoldenCheetah), Importer un fichier, Écrire un fichier à la main, Pendant la séance. L'explication du sujet sous le focus s'affiche dans la carte de détail à droite, au Click comme au clavier. Y revient à la liste. |
| O20-2 | Dans la liste, les lignes « Créer », « Importer » et « Comment ça marche ? » montrent aussi l'explication de leur sujet dans la carte. |
| O20-3 | Un fichier `.qwk` contient une ligne par segment : `[Nx] durée@puissance[-puissance] [rdurée@puissance[-puissance]]`. La durée s'écrit en `h`, `m` ou `s`, combinables (`1m30s`, `1.5m`). La puissance est en watts, ou en % de la FTP avec `%` (`50-75%` : le `%` vaut pour les deux bornes). Les lignes vides sont ignorées. `#` commence un commentaire, et le premier commentaire avant tout segment donne le nom. |
| O20-4 | Une rampe (`a-b`) donne un bloc `ramp`. `N x` ou une récupération `r…` donne des paires `interval_on` / `interval_off`, et les autres lignes des blocs `steady`. Les watts restent absolus, comme un `.erg`. Le plancher de 50 W du lot O19 s'applique. |
| O20-5 | Une erreur nomme la ligne fautive et rappelle la syntaxe. Sont refusés : de 0 à plus de 100 répétitions, une durée nulle, une cible au-delà de 2 000 W ou de 300 % de la FTP, une séance de plus de 6 h, un fichier sans segment. |
| O20-6 | `.qwk` rejoint `WORKOUT_SUFFIXES`, en dernier par priorité. Il est donc lu dans `~/OpenRide/Workouts/`, proposé à l'import et vérifié par `tools.workouts check`. |
| O20-7 | « Créer » ne remplace plus un autre entraînement. Avant, deux créations qui ne différaient que par la récupération ou l'échauffement écrivaient le même fichier. Désormais, les mêmes réglages retrouvent leur fichier, et des réglages différents sous le même nom reçoivent `_2`, `_3`…, comme à l'import. |

## 3. Contrat

Le contrat IPC est inchangé. L'import passe par `list_imports` / `import_workout`, et le core répond toujours `workout_saved` avec le `workout_id` final. Le champ clavier du lot O21 ajoutera une commande.

## 4. Fichiers

- Core : `workout_formats.py` (`parse_qwk`), `workout.py` (`.qwk`), `workout_menu.py` (`_store`, sans écrasement).
- Engine : `workout_help.gd` (sujets de l'aide), `menu_model.gd` (ligne « Comment ça marche ? »), `menu_flow.gd` (écran et cartes).
- Docs : `GUIDE_UTILISATION.md` §5.
- Tests : `core/tests/test_workout_qwk.py`, `core/tests/test_workout_menu.py`, `engine/tests/unit/test_menu_flow.gd`, banc des menus `engine/tests/menu_scenarios/erg.json`.
