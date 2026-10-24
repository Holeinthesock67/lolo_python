# Lot K8 – Diagnostic des déconnexions du Zwift Click

## 1. Objectif

Le Click se déconnecte de lui-même (environ 2 fois en 3 minutes le 22 octobre, constat M8, seul constat ouvert de l'audit). La cause ne se trouvera qu'avec le matériel, mais les journaux actuels ne permettent pas de la chercher : ils disent « déconnecté » sans durée de connexion, sans délai depuis le dernier appui, sans raison BlueZ, ni ce que faisait le trainer à cet instant. Ce lot enrichit le journal et l'analyseur pour que le prochain essai de Laurent donne des données exploitables.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_H6_analyse_journal.md` (livraison).
2. `CLAUDE.md` (« Faits matériels et pièges connus », section Click) ; `docs/spikes.md`.
3. Code : `core/src/openride_core/input_providers.py` (`ZwiftClickProvider`), `core/src/openride_core/ble_util.py` (verrou BLE), `core/src/openride_core/ftms_driver.py` (écritures au trainer), `core/src/openride_core/tools/log_report.py` et ses journaux de test `core/tests/data/logs/`.

## 3. Prérequis

Aucun. Partir de `main` à jour.

## 4. Travail demandé

- **Journal (`input_providers.py`)**, sans changer le comportement de reconnexion :
  - à la connexion : adresse, durée de la recherche, nombre de tentatives ;
  - à la déconnexion (rappel `disconnected_callback` de bleak, ou fin de la boucle de notifications) : durée de connexion, temps depuis la dernière notification et depuis le dernier appui, nombre de notifications reçues, raison si bleak ou BlueZ la donne ;
  - toutes les 60 s pendant la connexion : cadence réelle des notifications (le Click en envoie environ 10 par seconde) ;
  - format de ligne fixe et documenté dans le module, en français, une ligne par événement.
- **Analyseur (`log_report.py`)** : section « Click » enrichie : durées de connexion (min, médiane, max), délai de reconnexion, temps depuis le dernier appui au moment des coupures, cadence de notifications, et coupures du Click qui tombent à moins de 2 s d'une écriture au trainer ou d'une reconnexion du trainer (corrélation à tester, cf. verrou BlueZ). Sortie texte et `--json`.
- Journaux de test synthétiques dans `core/tests/data/logs/` reproduisant ces lignes.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/input_providers.py` (journal seulement), `core/src/openride_core/tools/log_report.py`, `core/tests/test_log_report.py`, `core/tests/test_drivers_session.py` (si un test de journal du Click y trouve sa place), `CLAUDE.md` (une ligne sur les nouveaux messages), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Nouveaux :** `core/tests/data/logs/seance_click_coupures.log`, éventuellement `core/tests/test_click_journal.py`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `cd core && pytest -q` passe en entier ; les anciens journaux de test donnent le même résultat qu'avant pour les champs existants.
2. Avec les doublures BLE (`FakeClient`, `fake_finder`) : une connexion, 25 notifications dont 3 appuis, puis une déconnexion produisent les lignes attendues (durée, compteurs, temps depuis le dernier appui).
3. Sur le journal synthétique : durées de connexion et délais de reconnexion exacts ; une coupure placée à 1 s d'une écriture au trainer est comptée comme corrélée, une autre à 10 s ne l'est pas.
4. `--json` : nouvelles clés présentes, anciennes clés inchangées.
5. Aucune écriture de journal supplémentaire dans la boucle à 50 Hz (les nouvelles lignes sont émises par la tâche du Click, au plus une par minute hors événements).

## 8. Hors périmètre

- Correction de la cause des déconnexions (interne, avec le matériel).
- Changement des délais de recherche ou du verrou BLE.

## 9. Essais à faire sur le matériel (propriétaire)

- Séance de 20 minutes avec le Click, puis `python -m openride_core.tools.log_report ~/run_victory.log` : coller la section « Click ».

## 10. Livraison (24 octobre 2026, PR #34)

- Journal du Click dans `core/src/openride_core/input_providers.py` : une ligne à la connexion (adresse, durée de recherche, tentatives), une à la coupure (durée de connexion, dernière notification, dernier appui, nombre de notifications, dernière écriture au trainer, raison), la cadence des notifications toutes les 60 s.
- Ajout hors liste : `ble_util.note_trainer_write()`, appelé avant chaque écriture au Control Point, pour dater la dernière écriture au trainer.
- Analyseur `log_report.py` : durées de connexion, délais de reconnexion, coupures corrélées à une écriture ou à un événement du trainer (2 s ou moins). Anciennes clés JSON inchangées.
- Fusionné avec la connexion aux deux boîtiers du Click (PR #47) : le journal porte l'adresse du boîtier tenu ; l'absence du second boîtier reste en DEBUG tant qu'il ne s'est jamais connecté.
- Reste : la séance de 20 min avec le Click (§9).
