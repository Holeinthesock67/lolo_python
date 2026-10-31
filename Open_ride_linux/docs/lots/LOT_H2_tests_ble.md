# Lot H2 – Tests de la recherche Bluetooth sans matériel

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Tests de la recherche Bluetooth sans matériel (audit F8) | Python | — | Petite | **Livré le 23 octobre** (PR #12, couverture 100 %) |

## 1. Objectif

Tester `ble_util.find_device` et `ble_util.known_bluez_address` sans adaptateur Bluetooth, avec un faux scanner `bleak` et un faux bus D-Bus. Aujourd'hui, ces fonctions ne sont vérifiées que sur le vrai vélo (couverture du module : 31 %). Ce lot ferme le constat F8 de l'audit.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `CLAUDE.md`, section « Faits matériels et pièges connus » (BlueZ, Click resté connecté).
3. `docs/AUDIT_2026-10-23.md`, constat F8.
4. Code : `core/src/openride_core/ble_util.py` ; doublures existantes dans `core/tests/test_drivers_session.py` (`FakeClient`, `fake_finder`).

## 3. Prérequis

Aucun. Partir de `main` à jour.

## 4. Travail demandé

Nouveau fichier `core/tests/test_ble_util.py`. **Aucune modification du code de production**, sauf si un test révèle un défaut : dans ce cas, s'arrêter et le signaler dans le rapport avant de corriger.

**Technique :**
- `find_device` importe `BleakScanner` à l'intérieur de la fonction : remplacer l'attribut avec `monkeypatch.setattr("bleak.BleakScanner", FakeScanner)` (ou injecter un faux module `bleak` dans `sys.modules`).
- `known_bluez_address` importe `dbus_fast` à l'intérieur : injecter un faux module `dbus_fast` et `dbus_fast.aio` dans `sys.modules` avec un `MessageBus` simulé qui renvoie un dictionnaire d'objets BlueZ (`org.bluez.Device1` avec `Name`, `Alias`, `Address`, valeurs enveloppées dans un objet ayant `.value`).

**Cas à couvrir :**

| Fonction | Cas | Attendu |
| --- | --- | --- |
| `find_device` | adresse donnée, trouvée au scan | le `BLEDevice` du scan |
| `find_device` | adresse donnée, absente du scan | l'adresse (str), pour une connexion directe |
| `find_device` | fragment de nom, trouvé par `d.name` | l'appareil ; recherche insensible à la casse (`hometrainer` trouve « HomeTrainer 0000 ») |
| `find_device` | fragment de nom, trouvé seulement par `ad.local_name` (`d.name` à `None`) | l'appareil |
| `find_device` | rien au scan, appareil connu de BlueZ | l'adresse BlueZ, et un message INFO « non annoncé » |
| `find_device` | rien au scan, BlueZ ne le connaît pas | `None` |
| `find_device` | délai transmis | `timeout` passé tel quel au scanner |
| `known_bluez_address` | correspondance par `Alias` seul | l'adresse |
| `known_bluez_address` | objet sans `Device1` ou sans `Address` | ignoré |
| `known_bluez_address` | `dbus_fast` absent (ImportError) ou bus en erreur | `None`, sans exception, message DEBUG |
| `known_bluez_address` | le bus est toujours déconnecté, même en cas d'erreur pendant l'appel | `disconnect()` appelé |
| `ble_lock` | deux appels dans la même boucle | même verrou ; boucles différentes : verrous différents |
| `backoff_delays` | suite | 1, 2, 4, 8, 10, 10 |

## 5. Fichiers concernés

- **Nouveau :** `core/tests/test_ble_util.py`.
- **Modifiés :** `docs/AUDIT_2026-10-23.md` (suivi de F8), `docs/SUIVI_AVANCEMENT.md` (total des tests).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Tous les cas du tableau du §4 ont un test, et `cd core && pytest -q` passe en entier.
2. La couverture de `ble_util.py` dépasse 90 % : `pytest --cov=openride_core.ble_util --cov-report=term-missing tests/test_ble_util.py` (installer `pytest-cov` pour la mesure, sans l'ajouter aux dépendances).
3. Aucun test n'ouvre de connexion D-Bus ou Bluetooth réelle : la suite passe dans un conteneur sans BlueZ.
4. `ble_util.py` est inchangé (ou l'écart est justifié dans le rapport).

## 8. Hors périmètre

- Tests de `ftms_driver.py` et `input_providers.py` (déjà couverts par `test_drivers_session.py`).
- Cause des déconnexions du Click (question matérielle, en interne).


## 9. Livraison (23 octobre 2026)

Branche `lot-h2-tests-ble` (PR #12), fusionnée dans `main`. Les 4 critères d'acceptation du §7 sont tenus :
- 14 tests dans `core/tests/test_ble_util.py` couvrant tous les cas du tableau du §4 (`find_device`, `known_bluez_address`, `ble_lock`, `backoff_delays`, `default_client_factory`).
- Couverture de `ble_util.py` portée de 31 % à **100 %** (`55 Stmts, 0 Miss`).
- `ble_util.py` strictement inchangé ; aucun accès D-Bus ni Bluetooth réel.
- Aucun écart.
