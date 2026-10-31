# Lot CT1 – Contrat IPC et cahiers du mode Course tactique

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : contrat IPC et cahiers du mode Course tactique | Documentation | CT0, TT1 (4.0) | Moyenne | Prêt (version 5.0), validation du propriétaire |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`.

## 1. Objectif

Écrire l'ajout compatible du contrat pour le mode `tactical` et figer les noms des champs, pour que les lots core (CT2 à CT8) et engine (CT9 à CT11) puissent avancer en parallèle.

## 2. À lire

1. `docs/5.0/PLAN_SERIE_CT.md` (décisions du propriétaire du 29 octobre), `docs/SPECIFICATION_GENERALE.md` §6.1 et §7.1, `docs/contracts/ipc_v1.md`.
2. `docs/2.0/README.md`, cahier `LOT_T1_contrat_1_4.md` (modèle d'un lot de contrat), étude des power-ups 4.0 (série TT, contrat TT1).

## 3. Prérequis

CT0 rendu (les valeurs retenues peuvent changer les champs utiles). Contrat TT1 de la 4.0 fusionné (identifiants des effets).

## 4. Travail demandé

- Révision : la première libre à la fusion (spécification générale §6.1, ordre des fusions ; après la série U et TT1). Ligne au journal des changements de `ipc_v1.md`, schémas `docs/contracts/ipc/*.schema.json` mis à jour.
- `hello_ack.config.modes` : valeur `"tactical"`.
- Commande `start_tactical` sur le modèle de `start_run` : circuit (`circuit_id` ou graine), durée ou distance, bots (`bots` de `start`), intensité des relances (`soft`, `normal`, `strong`). Refusée en ERG ; `set_ride_mode` répond `busy` pendant le mode.
- Objet `state.tactical` (mode `TACTICAL` seulement) : `wbal_pct`, `burnout_s`, `sling_pct`, `credits_pct`, `ability` (`id` de l'effet, reste en s, ou `null`), `corner` (`d_m`, `v_crit_kmh`, `apex` : fenêtre ouverte ou non), `leech` (`id` du bot qui charge dans la roue du cycliste et sa charge, ou `null`), `branch` (même forme que `open_world.next`).
- Éléments de `bots` : `burnout` (booléen), `sling_pct`, `lane_err` (le bot rate sa trajectoire) ; `wbal_pct` existe déjà (1.4).
- `summary.tactical` : catapultes, Burnouts, capacités utilisées, temps en tête, crédits gagnés.
- Taille : pire trame mesurée avec `python -m openride_core.ipc_budget`, sous 4 096 octets sans allègement.
- Plan `docs/5.0/PLAN_SERIE_CT.md` à jour, plan des boutons ajouté au §7.1 (colonne « Course tactique »).

## 5. Fichiers concernés

- **Modifiés :** `docs/contracts/ipc_v1.md`, `docs/contracts/ipc/*.schema.json`, `core/src/openride_core/ipc_budget.py` (trame type), `core/tests/test_contract_ipc.py`, `docs/SPECIFICATION_GENERALE.md` (§6.1, §7.1), `docs/5.0/PLAN_SERIE_CT.md`, ce cahier, `00_INDEX.md`.
- **Interdits :** tout code de séance.

## 6. Modifications de contrat autorisées

Celles décrites ci-dessus, par ajout compatible ; validation du propriétaire avant fusion.

## 7. Critères d'acceptation

1. Schémas valides, exemples de trames du §7 du contrat validés par les tests.
2. Pire trame `TACTICAL` sous 4 096 octets.
3. Plan des boutons sans exception (§7.1) : Z court capacité la plus haute payable sous 100 %, Z long Overdrive (100 %), A et flèches comme au monde ouvert pour les variantes, Y pause.

## 8. Hors périmètre

Code du mode (CT2 et suivants).
