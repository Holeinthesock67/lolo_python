# Lot O24 – Écran Appareils : ceinture vraiment activée, appareils oubliables

## 1. Objectif

Audit des options du 31 octobre (`docs/AUDIT_OPTIONS_MENUS_2026-10-31.md`, validé par le propriétaire le 31 octobre) : la ceinture cardio choisie dans l'écran **Appareils** était enregistrée (`drivers.hr_address`, `drivers.hr_name`) sans être activée. `drivers.hr` restait à `none`, le lanceur ne passe pas `--hr` : la ceinture n'était jamais lue, sauf en éditant `config.toml` à la main. Aucun appareil ne pouvait non plus être retiré depuis le menu.

## 2. Spécification

| # | Règle |
| --- | --- |
| O24-1 | Choisir une ceinture (`pair_devices` avec une adresse dans `hr`) écrit aussi `drivers.hr = "ble"`, dans la couche du profil en cours comme les autres clés de la ceinture (lot MJ4). Même règle pour `openride-core devices --save`. |
| O24-2 | `pair_devices` accepte `""` pour un rôle : l'appareil est oublié. Trainer : adresse vidée, `trainer.device_name` remis à sa valeur par défaut (recherche par le nom). Boîtier du Click : adresse vidée. Ceinture : `drivers.hr = "none"`, adresse et nom vidés. `null` garde toujours la valeur actuelle. |
| O24-3 | Écran Appareils : valider **Trainer** ou **Ceinture** fait le tour des appareils trouvés puis de « aucun » (« aucun (oublié) » tant que ce n'est pas enregistré). **Oublier le Click** prépare l'oubli des deux boîtiers. La confirmation cite « l'oubli du trainer », « l'oubli du Click », « l'oubli de la ceinture ». Pendant une recherche ou une identification, ces lignes sont inactives. |
| O24-4 | « Libérer le trainer » n'entre pas dans l'écran : pendant qu'OpenRide tourne, le core tient le trainer, et **Quitter** le relâche déjà ; l'icône du bureau reste pour le cas d'un arrêt brutal. |

## 3. Contrat

`docs/contracts/ipc_v1.md` : valeur `""` des rôles de `pair_devices`, révision 1.5 (ajout compatible : un engine plus ancien n'envoie jamais de chaîne vide).

## 4. Fichiers

- Core : `pairing.py` (`FORGET_VALUES`, `PairedDevices.forget`, `_values`, `paired_from_args`).
- Engine : `pairing_view_model.gd`.
- Docs : contrat IPC, `GUIDE_UTILISATION.md`, `CHANGELOG.md`, `scripts/config.example.toml`.
- Tests : `core/tests/test_pairing_menu.py` ; `engine/tests/unit/test_pairing_view_model.gd`, `engine/tests/unit/test_menu_style.gd`, scénario du banc des menus `engine/tests/menu_scenarios/appareils.json` (vérifie `drivers.hr = "ble"` au Click, au clavier et à la souris).

## 5. Critères d'acceptation

1. Banc des menus, scénario `appareils` : après Enregistrer, `config.toml` contient `drivers.hr = "ble"`, sur les trois voies.
2. `pair_devices` avec `""` pour le trainer, le boîtier « − » et la ceinture : les clés de la règle O24-2 sont écrites, le reste du fichier est gardé.
3. Sur le PC (fil de fusion) : appairer la vraie ceinture, relancer, la FC s'affiche dans le HUD.
