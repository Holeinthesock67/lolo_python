# Lot TT1 – Contrat des bonus tactiques

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série TT : contrat IPC des bonus tactiques (valeurs de `held` et `active`, champ `refused`, réglage `powerups.mode` à trois choix), correction de la règle ERG de la spécification | Contrat | T1, révision 1.8 fermée | Petite | Prêt (version 4.0) |

Série TT (bonus tactiques, version 4.0). Plan de la série : `docs/4.0/PLAN_SERIE_TT.md`, recommandations retenues par le propriétaire le 29 octobre (« ok pour tout », §6 du plan). Cahier rédigé le 8 novembre 2026 (le plan les annonçait, aucun n'existait).

## 1. Objectif

Écrire le contrat dont les lots TT2 à TT7 ont besoin, en un seul ajout compatible.

## 2. À lire

Plan §1 à §3 ; `docs/contracts/ipc_v1.md` (objet `powerup` de `state`, révisions 1.4 à 1.8) ; `docs/SPECIFICATION_GENERALE.md` §6.1 (règle de numérotation) et §7.1 ; `core/src/openride_core/settings.py`.

## 3. Travail demandé

- **Révision :** la première libre au moment de la fusion (règle du §6.1 ; au 8 novembre, `main` est en 1.8 et 1.9 à 1.11 sont réservées par des PR ouvertes).
- Valeurs `feather`, `anvil`, `draft_plus`, `aero`, `power`, `breakaway`, `roller` de `powerup.held` et `powerup.active` ; `lightweight` reste un alias de `feather` pendant une révision.
- Champ facultatif `refused` de `powerup` : `{kind, reason}` pendant 2 s ; raisons `no_bots`, `no_descent`, `near_finish`, `no_gravel`, `erg`.
- Réglage `powerups.mode` : `off`, `classiques` (défaut, comportement d'aujourd'hui) ou `tactiques` ; l'ancien `on` est lu comme `classiques`. Message `settings` sous 1 400 octets.
- Correction de la ligne O18-7 et du §7.1 de la spécification : bonus coupés dans tout ERG, ERG de session libre compris (c'est déjà le comportement du code).
- L'engine ignore une valeur inconnue (icône neutre).

## 4. Critères d'acceptation

1. Schémas JSON de `docs/contracts/ipc/` à jour, tests du contrat verts.
2. Journal des changements d'`ipc_v1.md` et §6.1 de la spécification complétés.
3. Validation du contrat par le propriétaire avant la fusion.

## 5. Fichiers touchés

`docs/contracts/ipc_v1.md`, `docs/contracts/ipc/*.json`, `docs/SPECIFICATION_GENERALE.md`, `core/src/openride_core/config.py` (valeurs de `powerups.mode`).
