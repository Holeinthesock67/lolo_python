# Lot N12 – Appairage des appareils côté core : enregistrer le matériel trouvé dans la configuration locale

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Appairage côté core : enregistrer le nom et l'adresse du matériel trouvé dans `~/OpenRide/config.toml` | Python | M3 (livré) | Petite | **Livré le 25 octobre** (issue #112, PR #177) |

## 1. Objectif

Le propriétaire veut, dans les futurs menus, une section « Appareils » qui recherche le home trainer, les deux boîtiers du Zwift Click et la ceinture cardio, puis **garde sur le PC** ce qu'elle a trouvé : nom annoncé et adresse Bluetooth. Depuis le nettoyage du dépôt du 24 octobre, ces valeurs réelles ne doivent plus apparaître dans le dépôt : elles vivent seulement dans `~/OpenRide/config.toml`, qui est hors du dépôt.

Aujourd'hui, `openride-core devices` (lot M3) affiche un bloc `[drivers]` à recopier à la main. Ce lot ajoute l'écriture de ce bloc dans la configuration locale. Il prépare aussi l'appel par le menu (lot N13) : la recherche et l'enregistrement sont des fonctions que le core pourra appeler depuis l'IPC.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_M3_inventaire_appareils.md` (et sa section « Livraison »), `docs/SIMULATION_BLE.md`.
2. `docs/SRS_v1.1.md` §11 (configuration) et `core/src/openride_core/config.py` (`TrainerConfig.device_name`, `DriversConfig`, `load`, `validate`).
3. Code : `core/src/openride_core/tools/devices.py` (recherche et classement, `CONFIG_KEYS`), `core/src/openride_core/session.py` (`_click_device`), `core/src/openride_core/tools/log_scenario.py` (repère du boîtier « + »), `core/src/openride_core/__main__.py` (`build_parser`).

## 3. Prérequis

Aucun : M3 est livré. Ne dépend pas du contrat IPC (le menu est le lot N13).

## 4. Travail demandé

- Nouveau module `core/src/openride_core/pairing.py` :
  - `PairedDevices` : `trainer_name`, `trainer_address`, `click_plus_address`, `click_minus_address`, `hr_name`, `hr_address` (chaînes, vides si absent) ;
  - `from_inventory(inventaire) -> PairedDevices` : choisit dans le résultat de `tools/devices.py` le trainer FTMS au meilleur RSSI, les deux boîtiers du Click (le « + » est celui qui envoie un appui « + » pendant la phase d'identification ci-dessous, sinon le premier trouvé) et la ceinture (une montre seulement s'il n'y a pas de ceinture) ;
  - `save(paired, path=None) -> list[str]` : écrit les valeurs dans `~/OpenRide/config.toml` (ou `path`) : `[trainer] device_name` et `[drivers] trainer_address`, `click_address` (boîtier « + »), `click_minus_address`, `hr_address`, `hr_name`. Les autres clés, les autres sections et **les commentaires** sont conservés ; une sauvegarde `config.toml.bak` est faite avant l'écriture ; le fichier final passe `config.validate` (sinon rien n'est écrit et l'erreur est rendue). Retourne la liste des lignes changées, pour l'affichage ;
  - aucune valeur n'est écrite ailleurs que dans ce fichier (ni journal, ni dépôt, ni `/tmp`).
- Nouvelle clé `[drivers] click_minus_address` (chaîne, vide par défaut) dans `config.py` et sa validation ; `session._click_device` et `tools/log_scenario.py` reconnaissent le « + » d'après `click_address` de la configuration chargée (repli sur l'adresse simulée seulement en simulation).
- Identification du « + » : `openride-core devices --save` demande, après la recherche, « Appuyez sur le bouton + du Click » et attend au plus 15 s un appui (via `ZwiftClickProvider`, fonction injectable pour les tests) ; sans appui, il garde l'ordre de la recherche et le dit.
- `openride-core devices --save [--yes] [--config FICHIER]` : affiche les différences avec la configuration actuelle, demande confirmation (sauf `--yes`), puis appelle `save`. `--sim-scenario demo` fonctionne aussi (écrit dans le fichier donné par `--config`, jamais dans le vrai `~/OpenRide/config.toml` pendant les tests).
- Documentation : `README.md` (section appareils), `docs/SIMULATION_BLE.md` si les adresses simulées y sont citées pour le « + ».

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/pairing.py`, `core/tests/test_pairing.py`.
- **Modifiés :** `core/src/openride_core/tools/devices.py` (option `--save`), `core/src/openride_core/__main__.py`, `core/src/openride_core/config.py`, `core/src/openride_core/session.py`, `core/src/openride_core/tools/log_scenario.py`, `README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** l'engine, le contrat IPC, tout fichier du dépôt contenant une vraie adresse ou un vrai nom d'appareil (les tests n'utilisent que les adresses simulées `C1:1C:00:00:00:0x`).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Scénario simulé `demo` : `devices --save --yes --config TMP/config.toml` écrit le nom et l'adresse du trainer simulé, les deux boîtiers et la ceinture ; un second appel ne change rien et le dit.
3. Fichier de départ avec des commentaires, une section `[rider]` et une clé inconnue : tout est conservé à l'identique, seules les clés d'appareils changent ; `config.toml.bak` contient l'ancien fichier.
4. Valeur invalide (adresse mal formée) : aucune écriture, message clair, code de sortie non nul.
5. Appui « + » simulé sur le second boîtier trouvé : c'est son adresse qui va dans `click_address`.
6. `session._click_device` classe correctement les deux boîtiers avec une configuration dont `click_address` n'est pas l'adresse simulée.
7. Aucune adresse réelle ni nom de marque dans les fichiers ajoutés ou modifiés (vérifié par une recherche dans la PR).

**Sur le PC cible (le propriétaire) :** lancer `openride-core devices --save`, appuyer sur « + » quand demandé, vérifier `~/OpenRide/config.toml`, puis rouler une séance avec les deux boîtiers.

## 8. Hors périmètre

- Écran « Appareils » du menu et commandes IPC de recherche (lot N13).
- Connexion permanente ou appairage BlueZ (`bluetoothctl pair`) : OpenRide se connecte sans appairage système.

## 9. Livraison (25 octobre 2026, PR #177)

- Code et tests fusionnés sur `main` par la PR #177 (issue #112 fermée) ; détail dans la description de la PR et dans `docs/SUIVI_AVANCEMENT.md`.
