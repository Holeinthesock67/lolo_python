# Lot O32 – Derniers choix du menu mémorisés par profil

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Derniers choix du menu mémorisés par profil : parcours rechargé par le core, entraînement, bot et fantôme, départ du monde ouvert (`hello_ack.config.last_choices`) | Python + GDScript | MJ7 (livré) | Petite | Livré le 31 octobre (PR #650) |

## 1. Objectif

Audit des options du 31 octobre (`docs/AUDIT_OPTIONS_MENUS_2026-10-31.md`, §7), accepté par le propriétaire le 31 octobre : à chaque lancement, le menu repartait de zéro. Il fallait rechoisir le parcours, et l'écran Prêt revenait à « Bot : aucun ». Chaque profil retrouve désormais ses derniers choix, sans réglage ni fichier à écrire.

## 2. Spécification

| # | Règle |
| --- | --- |
| O32-1 | Le core note les choix faits au menu et acceptés : parcours (`select_route` réussi, jamais un monde ouvert `ow:`), entraînement (`select_workout` réussi, jamais un test de FTP), bots et fantôme (`bots` du `start` d'une séance, liste vide sans bot) et départ du monde ouvert (`start_open_world` accepté). Une commande de la ligne de commande (`--route`, `--autostart`, `cmd_id` 0) ne change rien. |
| O32-2 | Les choix vont dans `derniers_choix.json`, dans le dossier du profil (`~/OpenRide/Profils/<profil>/`). C'est un fichier par profil, écrit de façon sûre. Une valeur refusée à la lecture est oubliée seule et le menu reprend sa valeur par défaut pour elle. |
| O32-3 | Le core publie les choix dans `hello_ack.config.last_choices`. Il les republie après chaque choix noté et à chaque changement de profil. |
| O32-4 | Au démarrage hors `--autostart` et sans reprise, puis après un changement de profil hors séance, le core recharge lui-même le dernier parcours s'il existe encore. Un parcours effacé est ignoré : « Parcours : à choisir ». |
| O32-5 | Engine, écran Prêt : le bot et le fantôme de la dernière séance sont repris à chaque nouvel accueil, au lieu de « aucun ». Un bot absent de la liste du menu revient à « aucun ». |
| O32-6 | Engine, listes : la liste des entraînements s'ouvre sur le dernier entraînement choisi, et celle des parcours sur le parcours en cours. |
| O32-7 | Engine, monde ouvert : le globe s'ouvre centré sur le dernier départ, avec le même cap, la même navigation et la même longueur de boucle. A, A, A relance donc le même départ. Une destination sans cible revient à la balade. |
| O32-8 | Le Cyber-Rogue reprend déjà l'objectif et la durée de la dernière run, lus dans le journal (`rogue.last`, lot R13), et le châssis choisi vient du profil. Une run ne change pas les bots notés. |

## 3. Contrat

Révision 1.5, ajout compatible : objet facultatif `last_choices` de `hello_ack.config` (`docs/contracts/ipc_v1.md` §5, schéma `hello_ack.schema.json`). Un engine plus ancien l'ignore.

## 4. Fichiers

- Core : `last_choices.py` (nouveau), `session.py` (`_remember`, `_publish_last_choices`, `_preselect_last_route`).
- Engine : `menu_model.gd` (`set_last_choices`, `bot_index`, focus des listes), `world_menu_model.gd` (`set_last_start`), `main.gd` (lecture du `hello_ack`).
- Docs : `ipc_v1.md`, `hello_ack.schema.json`, `GUIDE_UTILISATION.md` §7, `CLAUDE.md`.
- Tests : `core/tests/test_derniers_choix.py` ; engine `unit/test_menu_model.gd`, `unit/test_menu_flow.gd`, `unit/test_world_menu_model.gd`.

## 5. Critères d'acceptation

1. `pytest -q` passe dans `core/`, et `run_engine_tests.sh` passe.
2. Choisir un parcours, un entraînement et un bot de 200 W, rouler, quitter, relancer : l'accueil montre le parcours, l'écran Prêt « Bot : 200 W », et la liste ERG s'ouvre sur l'entraînement.
3. Un autre profil garde ses propres choix ; un profil neuf n'en a aucun.
4. Effacer le `.world` du dernier parcours : au lancement suivant, « Parcours : à choisir » et aucune erreur.

## 6. Hors périmètre

Mémoriser l'écran du menu ouvert en dernier ; les choix des plans (plan actif déjà gardé par le lot O11) ; les réglages, déjà persistés par `config.toml` et `profil.toml`.

## Livraison

PR #650, fusionnée le 31 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Audit des options du 31 octobre, accepté par le propriétaire ; en PR ».
