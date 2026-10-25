# Lot N13 – Section « Appareils » du menu : rechercher et appairer le matériel

## 1. Objectif

Demande du propriétaire du 25 octobre : dans les menus, une section pour découvrir et appairer le matériel (home trainer, Zwift Click, ceinture cardio) et garder sur le PC les paramètres trouvés (nom, adresse Bluetooth). Ce lot ajoute cette section au menu piloté au Click et au clavier. Le core fait la recherche et l'écriture (lot N12) ; l'engine affiche et choisit.

**Lot interne :** il ajoute des messages au contrat IPC (décision du propriétaire) et un écran au menu du lot N6.

## 2. À lire

1. `docs/contracts/ipc_v1.md` (révision 1.1), `docs/lots/LOT_N12_appairage_core.md`, `docs/lots/LOT_N5_modele_etat_appareils.md`, `docs/lots/LOT_N6_affichage_menus.md`.
2. Code : `core/src/openride_core/pairing.py` (N12), `engine/scripts/devices_view_model.gd` (N5), `engine/scripts/menu_model.gd`.

## 3. Prérequis

N12 et N6 fusionnés (N5 aussi, par N6).

## 4. Proposition de contrat (révision 1.2, ajouts compatibles)

| Message | Sens | Champs |
| --- | --- | --- |
| commande `scan_devices` | engine vers core | `args` : `{ "timeout_s": nombre }` (8 par défaut) |
| `scan_results` | core vers engine | `request_cmd_id`, `done` (booléen), `items` : liste de `{role, name, address, rssi, configured}` ; `role` vaut `trainer`, `click`, `hr_strap`, `hr_watch` |
| commande `identify_click_plus` | engine vers core | `args` : `{}` ; le core attend un appui « + » pendant 15 s et le signale dans `scan_results` (`plus_address`) |
| commande `pair_devices` | engine vers core | `args` : `{trainer, click_plus, click_minus, hr}` (adresses choisies, ou `null` pour garder la valeur actuelle) ; le core appelle `pairing.save` et répond par `error` en cas d'échec |

- La recherche n'est permise qu'hors séance (`IDLE` ou `READY`) ; pendant `RUNNING`, le core répond `error` avec le code `busy`.
- Le core coupe ses propres connexions aux appareils pendant la recherche, puis se reconnecte avec la nouvelle configuration.
- `scan_results` respecte la limite de 1 400 octets (au plus 12 appareils, noms coupés à 24 caractères).

## 5. Écran

Menu « Appareils » : liste des appareils trouvés par rôle, celui déjà configuré marqué ; « Rechercher », « Identifier le bouton + », « Enregistrer », « Retour ». Le Click sert à naviguer, sauf pendant l'identification du « + ». Confirmation avant l'enregistrement, avec les changements.

## 6. Fichiers concernés

Contrat et schémas (`ipc_v1.md`, nouveau `scan_results.schema.json`, `cmd.schema.json`), `session.py` (commandes), nouveau `engine/scripts/pairing_view_model.gd` et son test, `menu_view.gd` (N6), `README.md`, `docs/SUIVI_AVANCEMENT.md`.

## 7. Critères d'acceptation

1. Toutes les suites passent, dont un scénario IPC « recherche puis enregistrement » en Bluetooth simulé.
2. Sur le PC cible : depuis le menu, rechercher, identifier le « + », enregistrer, quitter et relancer OpenRide : le trainer et les deux boîtiers se connectent sans terminal.
3. Aucune vraie adresse ni vrai nom dans le dépôt.

## 8. Hors périmètre

- Mise à jour du micrologiciel des appareils, étalonnage du trainer (spindown).
