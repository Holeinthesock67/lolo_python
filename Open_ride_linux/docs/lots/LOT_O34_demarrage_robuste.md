# Lot O34 – Démarrage robuste : séance interrompue et configuration invalide

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Démarrage robuste : séance interrompue d'un lancement précédent proposée à l'accueil (FIT ou non, commande `recover_session`), configuration invalide remise par défaut depuis une fenêtre du lanceur (copie `.bak`) | Python + GDScript | N8, MJ7 (livrés) | Petite | Livré le 31 octobre (PR #658) |

## 1. Objectif

Audit des options du 31 octobre (`docs/AUDIT_OPTIONS_MENUS_2026-10-31.md`, §7), accepté par le propriétaire le 31 octobre. Deux cas obligeaient à ouvrir un terminal ou un fichier :

- après un arrêt brutal du PC, la séance restait dans un journal sans FIT, et il fallait lancer `openride-core recover` ;
- une valeur invalide dans `config.toml` ou `profil.toml` bloquait le lancement, avec un message qui demandait de corriger le fichier à la main.

## 2. Spécification

| # | Règle |
| --- | --- |
| O34-1 | Au démarrage et après un changement de profil, le core examine les 10 derniers journaux du profil. Il retient au plus 3 séances commencées et jamais terminées (pas d'événement `stop`), qui ont des relevés et pas encore de FIT. Le journal repris par `--resume` n'est jamais retenu. |
| O34-2 | Ces séances partent dans `hello_ack.config.interrupted` : `id`, `start`, `route_id`, `distance_m`, `duration_s` (temps chronométré du dernier relevé). |
| O34-3 | L'accueil gagne en tête la ligne « Séance interrompue à enregistrer », suivie de « (+N) » s'il y en a d'autres. Le détail donne la date, le parcours, la distance et la durée. Elle ouvre l'écran « Séance interrompue » : « Enregistrer la séance » ou « Ne pas l'enregistrer », ce second choix étant confirmé avec « Non » par défaut. Y revient à l'accueil et la séance reste proposée. |
| O34-4 | `recover_session {id, save}` : avec `save` vrai, le core produit le FIT comme `recover`. Dans les deux cas, il ajoute au journal un événement `stop` de raison `interrupted` (une dernière ligne tronquée reste seule sur sa ligne). La séance n'est plus proposée. Le core répond par le message `interrupted` (séances restantes). L'engine propose la suivante, ou revient à l'accueil avec le résultat sur la ligne d'état. |
| O34-5 | Une `ConfigError` porte la valeur fautive (`section`, `key`) ou le fichier illisible (`path`). Le lanceur pose la question dans une fenêtre (zenity, sinon kdialog ; dans un terminal, `[o/N]`) : « Remettre « [section] clé » à sa valeur par défaut ? ». |
| O34-6 | Sur « Oui », la ligne est mise en commentaire dans le fichier qui la contient (`config.toml` ou `profil.toml` du profil), avec la date, après une copie `<fichier>.bak`. Un fichier qui n'est plus du TOML repart du modèle (`config.toml`) ou de son seul bloc `[profil]` (`profil.toml`). Le lanceur relit ensuite la configuration, et plusieurs valeurs se réparent l'une après l'autre, 10 au plus. |
| O34-7 | Sur « Non », ou si la faute n'est sur aucune ligne (cohérence entre deux clés par défaut), le message d'erreur reste celui d'avant et rien n'est écrit. Sans outil de fenêtre, la réponse est « Non ». |

## 3. Contrat

Révision 1.5, ajouts compatibles : liste facultative `interrupted` de `hello_ack.config`, commande `recover_session`, message `interrupted` (`docs/contracts/ipc_v1.md` §4 et §5, schémas `hello_ack`, `cmd`, `interrupted`).

## 4. Fichiers

- Core : `resume.py` (`interrupted_sessions`, `close_interrupted`), `session.py` (`_publish_interrupted`, `_recover_session`), `config.py` (`ConfigError.section`, `key`, `path`), `config_repair.py` (nouveau), `launcher.py` (`desktop_question`, `terminal_question`, boucle de réparation dans `main`).
- Engine : `menu_model.gd` (ligne de l'accueil), `menu_flow.gd` (écran, réponse, erreurs), `ipc_client.gd` (message `interrupted`), `main.gd`.
- Essais : `scripts/isolation_tests.py`, où les fenêtres muettes des tests répondent « Non ».
- Docs : contrat et schémas, `GUIDE_UTILISATION.md` §8 et §9 (`openride-core recover` n'y est plus cité), `CLAUDE.md`.
- Tests : `core/tests/test_seance_interrompue.py`, `core/tests/test_config_repair.py`, `engine/tests/unit/test_interrupted_menu.gd`.

## 5. Critères d'acceptation

1. `pytest -q` passe dans `core/`, et `run_engine_tests.sh` passe.
2. Couper le core pendant une séance (`kill -9`), le lanceur arrêté aussi, puis relancer : l'accueil propose la séance ; « Enregistrer la séance » crée le FIT dans `Activities/`, et la ligne disparaît.
3. `ftp_w = 5` dans `profil.toml` : au lancement, la fenêtre propose de remettre la FTP par défaut ; sur « Oui », OpenRide démarre et `profil.toml.bak` garde l'ancienne valeur.

## 6. Hors périmètre

`profil.toml` illisible au point que le profil lui-même ne se lit plus (`ProfileContextError`, message seul) ; la reprise en séance d'une séance interrompue d'un lancement précédent, qui reste réservée au plantage du core pendant le même lancement (lot N8).

## Livraison

PR #658, fusionnée le 31 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Audit des options du 31 octobre, accepté par le propriétaire ; en PR ».
