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

## Livraison

Livré le 30 octobre 2026 (branche `claude/project-thread-grv91v-mj7`, empilée sur MJ5 et MJ6).

- `profiles.py` : `list_contexts` (joueurs triés par nom, puis le profil d'essai), `check_name` (1 à 16 caractères, lettres accentuées, chiffres, espace, tiret, espaces en trop retirés, nom unique sans tenir compte de la casse), `id_from_name` (« Thérèse » → `therese`, `-2` si pris), `create` (huit profils joueur au plus), `rename` (l'identifiant reste), `delete` (corbeille `Profils/.corbeille/<id>_AAAAMMJJ-HHMMSS`, refusé pour le profil en cours, le profil d'essai, le dernier profil joueur et un profil verrouillé par une séance), `default_id` (`[profils] dernier`, sinon le seul profil joueur, sinon `principal`, une fois la migration MJ5 finie), `.profil_actif`.
- `session.py` : commandes `list_profiles` (calcul hors de la boucle), `select_profile`, `create_profile` (copie du même datagramme ignorée), `rename_profile`, `delete_profile` ; hors séance seulement (`busy`) ; `hello_ack.config.profile` ; changement de profil : verrou pris sur le nouveau avant de rendre l'ancien, configuration effective, progression, records, journaux, vent, braquet de départ et difficulté rechargés, ceinture cardio changée si le profil en a une autre, W' estimé recalculé, puis `hello_ack`, `settings` et `progression` ; trainer et Click intacts.
- `config.py` : section `[profils] dernier` (SRS §11) ; écrite seulement pour un profil `joueur`.
- `launcher.py` : `Supervisor.active_profile_path` ; après un plantage du core ou une relance du menu, le core repart sur le profil noté dans `.profil_actif` (jamais le profil d'essai), avec ses journaux pour la reprise.
- `__main__.py` : `openride-core profil list [--json] | create NOM | rename ID NOM | delete ID` ; le verrou de la séance suit le profil choisi au menu.
- Tests : `core/tests/test_profils_joueurs.py`.
