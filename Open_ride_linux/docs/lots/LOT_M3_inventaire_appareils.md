# Lot M3 – Inventaire des appareils : `openride-core devices`

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Inventaire des appareils Bluetooth : `openride-core devices` | Python | — | Petite | **Livré le 24 octobre** (issue #80) |

## 1. Objectif

Pour remplir `trainer_address`, `click_address` ou `hr_address` dans `config.toml`, il faut aujourd'hui lancer `openride-ble-diag scan` (liste brute du sprint 0) et deviner quel appareil est quoi. Ce lot ajoute une commande qui recherche les appareils utiles à OpenRide, les **classe** (trainer FTMS, boîtier Zwift Click, ceinture ou montre cardio), signale ceux que BlueZ garde connectés, et affiche les lignes de configuration à copier.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/SIMULATION_BLE.md` (appareils simulés et leurs adresses).
2. `docs/SRS_v1.1.md` §5 (appareils) et la section `[drivers]` de la configuration (`docs/SRS_v1.1.md` §11 ou `config.py`).
3. Code : `core/src/openride_core/ble_util.py` (`find_device`, `known_bluez_address`), `core/src/openride_core/ftms.py` (UUID des services), `core/src/openride_core/zwift_click.py` (identification du Click), `core/src/openride_core/tools/ble_diag.py` (`scan`, à ne pas modifier), `core/src/openride_core/__main__.py` (`build_parser`), `core/src/openride_core/config.py`.

## 3. Prérequis

Aucun. M2 change la façon dont la ceinture est choisie en séance, pas ce lot : les deux sont indépendants (fichiers distincts).

## 4. Travail demandé

- `openride-core devices [--timeout S] [--json] [--config FICHIER]` (défaut 8 s) :
  - recherche par `BleakScanner` (fonction de recherche **injectable** pour les tests), une ligne par appareil : rôle, nom, adresse, RSSI, services reconnus ;
  - rôles : `trainer` (service FTMS 0x1826), `click` (règle de `zwift_click.py`), `hr_strap` ou `hr_watch` (service 0x180D ; montre si le nom ressemble à une montre, même liste de noms que M2 si M2 est déjà fusionné, sinon constante locale), `other` (masqué sauf avec `--all`) ;
  - appareils connus de BlueZ et connectés mais muets (Click resté accroché, trainer réservé) : listés à part, avec le conseil `openride-core release-trainer` pour un trainer ;
  - en fin de sortie, le bloc `[drivers]` proposé (`trainer_address = "…"`, `click_address`, `hr_address`) et, si `config.toml` contient déjà des adresses, les différences (« configuré mais absent », « présent mais non configuré ») ;
  - `--json` : clés stables documentées en tête du module.
- Aucune écriture dans `config.toml` (copie manuelle par l'utilisateur), aucune connexion aux appareils.
- Option `--sim-scenario NOM|FICHIER` : la recherche se fait dans le Bluetooth simulé (démonstration et tests), mêmes noms que `run --sim-scenario`.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/tools/devices.py`, `core/tests/test_devices.py`.
- **Modifiés :** `core/src/openride_core/__main__.py` (sous-commande `devices`), `README.md` et `CLAUDE.md` (commande citée), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `ble_util.py`, `ble_diag.py`, `ble_sim.py` (lecture seule).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/` (le test de cohérence des commandes citées compris).
2. Recherche simulée avec le scénario `demo` : un trainer, deux boîtiers Click (« + » et « − », adresses du simulateur) et une ceinture, chacun au bon rôle ; le bloc `[drivers]` proposé contient leurs adresses.
3. Recherche injectée avec une montre et une ceinture : rôles `hr_watch` et `hr_strap`, la ceinture est proposée pour `hr_address`.
4. Configuration avec un `trainer_address` absent de la recherche : la différence « configuré mais absent » est affichée.
5. `--json` : sortie validée par un schéma écrit dans le test ; aucune clé en plus ni en moins.
6. Aucun appel de connexion (`BleakClient`) pendant la commande (vérifié par une doublure qui échoue si on la construit).

**Sur le PC cible (le propriétaire) :** `openride-core devices` avec le HomeTrainer, les deux Click réveillés et la ceinture.

## 8. Hors périmètre

- Écriture automatique de `config.toml`.
- Écran d'état des appareils dans l'engine (lot G).

## 9. Livraison (24 octobre 2026)

- `core/src/openride_core/tools/devices.py` : recherche injectable (`ble_scan` par `BleakScanner.discover`, `bluez_connected` par D-Bus, `sim_sources` pour le Bluetooth simulé), `classify`, `propose`, `differences`, sortie texte et `--json` (clés en tête du module). M2 étant fusionné avant, la liste des noms de montres est celle de `hr_monitor.WATCH_NAME_HINTS`.
- `openride-core devices [--timeout S] [--json] [--all] [--config FICHIER] [--sim-scenario NOM|FICHIER]` dans `__main__.py`.
- Choix assumés : le Click récent a deux boîtiers de même nom, impossibles à distinguer en recherche ; le bloc propose le premier (par adresse) pour `click_address` et cite le second en commentaire (`click_other_address` en JSON). La ceinture est proposée avant une montre. Un appareil connecté mais muet reste proposé.
- Tests : `core/tests/test_devices.py` (critères 2 à 6 ; la doublure de `BleakClient` échoue si on la construit). Le test de cohérence des commandes citées passe.
