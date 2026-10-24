# Lot M1 – Erreur d'écriture du Control Point : renvoyer la commande au lieu de reconnecter

## 1. Objectif

Le 24 octobre, une écriture du Control Point FTMS a échoué sur le Victory avec l'erreur ATT 0x80 (« Application Error »). Aujourd'hui, toute exception levée par `ControlPoint.call` remonte jusqu'à `FtmsDriver.run` : le pilote coupe la liaison, attend, recherche le trainer et se reconnecte, soit plusieurs secondes sans consigne pour une seule écriture ratée. Ce lot fait **renvoyer la commande** après une erreur ATT ponctuelle, sans toucher à la liaison ; la reconnexion ne reste que pour les vraies pannes (liaison coupée, erreurs répétées).

## 2. À lire

1. `docs/lots/00_INDEX.md` (règles communes), `docs/AUDIT_FTMS_2026-10-24.md` (écarts 1 et 2 : une procédure à la fois, erreurs 0xFE et 0xFD).
2. `docs/SIMULATION_BLE.md` (scénario `erreur_0x80`, événement `att_error` avec `count`).
3. Code : `core/src/openride_core/ftms_driver.py` (`ControlPoint.call`, `_flush_command`, `_take_control`, `run`, `_forget_sent`), `core/src/openride_core/ftms.py` (codes `ATT_PROCEDURE_IN_PROGRESS`, `ATT_CCCD_IMPROPERLY_CONFIGURED`), `core/src/openride_core/ble_sim.py` (`att_error`, `pending_att_errors`).
4. Tests : `core/tests/test_ble_sim.py` (`test_att_error_0x80_then_recovery`), `core/tests/test_drivers_session.py`.

## 3. Prérequis

Aucun. Partir de `main` à jour (simulateur Bluetooth de la PR #74 compris).

## 4. Travail demandé

- **Reconnaître une erreur ATT.** Fonction `att_error_code(exc) -> int | None` dans `ftms_driver.py` : lit le code dans le message BlueZ/bleak (`... ATT error: 0x80`, insensible à la casse) ; `None` pour toute autre exception (liaison perdue, délai dépassé, etc.).
- **Renvoi.** Dans `_flush_command` et `_take_control`, une écriture qui échoue avec une erreur ATT est renvoyée **jusqu'à 2 fois** (3 essais en tout), 0,25 s d'attente entre deux essais, avec la consigne **la plus récente** (`_want`), pas une copie périmée.
  - 0xFE (« Procedure Already In Progress ») : attendre en plus la fin de la procédure en cours (au plus `CP_RESPONSE_TIMEOUT_S`) avant le renvoi.
  - 0xFD (indications non abonnées) : refaire `cp.enable()` avant le renvoi.
  - Autres codes (0x80 compris) : renvoi simple.
- **Échec persistant.** Après 3 essais ratés de suite, l'exception remonte comme aujourd'hui (reconnexion). Une écriture réussie remet le compteur à zéro.
- **Journal.** Une ligne `WARNING` par erreur (`Trainer : écriture 0x05 refusée (ATT 0x80), renvoi 1/2`) et une ligne `INFO` au succès d'un renvoi. Compteur public `att_retries` (comme `reconnect_count`), écrit dans la ligne de bilan de fin de séance si elle existe.
- **Relâche.** `release_control` garde son comportement (un essai par étape, borné dans le temps) : l'arrêt ne doit jamais s'allonger.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/ftms_driver.py`, `core/tests/test_ble_sim.py` (le test 0x80 attend désormais un renvoi sans reconnexion ; ajout des cas ci-dessous), `docs/SIMULATION_BLE.md` (tableau des tests et ligne du scénario `erreur_0x80`), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `ble_sim.py` et `sim_scenarios.py` (lecture seule : le simulateur sait déjà produire ces erreurs ; un manque est signalé), contrat IPC.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Une erreur 0x80 sur une consigne ERG (`att_error`, `count` 1) : `reconnect_count` reste à 0, `att_retries` vaut 1, la consigne arrive au trainer simulé moins de 0,6 s après l'erreur, et le statut ne quitte jamais `CONNECTED`.
3. Deux erreurs de suite (`count` 2) : toujours aucune reconnexion ; trois de suite (`count` 3) : une reconnexion, puis reprise du contrôle et de la consigne comme aujourd'hui.
4. 0xFE puis succès : le renvoi n'a lieu qu'après la réponse 0x80 de la procédure en cours (ordre des écritures relevé sur le trainer simulé).
5. Une liaison coupée pendant l'écriture (`drop`) déclenche la reconnexion, sans renvoi.
6. Le scénario `erreur_0x80` en séance complète (`CoreSession`, Bluetooth simulé) se termine sans `ERROR`, avec une seule connexion du trainer.
7. `att_error_code` : tests unitaires sur les messages réels de BlueZ (0x80, 0xFE, 0xFD, majuscules, message sans code).

**Sur le vélo (Laurent) :** relire `~/run_victory.log` après une séance ERG : une éventuelle erreur 0x80 doit être suivie de « renvoi » et non de « Reconnexion au trainer ».

## 8. Hors périmètre

- Cause de l'erreur 0x80 côté Victory (interne, matériel).
- Stabilité du Zwift Click.
- Analyse de ces lignes par `log_report` (à proposer dans le rapport si utile).
