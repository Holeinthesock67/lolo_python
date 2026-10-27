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

## 9. Livraison (26 octobre 2026)

Contrat révision 1.2 accepté par le propriétaire le 25 octobre (tableau §4 tel quel, plus les codes d'erreur `busy`, `scan_failed`, `pairing_failed`) ; le 26 octobre, il a confirmé que N13 et Q1 partagent la révision 1.2. Lot repris le 26 octobre à sa demande (« un écran qui montre la connexion des appareils au lancement, puis le menu une fois tout connecté ou en passant l'unilatéral »).

- **Core** (fait le 25 octobre) : `pairing.py` (`scan_items`, `scan_results_message`, `paired_from_args`) ; `session.py` (commandes `scan_devices`, `identify_click_plus`, `pair_devices`, appui « + » d'identification non relayé au menu) ; `run --config` transmis à la séance ; tests `core/tests/test_pairing_menu.py`, dont le scénario « recherche puis enregistrement » en Bluetooth simulé.
- **Écran « Connexion des appareils »** (ajout au §5, demande du 26 octobre) : au premier état hors séance, avant l'accueil. Lignes d'état des appareils (N5) ; passage seul à l'accueil quand le trainer, les boîtiers du Click et la ceinture (si elle est configurée) sont reliés depuis 2 s ; sinon « Passer » nomme ce qui manque (« un seul boîtier du Click » pour l'unilatéral) ; « Rechercher et appairer » ; « Quitter » avec confirmation. Pas d'écran de connexion si la séance tourne déjà au premier état (`--autostart`, reprise N8). `devices_view_model.connection()`, `menu_flow.gd`.
- **Écran « Appareils »** (Réglages → « Appareils : rechercher et appairer », ou depuis l'écran de connexion) : recherche lancée à l'ouverture, ligne d'état sous le titre, trainer et ceinture choisis parmi ceux trouvés (valider : suivant), « Click : identifier le bouton + » (l'autre boîtier trouvé devient « − »), « Enregistrer » avec confirmation qui nomme les changements, puis « Relancer OpenRide maintenant ». `pairing_view_model.gd`, `ipc_client.gd` (signal `scan_results_received`, `scan_devices`, `identify_click_plus`, `pair_devices`).
- **Relance** : l'engine sort avec le code 64 ; le lanceur `openride` arrête proprement le core (trainer relâché) puis relance core et engine, qui se connectent aux nouveaux appareils (critère 2 sans quitter à la main). `launcher.py` (`EXIT_RELAUNCH`), test `test_engine_relaunch_code_restarts_core_and_engine`.
- **Tests** : `engine/tests/unit/test_pairing_view_model.gd`, `test_menu_flow.gd` (écran de connexion, Passer, unilatéral, Appareils), `test_menu_model.gd` ; banc des menus `engine/tests/menu_bench.py` (vrai core sur Bluetooth simulé, vrai engine sous Xvfb, appuis joués par le message de test `menu_input`) : parcours `connexion_auto` et `appareils` (un seul boîtier → Passer → Réglages → Appareils → recherche → Enregistrer → `config.toml` écrit → Relancer, code 64).
- **Écart au §4** : le core ne coupe pas ses connexions pendant la recherche (les appareils reliés sont listés par BlueZ) ; la nouvelle configuration sert au lancement suivant, que « Relancer » déclenche.
- **Reste (propriétaire)** : critère 2 sur le PC avec le vrai Click (identification du « + » au vrai boîtier) et lisibilité à 2 m.
- **Correctif du 27 octobre (« scan_failed … org.bluez.Error.InProgress »)** : la recherche de l'écran Appareils lançait sa découverte BlueZ pendant que le trainer ou le Click cherchaient à se reconnecter, et BlueZ refuse deux découvertes à la fois. `pairing.scan_inventory` prend désormais le verrou BLE commun (`ble_util.ble_lock`, déjà partagé par les pilotes), en Bluetooth réel comme simulé, et attend la fin de leur tentative ; si BlueZ répond encore `InProgress` (recherche d'une autre application), `session._scan_inventory` refait deux essais après 1 s, puis un message lisible (`pairing.scan_error_message`), envoyé après le `scan_results` final pour que l'écran le garde. Le Bluetooth simulé (`SimWorld.discovery`) refuse maintenant lui aussi deux recherches simultanées ; tests `test_simulated_bluez_refuses_two_discoveries`, `test_scan_waits_for_driver_search_instead_of_failing`, `test_scan_waits_for_bluetooth_busy_with_another_search`, `test_scan_failed_message_is_readable_and_kept_on_screen`.
