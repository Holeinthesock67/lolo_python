# Lot X40 – Run Cyber-Rogue de bout en bout dans la séance du core

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : Run Cyber-Rogue de bout en bout dans la séance du core (`rogue_bout_en_bout`), pause, resynchronisation, trace pour le banc visuel | Python | R8, R7 | Petite | **Livré le 28 octobre** (branche `claude/project-thread-818r6t-x40`) ; issue #543 |

## 1. Objectif

Les tests de la série R valident chaque module (moteur de run, combat, couloirs, équilibrage simulé de R7), et `test_rogue_session.py` fait courir une run dans la séance à puissance fixe. Il manquait une run jouée comme au vélo : un cycliste qui suit les salles, pousse ses boutons au Click, choisit ses cartes et ses portes, met en pause, puis va jusqu'au bilan, en relevant tout ce que la séance envoie à l'engine. Le fil de la série R a proposé cet outil le 28 octobre (outil 1).

## 2. À lire

`core/src/openride_core/session.py` (`_start_run`, `_step_rogue`, `_handle_input`, `_finish`), `rogue/mode.py`, `tools/rogue_sim.py` (cycliste simulé `Bot` de R7), `core/tests/test_rogue_session.py`, schémas `docs/contracts/ipc/{state,room,loot}.schema.json`, cahiers R8 et R13.

## 3. Travail demandé

- **`python -m openride_core.tools.rogue_bout_en_bout [--objective threshold|endurance|vo2max|tous] [--duration 30] [--seed 5] [--profil moyen] [--trace FICHIER.jsonl] [--json]`**.
- La vraie `CoreSession` tourne au pas d'une seconde, sans trainer réel ni engine : d'abord `start_run`, puis `start`. Le cycliste de `rogue_sim` (profil au choix) décide de la puissance, de la cadence, des appuis Z et A et du braquet voulu. Ses appuis passent par `_handle_input`, le chemin du Click, et sa puissance par le trainer simulé `MockDriver`.
- Au bout de 30 s dans la première salle, Y met la run en pause pendant 60 s. L'outil demande alors `rogue_resync`, puis `resume`.
- Tous les messages vers l'engine sont relevés : `state` à chaque pas, `room`, `loot`, `input` et `error`. Avec `--trace`, ils sont écrits un par ligne (`{"t", "msg"}`) pour le banc visuel X41.
- **Vérifications :**
  - la run est composée puis lancée ;
  - les phases se suivent dans l'ordre : échauffement, salles et couloirs, boss, retour au calme, résultats ;
  - les salles et les offres sont envoyées à l'engine ;
  - la run reçoit les appuis (Z, A, braquets) et compte des Perfect Shifts ;
  - la pause fige le temps de run, W'bal et le mur, et relâche la pente du trainer ;
  - `rogue_resync` renvoie la salle en cours ;
  - les messages restent sous la limite de taille et respectent les schémas du contrat (si `jsonschema` est installé) ;
  - aucune erreur n'est envoyée à l'engine ;
  - la durée de la run est à 25 % près de la durée demandée ;
  - la séance se termine d'elle-même après les résultats, avec `summary.rogue` ;
  - le journal est relu : ligne `rogue_run`, instantanés des phases, enregistrements en mode ROGUE.
- Le journal, le FIT et la progression restent dans un dossier temporaire. Codes de sortie : 0, 1 si une vérification échoue, 2 pour un appel invalide.

## 4. Fichiers

- **Nouveaux :** `core/src/openride_core/tools/rogue_bout_en_bout.py`, `core/tests/test_rogue_bout_en_bout.py`, ce cahier.
- **Modifiés :** `tools/rogue_sim.py` (`Bot.decide`, physique fournie par l'appelant ; résultats de R7 inchangés), `rogue/mode.py` et `session.py` (fin de séance après les résultats, §7), `core/tests/test_rogue_session.py`, `docs/OUTILS_DE_TEST.md`, `00_INDEX.md`, `README.md` et `SUIVI_AVANCEMENT.md` (nombre de tests).

## 5. Critères d'acceptation

1. Les trois objectifs passent toutes les vérifications, chacun en moins de 30 s de calcul au cloud.
2. Une séance qui ne se termine pas après les résultats est signalée, et seulement elle.
3. Le même `--seed` donne la même run, et les rapports de `rogue_sim` ne changent pas.

## 6. Hors périmètre

L'affichage de la run par l'engine (banc visuel, lot X41) et l'équilibrage (R7).

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x40`, issue #543).

- **Défaut trouvé à la mise en service et corrigé :** à la fin d'une run (phase `RESULTS`), la séance restait en `RUNNING` sans fin. Le bilan n'arrivait que si le cycliste ouvrait la pause et choisissait « Terminer et enregistrer ». Désormais, la séance se termine d'elle-même, comme à l'arrivée d'un parcours, après `RESULTS_HOLD_S` = 3 s en `RESULTS`. Ce délai laisse l'engine montrer la phase et jouer son jingle de fin (R18). `RogueMode.done` porte cette règle. `test_rogue_session.py` vérifie désormais la fin automatique.
- **Mesuré au cloud :** les trois objectifs passent (30 min, graine 5, profil moyen). Chaque run fait de 30,2 à 30,4 min de run, calculées en 2 s environ. Elle compte 6 salles boss compris, 4 offres, des Perfect Shifts et des cartes. La pause est figée et la reprise se fait. Les trames `state` font au plus 1 013 octets, les `room` 3 928.
- **Tests :** `core/tests/test_rogue_bout_en_bout.py` (8 tests).
  - Deux objectifs complets.
  - La trace : phases, ordre des temps, dernière trame `FINISHED` avec le bilan.
  - Le défaut rejoué avec `RESULTS_HOLD_S` infini : la seule vérification en échec est celle de la fin de séance.
  - Les appels invalides et les codes de sortie.
