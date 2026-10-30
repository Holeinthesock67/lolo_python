# Lot MJ6 – Contrat IPC des profils

Série MJ, plan `docs/2.0/PLAN_SERIE_MJ.md` §6.

## 1. Objectif

Écrire dans le contrat les ajouts compatibles qui permettent à l'engine de lister, choisir, créer, renommer et supprimer les profils.

## 2. À lire

Plan §6 ; `docs/contracts/ipc_v1.md` (§5 et journal des changements), `docs/SPECIFICATION_GENERALE.md` §6.1.

## 3. Prérequis

MJ0.

## 4. Travail demandé

- `hello_ack.config.profile` `{id, name, type, count}` ; commandes `list_profiles`, `select_profile {id}`, `create_profile {name}`, `rename_profile {id, name}`, `delete_profile {id}` ; message `profiles` (`active`, `items` : `{id, name, type, level, last_ride, kit_primary}`, huit au plus) ; codes `profile_invalid` et `name_invalid`.
- Le core peut renvoyer un `hello_ack` complet après `select_profile` ou `create_profile` : l'engine repart alors de zéro sur ses listes (§5 du contrat).
- Révision : celle ouverte à la fusion (1.5 si elle l'est encore), ligne au journal des changements, schémas JSON et vecteurs de test.

## 5. Fichiers concernés

`docs/contracts/ipc_v1.md`, `docs/contracts/ipc/*.schema.json`, `core/tests/test_contract_ipc.py`.

## 6. Modifications de contrat autorisées

Celles du §4, ajouts compatibles seulement. **Validé par le propriétaire avant fusion.**

## 7. Critères d'acceptation

Schémas valides, vecteurs de test verts, message `profiles` de huit profils sous 1 000 octets.

## 8. Hors périmètre

Implémentation (MJ7, MJ8).

## Livraison

Livré le 30 octobre 2026 (branche `claude/project-thread-grv91v-mj6`), révision 1.5, encore ouverte (dernier ajout le 30 octobre, fin de la série R).

- `docs/contracts/ipc_v1.md` : cinq commandes au §4 (`list_profiles`, `select_profile`, `create_profile`, `rename_profile`, `delete_profile`), paragraphe « Profils de joueurs » (message `profiles`, règles hors séance, nom, idempotence), `hello_ack.config.profile` et « `hello_ack` en cours de route » au §5, codes `profile_invalid` et `name_invalid`, séquence « changement de profil » et trois exemples au §7, ligne du journal des changements.
- Schémas : `ipc/profiles.schema.json` (nouveau), `cmd`, `error` et `hello_ack` complétés.
- `core/tests/test_contract_ipc.py` : exemples valides, huit profils aux noms longs et accentués en moins de 1 000 octets, neuf profils et type inconnu refusés.
- Spécification générale §6.1 : ligne 1.5 complétée.

