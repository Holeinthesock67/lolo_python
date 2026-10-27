# Lot O4 – Section « Réglages » du menu : FTP, thème, qualité, version

## 1. Objectif

Changer sa FTP, son thème ou sa qualité graphique depuis le menu, au Click ou au clavier, sans ouvrir de fichier. Ce lot ajoute la section « Réglages » au menu du lot N6, appuyée sur le core du lot O3, et affiche la version d'OpenRide (lot O2).

**Lot interne :** il ajoute des messages au contrat IPC (décision du propriétaire) et un écran au menu ; sa recette est visuelle et se fait au Click.

## 2. À lire

1. `docs/contracts/ipc_v1.md` (révision 1.1 et ajouts de N13), `docs/lots/LOT_N13_menu_appareils.md` (même forme d'écran et de messages), `docs/lots/LOT_O3_reglages_core.md`, `docs/lots/LOT_N6_affichage_menus.md`.
2. Code : `core/src/openride_core/settings.py` (O3), `engine/scripts/menu_model.gd`, les vues du menu créées par N6.

## 3. Prérequis

N6, N13 (même révision de contrat, à faire l'un après l'autre), O3 et Q1 (commande `set_difficulty`) fusionnés ; O2 pour la version ; N10 pour plus d'un thème.

## 4. Proposition de contrat (ajouts compatibles à la révision de N13)

| Message | Sens | Champs |
| --- | --- | --- |
| `list_settings` | engine vers core (commande) | — |
| `settings` | core vers engine | `items` : liste de `{key, label, type, value, choices?, min?, max?, step?, applies}` (`applies` : `now` ou `next_session`) |
| `set_setting` | engine vers core (commande) | `key`, `value` ; réponse `ack` ou `error` avec code `setting_invalid` |

Le core n'accepte `set_setting` qu'**en dehors d'une séance** (état `IDLE` ou écran de fin) ; pendant `RUNNING` ou `PAUSED`, il répond `error` `busy` (code de N13 ; décision D6 de l'audit IPC du 26 octobre). Les schémas JSON vont dans `docs/contracts/ipc/`.

## 5. Travail demandé

- Core : traiter les trois messages en appelant `settings.current`, `settings.step` (côté engine) et `settings.apply` ; après écriture, recharger la configuration pour la séance suivante ; `hello_ack.config` reflète les nouvelles valeurs.
- Engine : état `SETTINGS` dans `menu_model.gd` (entrée depuis l'accueil, + et − pour changer la valeur, appui long pour valider, retour), vue `settings_view.gd` dans le style de N6, bips existants ; thème et qualité appliqués tout de suite au décor de fond du menu quand `applies` vaut `now`.
- **Difficulté du trainer** (lot Q1, décision du propriétaire du 25 octobre) : affichée en curseur horizontal de 0 à 100 % par pas de 10 % (+ et − pour le déplacer). Dans les réglages, elle s'enregistre par `set_setting` comme les autres. Le même curseur est proposé sur l'écran de pause de N6 : il envoie `set_difficulty` (Q1, accepté pendant la séance) et ne touche pas `config.toml`. Aucun bouton du Click ni touche dédiée.
- Ligne « OpenRide X.Y.Z » en bas de l'écran (version de `hello_ack.core_version` et de l'engine ; alerte discrète si elles diffèrent).
- Tests : modèle sans affichage (`engine/tests/unit/test_menu_model.gd` étendu), core (`core/tests/test_settings.py`), schémas, et une capture ajoutée à `engine/tests/run_visual_tests.sh` (livré : banc des menus, parcours `reglages`).

## 6. Fichiers concernés

`docs/contracts/ipc_v1.md`, `docs/contracts/ipc/*.schema.json`, `core/src/openride_core/ipc_server.py`, `session.py` (ou le module qui gère `IDLE`), `engine/scripts/menu_model.gd`, nouveau `engine/scripts/settings_view_model.gd`, `main.gd`, tests, `README.md`, `docs/SUIVI_AVANCEMENT.md`.

## 7. Critères d'acceptation

1. Toutes les suites passent (core, compilateur, engine sans écran, bout en bout `run_e2e.sh`).
2. Au clavier puis au Click : passer la FTP de 250 à 265 W, quitter, relancer : la valeur est conservée dans `~/OpenRide/config.toml` et utilisée par l'ERG.
3. Changer le thème ou la qualité depuis le menu modifie le décor de fond sans relancer.
4. `set_setting` pendant une séance est refusé et rien n'est écrit.

**Sur le PC cible (le propriétaire) :** lisibilité à 2 m, navigation au Click réel, ERG avec la nouvelle FTP.

## 8. Hors périmètre

- Réglages avancés (pente maximale, lissage, adresses Bluetooth : la section « Appareils » de N13 s'en charge).

## 9. Livraison (26 octobre 2026)

Contrat accepté par le propriétaire le 26 octobre (révision 1.3 : la 1.2 de N13 et Q1 est close depuis la fusion de P1, décision du propriétaire du 27 octobre) : `list_settings`, `set_setting`, message `settings` (`docs/contracts/ipc/settings.schema.json`), erreurs `busy` (pendant une séance, décision D6) et `setting_invalid`. `applies` vaut `next_session` ou `now` (qualité et thème).

- Core (`session.py`) : `settings` en réponse à `list_settings` et après chaque `set_setting` réussi ; refus pendant `RUNNING` et `PAUSED` ; FTP, masse, braquet de départ et difficulté pris en compte dès la séance suivante sans relancer (`hello_ack.config` aussi).
- Engine : `settings_view_model.gd` ; écran « Réglages » (Appareils puis les six réglages), écran de modification (+ / − pour changer, appui long + pour enregistrer, appui long − pour annuler), difficulté en curseur de 0 à 100 % par pas de 10 % ; **le même curseur sur l'écran de pause** envoie `set_difficulty` (Q1) sans toucher à `config.toml` ; qualité et thème appliqués tout de suite au décor de fond (`main.gd`).
- Tests : `test_menu_flow.gd` (réglages, modification, annulation, curseur de la pause), banc des menus parcours `reglages` (FTP 250 → 265 W écrite dans `config.toml`, qualité appliquée tout de suite, curseur de la pause : `Difficulté : 50 % -> 40 %` au journal du core).
- Ligne « OpenRide X.Y.Z » (27 octobre, après O2) : dernière ligne de l'écran, non sélectionnable ; version de l'engine (`project.godot`), et « core X.Y.Z : versions différentes, mettre à jour OpenRide » quand `hello_ack.core_version` diffère.
- Reste (propriétaire) : critère 2 au Click réel (FTP conservée après relance et utilisée par l'ERG), lisibilité à 2 m.
