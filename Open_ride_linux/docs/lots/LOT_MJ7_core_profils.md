# Lot MJ7 – Core : choisir, créer, renommer et supprimer un profil

Série MJ, plan `docs/2.0/PLAN_SERIE_MJ.md` §3.2, §3.3 et §6.

## 1. Objectif

Le core répond aux commandes du contrat MJ6 et change de profil sans être relancé.

## 2. À lire

Plan §3 et §6 ; lots MJ4 et MJ6 ; code `session.py`, `ipc_server.py`, `garage.py`, `profiles.py`.

## 3. Prérequis

MJ4, MJ6.

## 4. Travail demandé

- `list_profiles`, `select_profile` (hors séance seulement, sinon `busy` ; rechargement de la configuration effective, de la progression, des records, du plan et du dossier des journaux ; liaison du trainer et du Click gardée ; nouvelle ceinture recherchée si besoin ; `hello_ack` complet, puis `settings` et `progression`).
- `create_profile {name}` (identifiant tiré du nom, contrôle `name_invalid` : 1 à 16 caractères, lettres accentuées, chiffres, espace, tiret, nom unique ; huit profils au plus), `rename_profile`, `delete_profile` (dossier dans `Profils/.corbeille/`, refusé pour le profil en cours, le profil d'essai et le dernier profil joueur).
- `.profil_actif` lu par le lanceur pour relancer le core sur le bon profil après un plantage ; `[profils] dernier` mis à jour seulement pour un profil `joueur`.
- Commandes `openride-core profil list|create|rename|delete` pour les outils.

## 5. Fichiers concernés

`session.py`, `ipc_server.py`, `profiles.py`, `launcher.py`, `__main__.py`, tests ; interdits : l'engine.

## 6. Modifications de contrat autorisées

Aucune au-delà de MJ6.

## 7. Critères d'acceptation

1. Changement de profil hors séance : progression et réglages de l'autre profil dans le `hello_ack` suivant, liaison BLE simulée non coupée.
2. `select_profile` pendant une séance : `busy`.
3. Noms refusés et suppressions interdites : bons codes ; e2e vert.

## 8. Hors périmètre

Écrans (MJ8).
