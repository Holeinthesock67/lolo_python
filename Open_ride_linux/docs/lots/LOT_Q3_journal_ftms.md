# Lot Q3 – Journal des commandes FTMS et des accusés du trainer

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Journal des commandes FTMS et des accusés du trainer, délais dans `log_report` | Python | — | Petite | Livré le 25 octobre (PR #192) |

## 1. Objectif

Essai du 25 octobre, marches de pente 0 / 7 % : environ 22 s ressenties avant que la résistance se relâche. Le core met 4 à 5 s à changer la pente envoyée, et le trainer durcit en 2 à 3 s, mais ne relâche qu'au bout de 10 à 15 s. Le journal ne contient ni les écritures au Control Point FTMS ni les accusés du trainer : on ne peut pas dire si le retard vient du core, du Bluetooth ou du trainer. Ce lot ajoute une trace horodatée de chaque échange et une mesure du délai dans `log_report`. En fin de séance, le journal a aussi signalé « consignes remises à zéro par un tiers (Reset), renvoi » : la trace doit permettre de dire si ce Reset était le nôtre, revenu en écho.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_M8_journal_lanceur.md` (journal du lanceur et `log_report`), `docs/AUDIT_FTMS_2026-10-24.md`.
2. Code : `core/src/openride_core/ftms_driver.py` (`ControlPoint.call`, `on_indication`, `_flush_command`, `_on_status`, `_release`), `ftms.py` (codes d'opération, `parse_control_response`, `parse_machine_status`), `config.py`, `tools/log_report.py`, `ble_sim.py` (trainer simulé).

## 3. Prérequis

Aucun. `ftms_driver.py` est aussi modifié par Q5 : faire Q3 et Q5 l'un après l'autre, pas en parallèle.

## 4. Travail demandé

- **Trace FTMS**, activée par `[trainer] trace_ftms = true` (défaut faux) ou par l'option `--trace-ftms` de `openride-core run` et du lanceur :
  - à chaque écriture au Control Point, une ligne `FTMS > <opération> <valeurs lisibles> (<hex>)`, par exemple `FTMS > SIM pente 3.20 % crr 0.0040 cw 0.390 (11 0000 4001 28 27)` ;
  - à chaque indication, `FTMS < réponse <opération> <résultat> en <n> ms` (délai depuis l'écriture correspondante), ou `FTMS < sans réponse après <n> ms` à l'expiration ;
  - à chaque Machine Status, `FTMS < statut <nom> <valeurs>` en précisant s'il suit, de moins de 2 s, une commande envoyée par OpenRide (`écho probable de notre commande`) ;
  - horodatage à la milliseconde (horloge du driver), au niveau INFO quand la trace est active, rien sinon ;
  - pas plus d'une ligne par écriture : aucun ajout dans la boucle de 4 Hz des données du trainer.
- **`log_report`** : nouvelle section « Commandes FTMS » quand le journal contient la trace : nombre d'écritures par opération, délai écriture → accusé (médiane, p95, maximum), expirations, statuts « par un tiers » et échos probables.
- La même trace avec le trainer simulé (`ble_sim.py`) pour les tests.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/ftms_driver.py`, `config.py` (clé `trace_ftms` et validation), `__main__.py` et `launcher.py` (option `--trace-ftms`), `tools/log_report.py` ; `README.md` (section journaux), `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `core/tests/test_ftms_trace.py`.
- **Interdits :** `ftms.py` (le codage des trames ne change pas), `session.py`, l'engine, le contrat IPC.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Trace désactivée : journal identique à aujourd'hui (aucune ligne `FTMS >`).
3. Trace active, trainer simulé : une ligne `FTMS >` par écriture et une ligne `FTMS <` par réponse, délai cohérent avec la latence simulée (± 20 ms) ; expiration simulée signalée.
4. Reset simulé envoyé par un tiers, puis Reset envoyé par OpenRide : le premier est noté « par un tiers », le second « écho probable de notre commande ».
5. `log_report` sur un journal de test : section « Commandes FTMS » avec médiane, p95, maximum et nombre d'expirations justes ; section absente sans trace.
6. Coût : une séance simulée de 10 min avec trace ne produit pas plus de 2 lignes par seconde en moyenne.

**Sur le PC cible (le propriétaire) :** rouler les marches 0 / 7 % d'`essai-69` avec `--trace-ftms` et joindre la section « Commandes FTMS » de `log_report`.

## 8. Hors périmètre

- Changer la vitesse de la rampe (Q4) ou la façon d'envoyer les commandes.
- Journal binaire ou capture Bluetooth complète (`btmon`).

## Livraison

PR #192, fusionnée le 25 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Oui ; issue #170 ».
