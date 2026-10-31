# Lot X55 – Banc des menus : silences de l'engine et fermeture datée

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : toutes les attentes du banc des menus tolèrent les silences de l'engine ; étapes de la fermeture de l'engine datées dans le journal | Python, GDScript | N13 | Petite | Passage du banc sur le PC à faire (branche `claude/project-thread-svx7ij`) |

## 1. Objectif

Rotation du banc des menus sur le PC, `main` 12bafacc (31 octobre) : 20 scénarios sur 22 passent, plus aucun « engine sans réponse ». Deux échecs restaient, sans lien avec une PR ouverte, et les deux scénarios passent dans le cloud (aussi avec les quatre cœurs chargés).

1. `appareils`, voie Click : « A_LONG reçu par l'engine : aucune ligne « (Bip|Souris) : A_LONG » » puis « choisir « continue » : écran home, focus world ». L'écran avait bien changé : l'appui est arrivé, mais plus de 11 s après (délai du banc : durée de l'appui + 10 s). C'est le silence de l'engine juste après le premier écran déjà vu le 31 octobre (« engine muet »), que seule la vérification d'écran tolérait. Défaut du banc.
2. `quitter`, voie souris : « l'engine sort avec le code 0 : code None ». L'engine écrit « Quitter demandé depuis le menu » et envoie `bye` au core (11:14:38,5), mais son processus est encore là 10 s plus tard ; le banc l'arrête. Une sortie normale prend 1,2 à 1,4 s (cloud) ; la relance du scénario `appareils` est sortie en 1 s sur le PC. Cause non prouvée : `bye` est envoyé par le nœud IPC, l'un des derniers à sortir de la scène ; restent la sortie du nœud principal (chargement du parcours, sonde) et l'arrêt des serveurs de Godot.

## 2. Spécification

| # | Règle |
| --- | --- |
| X55-1 | Une seule attente d'une ligne de l'engine dans le banc (`Run.wait_engine`) : réponse à `menu_state`, bip ou appui ambigu d'un geste, clic de souris, touche, capture, étape `journal` de l'engine. Son délai ne compte pas les silences de l'engine (aucune ligne depuis 1 s ; en `--test-mode` il en écrit plusieurs par seconde), jusqu'à 60 s de silence. |
| X55-2 | La vérification d'écran repose sur la même attente (plus de logique de silence à part) ; une vérification ou un geste manqué note « engine muet X s » dans le rapport. |
| X55-3 | L'engine se ferme par une seule fonction (`_quit(code)` dans `main.gd`) pour quitter, relancer (64) et la session simulée (65). Après la demande, le journal date chaque étape : « Fermeture : nœuds de la scène sortis… », « …chargement du parcours et sonde fermés… », « …scène libérée, arrêt des serveurs de Godot… », en ms depuis la demande. |
| X55-4 | Étape `sortie` : le rapport donne le temps de sortie ; sans sortie dans le délai, la dernière étape « Fermeture : » vue, pour savoir où la fermeture attend. Il y ajoute les fils du processus Godot lus dans `/proc` (nom, état, attente dans le noyau ; aussi dans `fils_engine.txt`) : sans débogueur, qu'Ubuntu refuse d'attacher à un processus qui n'est pas un descendant. |

Écarté : allonger le délai de `sortie` ou des gestes (cacherait une fermeture vraiment lente), ou une exception pour le premier écran.

## 3. Fichiers

- `engine/tests/menu_bench.py` ;
- `engine/scripts/main.gd` (`_quit`, `_quit_step`, `_exit_tree`, `_notification`) ;
- `docs/OUTILS_DE_TEST.md`.

## 4. Critères d'acceptation

1. Cloud : `menu_bench.py --rotation` passe ; `appareils` et `quitter` passent sur les voies click et souris, quatre cœurs chargés (« engine muet » noté, aucun échec).
2. PC : rotation complète 22/22, ou, si `quitter` échoue encore, le rapport nomme la dernière étape de la fermeture (suite : lot de correction du jeu à cet endroit).

## 5. Passage PC du 31 octobre (7cs, branche ca1ad8fe + main)

3 passages sur 4 OK (`appareils` click et souris, `quitter` click), plus aucun « engine sans réponse » : l'échec `appareils` est corrigé. `quitter` à la souris ne sort toujours pas en 10 s ; dernière étape : « scène libérée, arrêt des serveurs de Godot », 154 ms après la demande. Le blocage est donc dans l'arrêt de Godot lui-même (serveurs, affichage X11), après tout le code du jeu, et seulement sur la voie souris. Seul effet propre à la souris hors du jeu : le survol d'une rangée change la forme du curseur X11 (`CURSOR_POINTING_HAND`, `menu_view.gd`). Hypothèse non prouvée ; la liste des fils de Godot au prochain passage dira lequel attend.
