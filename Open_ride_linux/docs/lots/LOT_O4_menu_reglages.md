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

Le core n'accepte `set_setting` qu'**en dehors d'une séance** (état `IDLE` ou écran de fin) ; pendant `RUNNING` ou `PAUSED`, il répond `error` `setting_busy`. Les schémas JSON vont dans `docs/contracts/ipc/`.

## 5. Travail demandé

- Core : traiter les trois messages en appelant `settings.current`, `settings.step` (côté engine) et `settings.apply` ; après écriture, recharger la configuration pour la séance suivante ; `hello_ack.config` reflète les nouvelles valeurs.
- Engine : état `SETTINGS` dans `menu_model.gd` (entrée depuis l'accueil, + et − pour changer la valeur, appui long pour valider, retour), vue `settings_view.gd` dans le style de N6, bips existants ; thème et qualité appliqués tout de suite au décor de fond du menu quand `applies` vaut `now`.
- **Difficulté du trainer** (lot Q1, décision du propriétaire du 25 octobre) : affichée en curseur horizontal de 0 à 100 % par pas de 10 % (+ et − pour le déplacer). Dans les réglages, elle s'enregistre par `set_setting` comme les autres. Le même curseur est proposé sur l'écran de pause de N6 : il envoie `set_difficulty` (Q1, accepté pendant la séance) et ne touche pas `config.toml`. Aucun bouton du Click ni touche dédiée.
- Ligne « OpenRide X.Y.Z » en bas de l'écran (version de `hello_ack.core_version` et de l'engine ; alerte discrète si elles diffèrent).
- Tests : modèle sans affichage (`engine/tests/unit/test_menu_model.gd` étendu), core (`core/tests/test_ipc_settings.py`), schémas, et une capture ajoutée à `engine/tests/run_visual_tests.sh`.

## 6. Fichiers concernés

`docs/contracts/ipc_v1.md`, `docs/contracts/ipc/*.schema.json`, `core/src/openride_core/ipc_server.py`, `session.py` (ou le module qui gère `IDLE`), `engine/scripts/menu_model.gd`, nouveau `engine/scripts/settings_view.gd`, `main.gd`, tests, `README.md`, `docs/SUIVI_AVANCEMENT.md`.

## 7. Critères d'acceptation

1. Toutes les suites passent (core, compilateur, engine sans écran, bout en bout `run_e2e.sh`).
2. Au clavier puis au Click : passer la FTP de 250 à 265 W, quitter, relancer : la valeur est conservée dans `~/OpenRide/config.toml` et utilisée par l'ERG.
3. Changer le thème ou la qualité depuis le menu modifie le décor de fond sans relancer.
4. `set_setting` pendant une séance est refusé et rien n'est écrit.

**Sur le PC cible (le propriétaire) :** lisibilité à 2 m, navigation au Click réel, ERG avec la nouvelle FTP.

## 8. Hors périmètre

- Réglages avancés (pente maximale, lissage, adresses Bluetooth : la section « Appareils » de N13 s'en charge).
