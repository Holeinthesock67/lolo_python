# Lot O28 – Historique dans le menu

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Historique dans le menu : séances (date, parcours, durée, NP, TSS) et leur bilan, cumul par semaine, tests de FTP ; mêmes calculs que `history`, `summary` et `ftp-test --history` | Python + GDScript | O12, L7 (livrés) | Moyenne | Audit des options du 31 octobre accepté par le propriétaire ; version 2.0 (choix du 1er novembre) ; en PR |

## 1. Objectif

Audit des options du 31 octobre (`docs/AUDIT_OPTIONS_MENUS_2026-10-31.md`, §7), accepté par le propriétaire le 31 octobre. Relire ses séances demandait le terminal : `openride-core history`, `summary` et `ftp-test --history`. Seul le bilan de la séance qui vient de finir s'affichait à l'écran.

## 2. Spécification

| # | Règle |
| --- | --- |
| O28-1 | L'accueil gagne la ligne « Historique » (détail : séances, semaines, tests de FTP), après « Test de FTP ». Elle envoie `list_history` à chaque ouverture : une séance qui vient de finir y est. |
| O28-2 | Le core répond par le message `history`, calculé par `compute_history` (`openride-core history`) avec la FTP du profil en cours : les 60 séances les plus récentes, les 8 dernières semaines où l'on a roulé, et le nombre de fichiers illisibles, qui ne sont pas listés. Il ajoute les 20 derniers tests de FTP, lus comme `ftp-test --history`. |
| O28-3 | L'écran « Historique » commence par « Cumul par semaine » et « Tests de FTP », grisés s'ils sont vides. Viennent ensuite les séances, de la plus récente à la plus ancienne. Chaque ligne montre la date, l'heure et le nom du parcours, avec en détail la durée, la distance, la NP et le TSS ; « sans fichier FIT » s'ajoute pour une séance dont il ne reste que le journal. |
| O28-4 | « Cumul par semaine » : une ligne par semaine (« Semaine du 26/10/2026 · 2 séances »), avec en détail la durée, la distance, le dénivelé et le TSS. « Tests de FTP » : la date et la FTP calculée, avec en détail la FTP d'avant et les avertissements, du plus récent au plus ancien. |
| O28-5 | A sur une séance envoie `history_session {id}`. Le bilan reçu s'affiche dans le panneau du bilan de fin de séance : mêmes lignes, et « Voir le bilan détaillé » pour les blocs ERG. Le bilan est calculé comme `openride-core summary`, avec la même forme que `state.summary`. « Retour à l'historique » et Y ramènent à la liste. |
| O28-6 | Si la séance n'existe plus ou si son fichier est devenu illisible, le core répond `bad_args`, et la raison s'affiche sur la ligne d'état. |

## 3. Contrat

Révision 1.5, ajouts compatibles : commandes `list_history` et `history_session`, messages `history` et `history_session`. Ce sont des messages d'un seul datagramme, de 60 000 octets au plus (`docs/contracts/ipc_v1.md` §2 et §4, schémas `cmd`, `history`, `history_session`).

## 4. Fichiers

- Core : `ipc_lists.py` (`build_history_message`, `history_file`, `build_history_session`), `session.py` (`_send_history`), `ipc_server.py` (types de listes, requêtes).
- Engine : `history_view_model.gd` (nouveau ; avertissements des tests de FTP repris par `menu_flow.gd`), `menu_model.gd` (ligne de l'accueil), `menu_flow.gd` (écrans, `shown_summary`), `menu_view.gd` (panneau du bilan), `ipc_client.gd`, `main.gd`.
- Docs : contrat et schémas, `GUIDE_UTILISATION.md` §8, `CLAUDE.md`.
- Tests : `core/tests/test_historique_menu.py`, `core/tests/test_contract_ipc.py`, `engine/tests/unit/test_history_menu.gd`, `test_menu_model.gd`, scénarios `menu_scenarios/` de l'accueil.

## 5. Critères d'acceptation

1. `pytest -q` passe dans `core/`, et `run_engine_tests.sh` passe.
2. Sur le PC, avec des séances enregistrées : les chiffres d'une séance à l'écran sont ceux de `openride-core history`, et son bilan est celui de `openride-core summary <fichier>`.
3. Après une séance, rouvrir « Historique » : la séance est en tête.

## 6. Hors périmètre

Les commandes `history`, `summary` et `ftp-test` restent disponibles. Ne sont pas couverts : effacer ou exporter une séance depuis le menu, accepter une FTP d'un ancien test (cela reste au bilan du test), les courbes d'une séance passée.
